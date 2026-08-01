# VERSION: 1.22
# AUTHORS: imDMG [imdmgg@gmail.com]

# ThePirateBay search engine plugin for qBittorrent

import base64
import json
import logging
import re
import socket
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from html import unescape
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlencode, urlparse
from urllib.request import ProxyHandler, build_opener


if __name__ == "__main__" or __name__.startswith(Path(__file__).stem):
    sys.path.insert(0, str(Path(__file__).parent.parent.absolute()))

import socks
from novaprinter import prettyPrinter


FILE = Path(__file__)
BASEDIR = FILE.parent.absolute()

FILENAME = FILE.stem
FILE_J, FILE_C, FILE_L = [
    BASEDIR / (FILENAME + fl) for fl in (".json", ".cookie", ".log")
]

PATTERNS = ("%sq.php?q=%s&cat=%s", "magnet:?xt=urn:btih:{}&{}&%s")

ITEMS_PER_PAGE = 100

# base64 encoded image
ICON = (
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAMAAAAoLQ9TAAAAZlBMVEX///8AAAD+/v5DQ0Ovr"
    "69ZWVlJSUlUVFQFBQUTExMQEBBfX1+ysrJlZWU2Njbl5eUfHx8nJyfR0dGcnJyOjo6lpaU9PT"
    "3x8fHX19ctLS2IiIhxcXEbGxu/v7+CgoJ6enrIyMjd3d1jlIJrAAAAnklEQVQYlVWP0RKEIAh"
    "FIbPUrDSzMrPa///JpTab2fPGgbkAAFFk4GapWMbfosSXOguBUgmByB8RhkYvrV5f0fXcWDtk"
    "4RDVFaAEdsUj0Ai0lBFILNFRp96wmRQyOiXhPnpdeu/LUveOw4FsasaBZufT7ZJBiswfEmVnt"
    "omzYAF6ZRhvx7UOUzRNokkZ53v9nDie16vpVxN99YF/KPoLnGwIE09eqPEAAAAASUVORK5CYI"
    "I="
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


class EngineError(Exception): ...


@dataclass
class Config:
    # username: str = "USERNAME"
    # password: str = "PASSWORD"
    proxy: bool = False
    proxies: dict[str, str] = field(
        default_factory=lambda: {"http": "", "https": ""}
    )
    ua: str = (
        "Mozilla/5.0 (X11; Linux i686; rv:38.0) Gecko/20100101 Firefox/38.0 "
    )
    trackers: list[str] = field(default_factory=list)

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


class ThePirateBay:
    name = "ThePirateBay"
    url = "https://thepiratebay.org/"
    url_api = "https://apibay.org/"
    supported_categories = {
        "all": "0",
        "books": "601",
        "games": "400",
        "movies": "200",
        "music": "100",
        "pictures": "603",
        "software": "300",
        "tv": "205,208,212",
    }

    # establish connection
    session = build_opener()
    _magnet: str

    def search(self, what: str, cat: str = "all") -> None:
        self._catch_errors(self._search, what, cat)

    def searching(self, query: str, first: bool = False) -> int:
        json_data: list[dict[str, str]] = json.loads(
            self._request(query).decode()
        )
        if json_data[0]["id"] == "0":
            return 0

        self.draw(json_data)

        return len(json_data)

    def draw(self, json_data: list[dict[str, str]]) -> None:
        for tor in json_data:
            prettyPrinter(
                {
                    "link": self._magnet.format(
                        tor["info_hash"],
                        urlencode({"dn": tor["name"]}),
                    ),
                    "name": unescape(tor["name"]),
                    "size": int(tor["size"]),
                    "seeds": max(0, int(tor["seeders"])),
                    "leech": max(0, int(tor["leechers"])),
                    "engine_url": self.url,
                    "desc_link": f"{self.url}description.php?id={tor['id']}",
                    "pub_date": int(tor["added"]),
                }
            )

    def _get_trackers(self) -> list[str]:
        if config.trackers:
            return config.trackers

        with self.session.open(f"{self.url}static/main.js") as r:
            js = r.read().decode()

        config.trackers = re.findall(
            r"^\s+?(?:let\s+?)?tr\s+?(?:\+)?=.+?\('(.+?)'\);$",
            js,
            re.MULTILINE | re.DOTALL,
        )
        FILE_J.write_text(config.to_str())

        return config.trackers

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

        self._magnet = PATTERNS[1] % urlencode(
            [("tr", t) for t in self._get_trackers()]
        )

    def _search(self, what: str, cat: str = "all") -> None:
        query = PATTERNS[0] % (
            self.url_api,
            quote(unquote(what)),
            self.supported_categories[cat],
        )

        t0, total = time.time(), self.searching(query, True)

        logger.debug(f"--- {time.time() - t0} seconds ---")
        logger.info(f"Found torrents: {total}")

    def _request(
        self,
        url: str,
        data: bytes | None = None,
        repeated: bool = False,
    ) -> bytes:
        try:
            with self.session.open(url, data, 15) as r:
                # check if the response is from the correct domain
                if r.geturl().startswith((self.url, self.url_api)):
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
thepiratebay = ThePirateBay

if __name__ == "__main__":
    if BASEDIR.parent.joinpath("settings_gui.py").exists():
        from settings_gui import EngineSettingsGUI

        EngineSettingsGUI(str(BASEDIR / FILENAME))

    engine = thepiratebay()
    engine.search("doctor")
