# VERSION: 1.04
# AUTHORS: imDMG [imdmgg@gmail.com]

# LimeTorrents search engine plugin for qBittorrent

import base64
import json
import logging
import re
import socket
import sys
import time
from collections.abc import Callable
from concurrent.futures.thread import ThreadPoolExecutor
from dataclasses import dataclass, field
from html import unescape
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlparse
from urllib.request import ProxyHandler, build_opener


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
    r'tt-name"><a\s+?href="(?P<link>.+?)".+?<a\s+?href="(?P<desc_link>.+?)"'
    r'>(?P<name>.+?)<.+?tdnormal">(?P<pub_date>.+?)<.+?tdnormal">(?P<size>.+?)'
    r'<.+?tdseed">(?P<seeds>\d+?)<.+?tdleech">(?P<leech>\d+?)<',
)

RE_RESULTS = re.compile(
    r"(?:<h2>No results found</h2>|"
    r'search_stat">(?:.+>(\d+?)</a><a.+?id="next".+?)?<)',
    re.S,
)
PATTERNS = ("%s/search/%s/%s/date/%i/",)

ITEMS_PER_PAGE = 40

# base64 encoded image
ICON = (
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAACVUlEQVQ4jc2SPWgTcRjGf3eXr"
    "16aRlO0trW0sX6gRSoW/KSDKBQEF3FRFHFRhCxurq4WFxcXQSjiIigIfgxVHKyLrYtJFYW2Fq"
    "3Npbkkl/9d7jsuLZhSBDef5YWXlx8P7/PAf62jL7Nt+591R/52I61fnJ86k708cOXWtrbOsYT"
    "c0emFVuCEzqLpV985zeXH2+PHX+3LDIcbAg5Nj2ZuduXyu9XB7q42h3TMo+EniCoebpAgoEi+"
    "KgplJ8yd7b/wFkBusSOF5+Ko3UuiSsUxcIPP6M4jHuRfM1GY4Ys+yYFNk0NRaW7y7ux4DkD5E"
    "zB4ve+q5LgjrhXnzc+HhLwgHdNYFHmEX6RsL5CKFfCDT/JM2RsbzZ142wLIXtx0SYosDS2bBo"
    "s1EzUqGNmS5+AWjXS8h1N97ylaPSSUMj8a32Uj6G9r+XBgWvWkCmr6M/HYDla8/dz7IkhHBcJ"
    "J8WS+C+FrfNV30ZveiqAYtgAs0ysYCYfMZkiq39BsCVU6jG7FWa5XiXGSilsjk0wirAofCh9f"
    "t6Swd6J3T097dHZXZ1xOJRQiEQlZlvCCJpVGk5oZUDdcaiWbX5pdNp0wq6wmoQKZlaf1SOJIf"
    "FiWGQjdELsRYgofIXwaNQ+h21Q0m1LZbQoruKbdNqYVIAl0AGkgI+bduSCrHHO9MGUKn5rhUa"
    "l6lHSHku5SNnxX2OENbdy4vxZjsDpVoN0vh5HqtL1gJZsDNddP6YYvVWoeuuY71UVvxo1yeuV"
    "O/flGTVxzkwF6gZ1AHwodKBi4FIApQOMfJLGurev1G5gZHg1VzNdyAAAAAElFTkSuQmCC"
)

# setup logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
_fh = logging.FileHandler(FILE_L, mode="w")
_fh.setFormatter(
    logging.Formatter(
        fmt="%(asctime)s %(name)-12s %(levelname)-8s %(message)s",
        datefmt="%m-%d %H:%M",
    )
)
logger.addHandler(_fh)
logger.propagate = False


def rng(t: int) -> range:
    return range(2, -(-t // ITEMS_PER_PAGE) + 1)


def date_normalize(date_str: str) -> int:
    now = int(time.time())
    units = {
        "year": 31536000,
        "month": 2592000,
        "week": 604800,
        "day": 86400,
        "hour": 3600,
        "minute": 60,
    }

    date_str = date_str.replace("yesterday", "1 day").replace(
        "last month", "1 month"
    )

    match = re.search(r"(\d+)\s+(\w+)", date_str)
    if not match:
        raise ValueError(f"Invalid date string: {date_str}")

    amount, unit = int(match.group(1)), match.group(2).rstrip("s")
    if unit not in units:
        raise ValueError(f"Invalid date string: {date_str}")

    return now - amount * units[unit]


class EngineError(Exception): ...


@dataclass
class Config:
    # username: str = "USERNAME"
    # password: str = "PASSWORD"
    magnet: bool = False
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
        self, obj: dict[str, str | bool | dict[str, str]]
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


class TheLimeTorrents:
    name = "TheLimeTorrents"
    url = "https://www.limetorrents.fun"
    url_dl = "https://itorrents.net"
    supported_categories = {
        "all": "all",
        "anime": "anime",
        "software": "applications",
        "games": "games",
        "movies": "movies",
        "music": "music",
        "tv": "tv",
    }

    # establish connection
    session = build_opener()

    def search(self, what: str, cat: str = "all") -> None:
        self._catch_errors(self._search, what, cat)

    def download_torrent(self, url: str) -> None:
        self._catch_errors(self._download_torrent, url)

    def searching(self, query: str, first: bool = False) -> int:
        page, torrents_found = self._request(query).decode(), -1
        if first:
            # firstly, we check if there is a result
            match = RE_RESULTS.search(page)
            if match is None:
                logger.debug(f"Unexpected page content:\n {page}")
                raise EngineError("Unexpected page content")
            torrents_found = int(match.group(1) or 0) * ITEMS_PER_PAGE
            if torrents_found <= 0:
                return 0
        self.draw(page)

        return torrents_found

    def draw(self, html: str) -> None:
        for tor in RE_TORRENTS.finditer(html):
            prettyPrinter(
                {
                    "link": (
                        self.url + tor.group("desc_link")
                        if config.magnet
                        else tor.group("link")
                    ),
                    "name": unescape(tor.group("name")),
                    "size": tor.group("size").replace("&nbsp;", " "),
                    "seeds": max(0, int(tor.group("seeds"))),
                    "leech": max(0, int(tor.group("leech"))),
                    "engine_url": self.url,
                    "desc_link": self.url + tor.group("desc_link"),
                    "pub_date": date_normalize(
                        unescape(tor.group("pub_date").lower())
                    ),
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
                socket.socket = socks.socksocket
                break
            else:
                self.session.add_handler(ProxyHandler(config.proxies))
            logger.debug("Proxy is set!")

        # change user-agent
        self.session.addheaders = [("User-Agent", config.ua)]

    def _search(self, what: str, cat: str = "all") -> None:
        query = PATTERNS[0] % (
            self.url,
            self.supported_categories[cat],
            quote(unquote(what)),
            0,
        )

        # make first request (maybe it enough)
        t0, total = time.time(), self.searching(query, True)
        # do async requests
        if total > ITEMS_PER_PAGE:
            query = query.replace("/date/0", "/date/{}")
            qrs = [query.format(x) for x in rng(total)]
            with ThreadPoolExecutor(min(len(qrs), 8)) as executor:
                for q in qrs:
                    executor.submit(self.searching, q)

        logger.debug(f"--- {time.time() - t0} seconds ---")
        logger.info(f"Found torrents: {total}")

    def _download_torrent(self, url: str) -> None:
        # Download url
        response = self._request(url)
        if config.magnet:
            match = re.search(r'href\s*=\s*"(magnet[^"]+)"', response.decode())
            if not match:
                raise ValueError("Error, please fill a bug report!")
            logger.debug(match.group(1) + " " + url)
            print(match.group(1) + " " + url)
            return

        # Create a torrent file
        with NamedTemporaryFile(suffix=".torrent", delete=False) as fd:
            fd.write(response)

            # return file path
            logger.debug(fd.name + " " + url)
            print(fd.name + " " + url)

    def _request(
        self,
        url: str,
        data: bytes | None = None,
        repeated: bool = False,
    ) -> bytes:
        try:
            with self.session.open(url, data, 15) as r:
                # check if the response is from the correct domain
                if r.geturl().startswith((self.url, self.url_dl)):
                    return r.read()
                raise EngineError(f"{url} is blocked. Try another proxy.")

        except (URLError, HTTPError, TimeoutError) as err:
            reason = getattr(err, "reason", None)
            if isinstance(err, HTTPError):
                raise EngineError(
                    f"Request to {url} failed with status: {err.code}"
                ) from err

            if isinstance(err, TimeoutError) or isinstance(
                reason, TimeoutError
            ):
                if not repeated:
                    logger.debug("Request timed out. Repeating...")
                    return self._request(url, data, True)

                raise EngineError(
                    f"{url} is not responding (timed out)."
                ) from err

            if isinstance(reason, str) and reason == "no host given":
                raise EngineError("Proxy is bad, try another!") from err

            raise EngineError(
                f"{url} is not response! Maybe it is blocked."
            ) from err

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
thelimetorrents = TheLimeTorrents

if __name__ == "__main__":
    if BASEDIR.parent.joinpath("settings_gui.py").exists():
        from settings_gui import EngineSettingsGUI

        EngineSettingsGUI(str(BASEDIR / FILENAME))
    engine = thelimetorrents()
    engine.search("doctor")
