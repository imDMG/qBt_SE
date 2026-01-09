# VERSION: 1.17
# AUTHORS: imDMG [imdmgg@gmail.com]

# rutracker.org search engine plugin for qBittorrent

import base64
import json
import logging
import re
import socket
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from html import unescape
from http.cookiejar import MozillaCookieJar
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Callable, Optional, Union
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlencode, urlparse
from urllib.request import HTTPCookieProcessor, ProxyHandler, build_opener

try:
    import socks
    from novaprinter import prettyPrinter
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent.absolute()))
    import socks
    from novaprinter import prettyPrinter

FILE = Path(__file__)
BASEDIR = FILE.parent.absolute()

FILENAME = FILE.stem
FILE_J, FILE_C, FILE_L = [
    BASEDIR / (FILENAME + fl) for fl in (".json", ".cookie", ".log")
]

RE_TORRENTS = re.compile(
    r'<a\sdata-topic_id="(?P<tor_id>\d+?)".+?">(?P<name>.+?)</a.+?tor-size"'
    r'\sdata-ts_text="(?P<size>\d+?)">.+?data-ts_text="(?P<seeds>[-\d]+?)">.+?'
    r'Личи">(?P<leech>\d+?)</.+?data-ts_text="(?P<pub_date>\d+?)">',
    re.S,
)
RE_RESULTS = re.compile(r"Результатов\sпоиска:\s(\d{1,3})\s<span", re.S)
PATTERNS = ("%stracker.php?nm=%s&c=%s", "%s&start=%s")

PAGES = 50

# base64 encoded image
ICON = (
    "AAABAAEAEBAAAAEAIABoBAAAFgAAACgAAAAQAAAAIAAAAAEAIAAAAAAAAAAAABMLAAATCwAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAABs3wUAY8wFBGPMBQN2sw8A9kA6AOdOOl/nTjo/5046AOdOOg"
    "DnTjoA5046AOdOOgHnTjoAAAAAAAAAAAB28wUAY8wFAGPMBWBjzAVWXtEHAMdsKgDnTjqf504"
    "64+dOOmnnTjoh5046JudOOmLnTjp85046DAAAAAAAAAAAbN8FAGPMBQxjzAXAY8wF1WPMBSNX"
    "2AAA9z86nehNOv/nTjr750464+dOOubnTjr/5046oedOOgMAAAAAdfEFAGPMBQBjzAVPY8wF8"
    "2PMBf9jzAW0XdEHOt5XNnbhVDSm6U04v+dOOvvnTjr/5046/edOOl3nTjoAbN8FDWPMBSljzA"
    "VpY8wF3GPMBf9jzAX/Y8wF/2PMBe5Y1wXYS+MAyY2kHHvwRjvr5046/+dOOvnnTjpK5046AGP"
    "MBZRjzAXpY8wF/WPMBf9jzAX/Y8wF/2PNBP9jzAX/YswF/1rUAa/qSzat5046/udOOv/nTjr/"
    "5046iudOOgJjzAUsY8wFq2PMBfxjzAX/Y8wF/2LFDsNfvxafY90AzVjhAM/WXy6U6E07+OdOO"
    "v/nTjr/5046/+dOOuznTjpbY8wFAGPMBRJjzAWxY8wF/2PNA/5cojyQRQD/t0kn36dejFVk+E"
    "k4wedOOv/nTjr/6E447edOOsznTjrI5046pmzfBQBjzAUAY8wFWWPMBf1jzAX/YtgAu0cc7Lh"
    "GI+T/Nxb+su9LM6zoTjn/8U4v1bBAc2i/R1MT/1oLC/dOKgwAAAAAbN8FAGPMBUxjzAX6Y8wF"
    "+WPmAK5JKdyiRiPj/zgj8euqPnOP/08e4po6iosuI/zSNyTydS0j/A41JPUAAAAAAG7iBQBjz"
    "AVVY8wF2GPkAGFVfHYhRhrvwkYk4v9FJOP/WCvPn89BU3w3JfHHRiTi/0Yk4vtGJOKgRiTiEA"
    "AAAAB39QUAbeEFHGrsACdGItcBRhfzdUYk4vtGJOL/RiTi/0Yk4vA6JO7dRiTi/UYk4t1GJOK"
    "NRiTiQk0k+AcAAAAAAAAAAAAAAABGF/8ARiTiGkYk4rRGJOLMRiTiz0Yk4vNGJOL/RiTi/0Yk"
    "4tNGJOIxRiTiAFMq/wAAAAAAAAAAAAAAAAAAAAAAVCv/AE0k+gRNJPoRTST4DkYk4hFGJOJRR"
    "iTi3UYk4v9GJOJyRiTiAFMq/wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "BTKv8ARiTiAEYk4lZGJOLgRiTiN00k+AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAE0k+ABGJOIIRiTiT0Yk4g9NJPoAAAAAAAAAAAAAAAAA//8AAP//AAD/"
    "uwAA+/cAAPH3AADgcwAA5+MAAO/PAAD23wAA/v8AAP53AAD+fwAA/58AAP/fAAD//wAA//8AA"
    "A=="
)

# setup logging
logging.basicConfig(
    filemode="w",
    filename=FILE_L,
    format="%(asctime)s %(name)-12s %(levelname)-8s %(message)s",
    datefmt="%m-%d %H:%M",
    level=logging.DEBUG,
)

logger = logging.getLogger(__name__)


def rng(t: int) -> range:
    return range(PAGES, -(-t // PAGES) * PAGES, PAGES)


class EngineError(Exception): ...


@dataclass
class Config:
    username: str = "USERNAME"
    password: str = "PASSWORD"
    proxy: bool = False
    # dynamic_proxy: bool = True
    proxies: dict[str, str] = field(
        default_factory=lambda: {"http": "", "https": ""}
    )
    ua: str = (
        "Mozilla/5.0 (X11; Linux i686; rv:38.0) Gecko/20100101 Firefox/38.0 "
    )

    def __post_init__(self) -> None:
        try:
            if not self._validate_json(json.loads(FILE_J.read_text())):
                raise ValueError("Incorrect json scheme.")
        except Exception as e:
            logger.error(e)
            FILE_J.write_text(self.to_str())
            (BASEDIR / f"{FILENAME}.ico").write_bytes(base64.b64decode(ICON))

    def to_str(self) -> str:
        return json.dumps(self.to_dict(), indent=4, sort_keys=False)

    def to_dict(self) -> dict[str, Any]:
        return {self._to_camel(k): v for k, v in self.__dict__.items()}

    def _validate_json(
        self, obj: dict[str, Union[str, bool, dict[str, str]]]
    ) -> bool:
        is_valid = True
        for k, v in self.__dict__.items():
            _val = obj.get(self._to_camel(k))
            if _val is None or not isinstance(_val, type(v)):
                is_valid = False
                continue
            if isinstance(_val, dict):
                for dk, dv in v.items():
                    if not isinstance(_val.get(dk), type(dv)):
                        _val[dk] = dv
                        is_valid = False
            setattr(self, k, _val)
        return is_valid

    @staticmethod
    def _to_camel(s: str) -> str:
        return "".join(
            x.title() if i else x for i, x in enumerate(s.split("_"))
        )


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

        form_data = {
            "login_username": config.username,
            "login_password": config.password,
            "login": "Вход",
        }
        logger.debug(f"Login. Data before: {form_data}")
        # encoding to cp1251 then do default encode whole string
        data_encoded = urlencode(form_data, encoding="cp1251").encode("ascii")
        logger.debug(f"Login. Data after: {data_encoded!r}")
        self._request(self.url_login, data_encoded)
        logger.debug(f"That we have: {[cookie for cookie in self.mcj]}")
        if "bb_session" not in [cookie.name for cookie in self.mcj]:
            raise EngineError(
                "We not authorized, please check your credentials!"
            )
        self.mcj.save(str(FILE_C), ignore_discard=True, ignore_expires=True)
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
            # firstly, we check if there is a result
            match = RE_RESULTS.search(page)
            if match is None:
                logger.debug(f"Unexpected page content:\n {page}")
                raise EngineError("Unexpected page content")
            torrents_found = int(match[1])
            if torrents_found <= 0:
                return 0
        self.draw(page)

        return torrents_found

    def draw(self, html: str) -> None:
        for tor in RE_TORRENTS.finditer(html):
            prettyPrinter(
                {
                    "link": self.url_dl + tor.group("tor_id"),
                    "name": unescape(tor.group("name")),
                    "size": tor.group("size"),
                    "seeds": max(0, int(tor.group("seeds"))),
                    "leech": int(tor.group("leech")),
                    "engine_url": self.url,
                    "desc_link": (
                        self.url + "viewtopic.php?t=" + tor.group("tor_id")
                    ),
                    "pub_date": int(tor.group("pub_date")),
                }
            )

    def _catch_errors(self, handler: Callable[..., None], *args: str) -> None:
        try:
            self._init()
            handler(*args)
        except EngineError as ex:
            logger.exception(ex)
            self.pretty_error(args[0], str(ex))
        except Exception as ex:
            self.pretty_error(args[0], "Unexpected error, please check logs")
            logger.exception(ex)

    def _init(self) -> None:
        # add proxy handler if needed
        if config.proxy:
            if not any(config.proxies.values()):
                raise EngineError("Proxy enabled, but not set!")
            # socks5 support
            for proxy_str in config.proxies.values():
                if not proxy_str.lower().startswith("socks"):
                    continue
                url = urlparse(proxy_str)
                socks.set_default_proxy(  # type: ignore[attr-defined]
                    socks.PROXY_TYPE_SOCKS5,
                    url.hostname,
                    url.port,
                    True,
                    url.username,
                    url.password,
                )
                socket.socket = socks.socksocket  # type: ignore
                break
            else:
                self.session.add_handler(ProxyHandler(config.proxies))
            logger.debug("Proxy is set!")

        # change user-agent
        self.session.addheaders = [
            ("User-Agent", config.ua),
            (
                "Content-Type",
                "application/x-www-form-urlencoded; charset=cp1251",
            ),
        ]

        # load local cookies
        try:
            self.mcj.load(str(FILE_C), ignore_discard=True)
            if "bb_session" in [cookie.name for cookie in self.mcj]:
                # if cookie.expires < int(time.time())
                return logger.info("Local cookies is loaded")
            logger.info("Local cookies expired or bad, try to login")
            logger.debug(f"That we have: {[cookie for cookie in self.mcj]}")
        except FileNotFoundError:
            logger.info("Local cookies not exists, try to login")
        self.login()

    def _search(self, what: str, cat: str = "all") -> None:
        query = PATTERNS[0] % (
            self.url,
            quote(unquote(what)),
            self.supported_categories[cat],
        )

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
        self,
        url: str,
        data: Optional[bytes] = None,
        repeated: bool = False,
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
            elif isinstance(err, HTTPError):
                reason = f"Request to {url} failed with status: {err.code}"

            raise EngineError(reason)

    def pretty_error(self, what: str, error: str) -> None:
        prettyPrinter(
            {
                "engine_url": self.url,
                "desc_link": f"file://{FILE_L}",
                "name": f"[{unquote(what)}][Error]: {error}",
                "link": self.url + "error",
                "size": "1 TB",  # lol
                "seeds": 100,
                "leech": 100,
                "pub_date": int(time.time()),
            }
        )


# pep8
rutracker = Rutracker

if __name__ == "__main__":
    if BASEDIR.parent.joinpath("settings_gui.py").exists():
        from settings_gui import EngineSettingsGUI

        EngineSettingsGUI(FILENAME)
    engine = rutracker()
    engine.search("doctor")
