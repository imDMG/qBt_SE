# VERSION: 2.18
# AUTHORS: imDMG [imdmgg@gmail.com]

# Kinozal.tv search engine plugin for qBittorrent

import base64
import gzip
import json
import logging
import re
import socket
import sys
import time
from concurrent.futures.thread import ThreadPoolExecutor
from dataclasses import dataclass, field
from html import unescape
from http.cookiejar import MozillaCookieJar
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Callable, Optional
from urllib.error import URLError, HTTPError
from urllib.parse import urlencode, unquote, quote, urlparse
from urllib.request import build_opener, HTTPCookieProcessor, ProxyHandler

import socks

try:
    from novaprinter import prettyPrinter
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent.absolute()))
    from novaprinter import prettyPrinter

FILE = Path(__file__)
BASEDIR = FILE.parent.absolute()

FILENAME = FILE.stem
FILE_J, FILE_C, FILE_L = [BASEDIR / (FILENAME + fl)
                          for fl in (".json", ".cookie", ".log")]

RE_TORRENTS = re.compile(
    r'nam"><a\s+?href="/(?P<desc_link>.+?)"\s+?class="r\d">(?P<name>.+?)'
    r'</a>.+?s\'>.+?s\'>(?P<size>.+?)<.+?sl_s\'>(?P<seeds>\d+?)<.+?sl_p\''
    r'>(?P<leech>\d+?)<.+?s\'>(?P<pub_date>.+?)</td>', re.S
)
RE_RESULTS = re.compile(r"</span>Найдено\s+?(\d+?)\s+?раздач", re.S)
PATTERNS = ("%sbrowse.php?s=%s&c=%s", "%s&page=%s")

PAGES = 50

# base64 encoded image
ICON = ("AAABAAEAEBAAAAEAIABoBAAAFgAAACgAAAAQAAAAIAAAAAEAIAAAAAAAQAQAAAAAAAAAAA"
        "AAAAAAAAAAAACARztMgEc7/4BHO/+ARztMAAAAAIBHO0yhd2n/gEc7/6F3af+ARztMAAAA"
        "AIBHO0yARzv/gEc7/4BHO0wAAAAAgEc7/7iYiv/O4+r/pH5x/4FIPP+kfnH/zsrE/87j6v"
        "/OycL/pYB1/4BHO/+jfHD/ztbV/7+yrP+ARzv/AAAAAIBHO//O4+r/zu/9/87v/f/O7/3/"
        "zu/9/87v/f/O7/3/zu/9/87v/f/O7/3/zu/9/87v/f/O1dT/gEc7/wAAAACARztMpYB1/8"
        "7v/f8IC5X/CAuV/wgLlf8IC5X/zu/9/77h+v9vgcv/SFSy/wAAif97j87/oXdp/4BHO0wA"
        "AAAAAAAAAIBHO//O7/3/gabq/w4Tnv8OE57/gabq/87v/f96muj/DBCd/wAAif83SMf/zu"
        "/9/4BHO/8AAAAAAAAAAIBHO0ynhXv/zu/9/87v/f8OE57/CAuV/87v/f+63vn/Hyqx/wAA"
        "if9KXMX/zO38/87v/f+mhHn/gEc7TAAAAAChd2n/1eHk/87v/f/O7/3/DhOe/wgLlf9nhu"
        "T/MEPF/wAAif82ScT/utjy/87v/f/O7/3/zsrD/6F3af8AAAAAgEc7/9Pk6v/O7/3/zu/9"
        "/xQcqP8IC5X/FBqo/xUYlf9of9v/zu/9/87v/f/O7/3/zu/9/87d4f+ARzv/AAAAAIBHO/"
        "/Y19X/zu/9/87v/f8RGaT/CAuV/wAAif90h8v/zu/9/87v/f/O7/3/zu/9/87v/f/OycL/"
        "gEc7/wAAAAChd2n/up6S/87v/f/O7/3/ERmk/wgLlf9DXdj/CQ6Z/zdAqf/O7/3/zu/9/8"
        "7v/f/O7/3/upyQ/6F3af8AAAAAgEc7TIJLQP/P7/3/zu/9/xQcqP8IC5X/zu/9/46l2f8j"
        "NMD/gJXS/87v/f/O7/3/zu/9/45kXf+ARztMAAAAAAAAAACARzv/0e35/5Go2/8UHKj/CA"
        "uV/5Go2//O7/3/XHDY/w4Tn/8YHJf/QEms/9Dr9v+ARzv/AAAAAAAAAACARztMu6KY/9Hu"
        "+v8IC5X/CAuV/wgLlf8IC5X/zu/9/87v/f9OZtz/FB2q/y08wv/Q6/b/oXdp/4BHO0wAAA"
        "AAgEc7/9/s8P/R7fn/0e77/9Hu+//O7/3/zu/9/87v/f/O7/3/z+/9/9Dt+P/Q7Pf/3u3t"
        "/87n8P+ARzv/AAAAAIBHO//Sz8j/3+zw/7qhlf+IWE//o31w/9jZ2P/a7fH/2NfV/7ylm/"
        "+GVEr/qYyD/87o8f/R2dj/gEc7/wAAAACARztMgEc7/4BHO/+ARztMAAAAAIBHO0yARzv/"
        "gEc7/4BHO/+ARztMAAAAAIBHO0yARzv/gEc7/4BHO0wAAAAACCEAAAABAAAAAQAAAAEAAI"
        "ADAAAAAQAAAAEAAAABAAAAAQAAAAEAAAABAACAAwAAAAEAAAABAAAAAQAACCEAAA== ")

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
    return range(1, -(-t // PAGES))


def date_normalize(date_str: str) -> int:
    if "сейчас" in date_str:
        return int(time.time())

    pub_date, _, pub_time = date_str.split()
    if "сегодня" in pub_date:
        pub_date = time.strftime("%d.%m.%Y", time.localtime())
    elif "вчера" in pub_date:
        pub_date = time.strftime(
            "%d.%m.%Y", time.localtime(time.time() - 86400)
        )
    return int(time.mktime(time.strptime(
        f"{pub_date} {pub_time}", "%d.%m.%Y %H:%M"
    )))


class EngineError(Exception):
    ...


@dataclass
class Config:
    username: str = "USERNAME"
    password: str = "PASSWORD"
    magnet: bool = False
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
        return json.dumps(self.to_dict(), indent=4, sort_keys=False)

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


class Kinozal:
    name = "Kinozal"
    url = "https://kinozal.tv/"
    url_dl = url.replace("//", "//dl.")
    url_login = url + "takelogin.php"
    supported_categories = {"all": "0",
                            "movies": "1002",
                            "tv": "1001",
                            "music": "1004",
                            "games": "23",
                            "anime": "20",
                            "software": "32"}

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

        form_data = {"username": config.username, "password": config.password}
        logger.debug(f"Login. Data before: {form_data}")
        # encoding to cp1251 then do default encode whole string
        data_encoded = urlencode(form_data, encoding="cp1251").encode()
        logger.debug("Login. Data after: {data_encoded}")

        self._request(self.url_login, data_encoded)
        logger.debug(f"That we have: {[cookie for cookie in self.mcj]}")
        if "uid" not in [cookie.name for cookie in self.mcj]:
            raise EngineError(
                "We not authorized, please check your credentials!"
            )
        self.mcj.save(str(FILE_C), ignore_discard=True, ignore_expires=True)
        logger.info("We successfully authorized")

    def searching(self, query: str, first: bool = False) -> int:
        response = self._request(query)
        if response.startswith(b"\x1f\x8b\x08"):
            response = gzip.decompress(response)
        page, torrents_found = response.decode("cp1251"), -1
        if first:
            # check login status
            if "Гость! ( Зарегистрируйтесь )" in page:
                logger.debug("Looks like we lost session id, lets login")
                self.login()
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
        table = str.maketrans(
            {"Т": "T", "Г": "G", "М": "M", "К": "K", "Б": "B"}
        )
        for tor in RE_TORRENTS.finditer(html):
            prettyPrinter({
                "link": "{}download.php?id={}".format(
                    self.url_dl, tor.group("desc_link").split("=")[-1]
                ),
                "name": unescape(tor.group("name")),
                "size": tor.group("size").translate(table),
                "seeds": int(tor.group("seeds")),
                "leech": int(tor.group("leech")),
                "engine_url": self.url,
                "desc_link": self.url + tor.group("desc_link"),
                "pub_date": date_normalize(tor.group("pub_date")),
            })

    def _catch_errors(self, handler: Callable, *args: str):
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
                socks.set_default_proxy(
                    socks.PROXY_TYPE_SOCKS5,
                    url.hostname,
                    url.port,
                    True,
                    url.username,
                    url.password
                )
                socket.socket = socks.socksocket  # type: ignore
                break
            else:
                self.session.add_handler(ProxyHandler(config.proxies))
            logger.debug("Proxy is set!")

        # change user-agent
        self.session.addheaders = [("User-Agent", config.ua)]

        # load local cookies
        try:
            self.mcj.load(str(FILE_C), ignore_discard=True)
            if "uid" in [cookie.name for cookie in self.mcj]:
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
        # choose download method
        if config.magnet:
            url = "%sget_srv_details.php?action=2&id=%s" % (self.url,
                                                            url.split("=")[1])

        path = self._get_download_path(self._request(url))

        # return magnet link / file path
        logger.debug(path + " " + url)
        print(path + " " + url)

    @staticmethod
    def _get_download_path(response: bytes) -> str:
        if config.magnet:
            if response.startswith(b"\x1f\x8b\x08"):
                response = gzip.decompress(response)
            return "magnet:?xt=urn:btih:" + response.decode()[18:58]
        # Create a torrent file
        with NamedTemporaryFile(suffix=".torrent", delete=False) as fd:
            fd.write(response)
            return fd.name


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
            elif hasattr(err, "code"):
                reason = f"Request to {url} failed with status: {err.code}"

            raise EngineError(reason)

    def pretty_error(self, what: str, error: str) -> None:
        prettyPrinter({
            "engine_url": self.url,
            "desc_link": f"file://{FILE_L}",
            "name": f"[{unquote(what)}][Error]: {error}",
            "link": self.url + "error",
            "size": "1 TB",  # lol
            "seeds": 100,
            "leech": 100,
            "pub_date": int(time.time())
        })


# pep8
kinozal = Kinozal

if __name__ == "__main__":
    if BASEDIR.parent.joinpath("settings_gui.py").exists():
        from settings_gui import EngineSettingsGUI

        EngineSettingsGUI(FILENAME)
    engine = kinozal()
    engine.search("doctor")
