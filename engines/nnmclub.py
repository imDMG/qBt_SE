# VERSION: 2.13
# AUTHORS: imDMG [imdmgg@gmail.com]

# NoNaMe-Club search engine plugin for qBittorrent

import base64
import json
import logging
import re
# import socket
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from html import unescape
from http.cookiejar import Cookie, MozillaCookieJar
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Callable
from urllib.error import URLError, HTTPError
from urllib.parse import unquote, quote
from urllib.request import build_opener, HTTPCookieProcessor, ProxyHandler

# import socks

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
    r'topictitle"\shref="(.+?)"><b>(.+?)</b>.+?href="(d.+?)".+?<u>(\d+?)</u>.+?'
    r'<b>(\d+?)</b>.+?<b>(\d+?)</b>.+?<u>(\d+?)</u>', re.S
)
RE_RESULTS = re.compile(r'TP_VER">(?:Результатов\sпоиска:\s(\d{1,3}))?\s', re.S)
# RE_CODE = re.compile(r'name="code"\svalue="(.+?)"', re.S)
PATTERNS = ("%stracker.php?nm=%s&%s", "%s&start=%s")

PAGES = 50

# base64 encoded image
ICON = ("AAABAAEAEBAAAAEAIABoBAAAFgAAACgAAAAQAAAAIAAAAAEAIAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAaQicAXRQFADICAQAHAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADz4QA8PizAP"
        "u3XQDpjEIBtgkCABoAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "BAIAEuyUAP3/8AD//akA//+hAP92SgCVAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAFA"
        "AAAAAAAAAAAAAAAAEAADjLiQD8//wA//7RFP//+lX/WlsPlwAAAAMAAAAGAAAAAAAAAAAA"
        "AAAAEAgAQqNBAP99HADfIAYAfgAAABQAAAAX21UC///4AP///Sj/+/Z//lZcMJOOjQCrqI"
        "EAwQ4CADAAAAAAAAAAAGEXAM39oAD//7oA/9ucAP94GwDFVRkK6p0wAP//owD/+KoB/+FT"
        "C///uQD//+wA//67AP6QUQC9DggAGAAAAACPNQDl964A//qqAv//3AD//8sB/39WAP85Aw"
        "X/nxkA/5MQAP/sJQD/0T8A//Z9AP/6kwD/86AA/qJGALwTAABEtzcA5cshAP/jOAD//7wg"
        "///+Dv/RUQH/AgEE8hcAAG40BgB3RAAAzlYCAPh0BAD/zh8A//+RAP//hQD/5B8A/xcAAE"
        "x+HgDXz5oc/8yfPv//2g7/6VMA/AkEABQAAAAAAAAAAQAAAA4cCgBBOwkAg3EfAKyPfQDE"
        "dkAAq0ELAGYAAAAABQMBQNldFf3/8w3///sA/7AoAPIAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAchNAPLaLgD/+8AA//eOAP9qDAGpAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAFwLgCX0h8A//WiAP/+TQD/Kg"
        "QAZAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAALQwAZqgR"
        "APr0hwD/2VIA/QAAAAYAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAoBACp6BAD/7H0A/3ZlALoAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAARAQAx4zcA/93AAPQAAAAIAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACgEASawXAPMTCgAnAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/D+sQfgfrEH4H6xBuAesQQ"
        "ADrEEAAaxBAACsQQAArEEBAKxBg/+sQQP/rEED/6xBg/+sQYf/rEGH/6xBj/+sQQ==")

# setup logging
logging.basicConfig(
    filename=f"{BASEDIR / FILENAME}.log",
    filemode="w",
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
    cookies: str = "COOKIES"
    torrent_date: bool = True
    # magnet: bool = False
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


class NNMClub:
    name = "NoNaMe-Club"
    url = "https://nnmclub.to/forum/"
    url_dl = "https://nnm-club.ws/"
    supported_categories = {"all": "-1",
                            "movies": "14",
                            "tv": "27",
                            "music": "16",
                            "games": "17",
                            "anime": "24",
                            "software": "21"}
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
        if config.cookies == "COOKIES":
            raise EngineError("Empty cookies in config file")
        for cookie in config.cookies.split("; "):
            name, value = cookie.split("=", 1)
            self.mcj.set_cookie(Cookie(
                0, name, value, None, False, "nnmclub.to", True, False,
                "/", True, False, None, False, None, None, {}
            ))

        logger.debug(f"That we have: {[cookie for cookie in self.mcj]}")
        if "phpbb2mysql_4_sid" not in [cookie.name for cookie in self.mcj]:
            raise EngineError(
                "We not authorized, please check your credentials!"
            )
        self.mcj.save(str(FILE_C), ignore_discard=True, ignore_expires=True)
        logger.info("We successfully authorized")

    def searching(self, query: str, first: bool = False) -> int:
        page, torrents_found = self._request(query).decode("cp1251",
                                                           "ignore"), -1
        if first:
            # check login status
            if f"Выход [ {config.username} ]" not in page:
                logger.debug(
                    f"Looks like we lost session id, lets login:\n {page}"
                )
                self.login()
            # firstly we check if there is a result
            try:
                torrents_found = int(RE_RESULTS.search(page)[1])
            except TypeError:
                logger.debug(f"Unexpected page content:\n {page}")
                raise EngineError("Unexpected page content")
            if torrents_found <= 0:
                return 0
        self.draw(page)

        return torrents_found

    def draw(self, html: str) -> None:
        for tor in RE_TORRENTS.findall(html):
            torrent_date = ""
            if config.torrent_date:
                _loc = time.localtime(int(tor[6]))
                torrent_date = f'[{time.strftime("%y.%m.%d", _loc)}] '

            prettyPrinter({
                "engine_url": self.url,
                "desc_link": self.url + tor[0],
                "name": torrent_date + unescape(tor[1]),
                "link": self.url + tor[2],
                "size": tor[3],
                "seeds": tor[4],
                "leech": tor[5]
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
            if "phpbb2mysql_4_data" in [cookie.name for cookie in self.mcj]:
                # if cookie.expires < int(time.time())
                return logger.info("Local cookies is loaded")
            logger.info("Local cookies expired or bad, try to login")
            logger.debug(f"That we have: {[cookie for cookie in self.mcj]}")
        except FileNotFoundError:
            logger.info("Local cookies not exists, try to login")
        self.login()

    def _search(self, what: str, cat: str = "all") -> None:
        c = self.supported_categories[cat]
        query = PATTERNS[0] % (self.url, quote(unquote(what)),
                               "f=-1" if c == "-1" else "c=" + c)

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
        # Download url
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
            logger.debug(err)
            error = str(err.reason)
            reason = f"{url} is not response! Maybe it is blocked."
            if "timed out" in error:
                if not repeated:
                    logger.debug("Request timed out. Repeating...")
                    return self._request(url, data, True)
                reason = "Request timed out"
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
nnmclub = NNMClub

if __name__ == "__main__":
    if BASEDIR.parent.joinpath("settings_gui.py").exists():
        from settings_gui import EngineSettingsGUI

        EngineSettingsGUI(FILENAME)
    engine = nnmclub()
    engine.search("doctor")
