# VERSION: 1.9
# AUTHORS: imDMG [imdmgg@gmail.com]

# rutracker.org search engine plugin for qBittorrent

import base64
import json
import logging
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from html import unescape
from http.cookiejar import MozillaCookieJar
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Callable
from urllib.error import URLError, HTTPError
from urllib.parse import urlencode, unquote, quote
from urllib.request import build_opener, HTTPCookieProcessor, ProxyHandler

try:
    from novaprinter import prettyPrinter
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent.absolute()))
    from novaprinter import prettyPrinter

FILE = Path(__file__)
BASEDIR = FILE.parent.absolute()

FILENAME = FILE.stem
FILE_J, FILE_C = [BASEDIR / (FILENAME + fl) for fl in (".json", ".cookie")]

RE_TORRENTS = re.compile(
    r'<a\sdata-topic_id="(\d+?)".+?">(.+?)</a.+?tor-size"\sdata-ts_text="(\d+?)'
    r'">.+?data-ts_text="([-\d]+?)">.+?Личи">(\d+?)</.+?data-ts_text="(\d+?)">',
    re.S
)
RE_RESULTS = re.compile(r"Результатов\sпоиска:\s(\d{1,3})\s<span", re.S)
PATTERNS = ("%stracker.php?nm=%s&c=%s", "%s&start=%s")

PAGES = 50

# base64 encoded image
ICON = ("AAABAAEAEBAAAAEAIABoBAAAFgAAACgAAAAQAAAAIAAAAAEAIAAAAAAAAAAAABMLAAATCw"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAABs3wUAY8wFBGPMBQN2sw8A9kA6AOdOOl/nTjo/5046"
        "AOdOOgDnTjoA5046AOdOOgHnTjoAAAAAAAAAAAB28wUAY8wFAGPMBWBjzAVWXtEHAMdsKg"
        "DnTjqf50464+dOOmnnTjoh5046JudOOmLnTjp85046DAAAAAAAAAAAbN8FAGPMBQxjzAXA"
        "Y8wF1WPMBSNX2AAA9z86nehNOv/nTjr750464+dOOubnTjr/5046oedOOgMAAAAAdfEFAG"
        "PMBQBjzAVPY8wF82PMBf9jzAW0XdEHOt5XNnbhVDSm6U04v+dOOvvnTjr/5046/edOOl3n"
        "TjoAbN8FDWPMBSljzAVpY8wF3GPMBf9jzAX/Y8wF/2PMBe5Y1wXYS+MAyY2kHHvwRjvr50"
        "46/+dOOvnnTjpK5046AGPMBZRjzAXpY8wF/WPMBf9jzAX/Y8wF/2PNBP9jzAX/YswF/1rU"
        "Aa/qSzat5046/udOOv/nTjr/5046iudOOgJjzAUsY8wFq2PMBfxjzAX/Y8wF/2LFDsNfvx"
        "afY90AzVjhAM/WXy6U6E07+OdOOv/nTjr/5046/+dOOuznTjpbY8wFAGPMBRJjzAWxY8wF"
        "/2PNA/5cojyQRQD/t0kn36dejFVk+Ek4wedOOv/nTjr/6E447edOOsznTjrI5046pmzfBQ"
        "BjzAUAY8wFWWPMBf1jzAX/YtgAu0cc7LhGI+T/Nxb+su9LM6zoTjn/8U4v1bBAc2i/R1MT"
        "/1oLC/dOKgwAAAAAbN8FAGPMBUxjzAX6Y8wF+WPmAK5JKdyiRiPj/zgj8euqPnOP/08e4p"
        "o6iosuI/zSNyTydS0j/A41JPUAAAAAAG7iBQBjzAVVY8wF2GPkAGFVfHYhRhrvwkYk4v9F"
        "JOP/WCvPn89BU3w3JfHHRiTi/0Yk4vtGJOKgRiTiEAAAAAB39QUAbeEFHGrsACdGItcBRh"
        "fzdUYk4vtGJOL/RiTi/0Yk4vA6JO7dRiTi/UYk4t1GJOKNRiTiQk0k+AcAAAAAAAAAAAAA"
        "AABGF/8ARiTiGkYk4rRGJOLMRiTiz0Yk4vNGJOL/RiTi/0Yk4tNGJOIxRiTiAFMq/wAAAA"
        "AAAAAAAAAAAAAAAAAAVCv/AE0k+gRNJPoRTST4DkYk4hFGJOJRRiTi3UYk4v9GJOJyRiTi"
        "AFMq/wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABTKv8ARiTiAEYk4l"
        "ZGJOLgRiTiN00k+AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAE0k+ABGJOIIRiTiT0Yk4g9NJPoAAAAAAAAAAAAAAAAA//8AAP//AAD/uwAA+/cAAP"
        "H3AADgcwAA5+MAAO/PAAD23wAA/v8AAP53AAD+fwAA/58AAP/fAAD//wAA//8AAA==")

# setup logging
logging.basicConfig(
    format="%(asctime)s %(name)-12s %(levelname)-8s %(message)s",
    datefmt="%m-%d %H:%M",
    level=logging.DEBUG
)

logger = logging.getLogger(__name__)


def rng(t: int) -> range:
    return range(PAGES, -(-t // PAGES) * PAGES, PAGES)


class EngineError(Exception):
    ...


@dataclass
class Config:
    username: str = "USERNAME"
    password: str = "PASSWORD"
    torrent_date: bool = True
    proxy: bool = False
    # dynamic_proxy: bool = True
    proxies: dict = field(default_factory=lambda: {"http": "", "https": ""})
    ua: str = ("Mozilla/5.0 (X11; Linux i686; rv:38.0) Gecko/20100101 "
               "Firefox/38.0 ")

    def __post_init__(self):
        try:
            if not self._validate_json(json.loads(FILE_J.read_text())):
                raise ValueError("Incorrect json scheme.")
        except Exception as e:
            logger.error(e)
            FILE_J.write_text(self.to_str())
            (BASEDIR / f"{FILENAME}.ico").write_bytes(base64.b64decode(ICON))

    def to_str(self) -> str:
        return json.dumps(self.to_dict(), indent=4)

    def to_dict(self) -> dict:
        return {self._to_camel(k): v for k, v in self.__dict__.items()}

    def _validate_json(self, obj: dict) -> bool:
        is_valid = True
        for k, v in self.__dict__.items():
            _val = obj.get(self._to_camel(k))
            if type(_val) is not type(v):
                is_valid = False
                continue
            if type(_val) is dict:
                for dk, dv in v.items():
                    if type(_val.get(dk)) is not type(dv):
                        _val[dk] = dv
                        is_valid = False
            setattr(self, k, _val)
        return is_valid

    @staticmethod
    def _to_camel(s: str) -> str:
        return "".join(x.title() if i else x
                       for i, x in enumerate(s.split("_")))


config = Config()


class Rutracker:
    name = "Rutracker"
    url = "https://rutracker.org/forum/"
    url_dl = url + "dl.php?t="
    url_login = url + "login.php"
    supported_categories = {"all": "-1"}

    # cookies
    mcj = MozillaCookieJar()
    # establish connection
    session = build_opener(HTTPCookieProcessor(mcj))

    def search(self, what: str, cat: str = "all") -> None:
        self._catch_errors(self._search, what, cat)

    def download_torrent(self, url: str) -> None:
        self._catch_errors(self._download_torrent, url)

    def login(self) -> None:
        self.mcj.clear()

        form_data = {"login_username": config.username,
                     "login_password": config.password,
                     "login": "Вход"}
        logger.debug(f"Login. Data before: {form_data}")
        # encoding to cp1251 then do default encode whole string
        data_encoded = urlencode(form_data, encoding="cp1251").encode()
        logger.debug(f"Login. Data after: {data_encoded}")
        self._request(self.url_login, data_encoded)
        logger.debug(f"That we have: {[cookie for cookie in self.mcj]}")
        if "bb_session" not in [cookie.name for cookie in self.mcj]:
            raise EngineError(
                "We not authorized, please check your credentials!"
            )
        self.mcj.save(FILE_C, ignore_discard=True, ignore_expires=True)
        logger.info("We successfully authorized")

    def searching(self, query: str, first: bool = False) -> int:
        page, torrents_found = self._request(query).decode("cp1251"), -1
        if first:
            # check login status
            if "log-out-icon" not in page:
                if "login-form-full" not in page:
                    raise EngineError("Unexpected page content")
                logger.debug("Looks like we lost session id, lets login")
                self.login()
                # retry request because guests cant search
                page = self._request(query).decode("cp1251")
            # firstly we check if there is a result
            try:
                torrents_found = int(RE_RESULTS.search(page)[1])
            except TypeError:
                raise EngineError("Unexpected page content")
            if torrents_found <= 0:
                return 0
        self.draw(page)

        return torrents_found

    def draw(self, html: str) -> None:
        for tor in RE_TORRENTS.findall(html):
            local = time.strftime("%y.%m.%d", time.localtime(int(tor[5])))
            torrent_date = f"[{local}] " if config.torrent_date else ""

            prettyPrinter({
                "engine_url": self.url,
                "desc_link": self.url + "viewtopic.php?t=" + tor[0],
                "name": torrent_date + unescape(tor[1]),
                "link": self.url_dl + tor[0],
                "size": tor[2],
                "seeds": max(0, int(tor[3])),
                "leech": tor[4]
            })

    def _catch_errors(self, handler: Callable, *args: str):
        try:
            self._init()
            handler(*args)
        except EngineError as ex:
            self.pretty_error(args[0], str(ex))
        except Exception as ex:
            self.pretty_error(args[0], "Unexpected error, please check logs")
            logger.exception(ex)

    def _init(self) -> None:
        # add proxy handler if needed
        if config.proxy:
            if not any(config.proxies.values()):
                raise EngineError("Proxy enabled, but not set!")
            self.session.add_handler(ProxyHandler(config.proxies))
            logger.debug("Proxy is set!")

        # change user-agent
        self.session.addheaders = [("User-Agent", config.ua)]

        # load local cookies
        try:
            self.mcj.load(FILE_C, ignore_discard=True)
            if "bb_session" in [cookie.name for cookie in self.mcj]:
                # if cookie.expires < int(time.time())
                return logger.info("Local cookies is loaded")
            logger.info("Local cookies expired or bad, try to login")
            logger.debug(f"That we have: {[cookie for cookie in self.mcj]}")
        except FileNotFoundError:
            logger.info("Local cookies not exists, try to login")
        self.login()

    def _search(self, what: str, cat: str = "all") -> None:
        query = PATTERNS[0] % (self.url, quote(unquote(what)),
                               self.supported_categories[cat])

        # make first request (maybe it enough)
        t0, total = time.time(), self.searching(query, True)
        # do async requests
        if total > PAGES:
            qrs = [PATTERNS[1] % (query, x) for x in rng(total)]
            with ThreadPoolExecutor(len(qrs)) as executor:
                executor.map(self.searching, qrs, timeout=30)

        logger.debug(f"--- {time.time() - t0} seconds ---")
        logger.info(f"Found torrents: {total}")

    def _download_torrent(self, url: str) -> None:
        response = self._request(url)

        # Create a torrent file
        with NamedTemporaryFile(suffix=".torrent", delete=False) as fd:
            fd.write(response)

            # return file path
            logger.debug(fd.name + " " + url)
            print(fd.name + " " + url)

    def _request(
            self, url: str, data: bytes = None, repeated: bool = False
    ) -> bytes:
        try:
            with self.session.open(url, data, 5) as r:
                # checking that tracker isn't blocked
                if r.geturl().startswith((self.url, self.url_dl)):
                    return r.read()
                raise EngineError(f"{url} is blocked. Try another proxy.")
        except (URLError, HTTPError) as err:
            error = str(err.reason)
            reason = f"{url} is not response! Maybe it is blocked."
            if "timed out" in error and not repeated:
                logger.debug("Request timed out. Repeating...")
                return self._request(url, data, True)
            if "no host given" in error:
                reason = "Proxy is bad, try another!"
            elif hasattr(err, "code"):
                reason = f"Request to {url} failed with status: {err.code}"

            raise EngineError(reason)

    def pretty_error(self, what: str, error: str) -> None:
        prettyPrinter({
            "engine_url": self.url,
            "desc_link": "https://github.com/imDMG/qBt_SE",
            "name": f"[{unquote(what)}][Error]: {error}",
            "link": self.url + "error",
            "size": "1 TB",  # lol
            "seeds": 100,
            "leech": 100
        })


# pep8
rutracker = Rutracker

if __name__ == "__main__":
    if BASEDIR.parent.joinpath("settings_gui.py").exists():
        from settings_gui import EngineSettingsGUI

        EngineSettingsGUI(FILENAME)
    engine = rutracker()
    engine.search("doctor")
