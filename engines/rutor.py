# VERSION: 1.8
# AUTHORS: imDMG [imdmgg@gmail.com]

# Rutor.org search engine plugin for qBittorrent

import base64
import json
import logging
import re
import sys
import time
from concurrent.futures.thread import ThreadPoolExecutor
from dataclasses import dataclass, field
from html import unescape
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Callable
from urllib.error import URLError, HTTPError
from urllib.parse import unquote, quote
from urllib.request import build_opener, ProxyHandler

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
    r'(?:gai|tum)"><td>(.+?)</td.+?href="(magnet:.+?)".+?href="/'
    r'(torrent/(\d+).+?)">(.+?)</a.+?right">([.\d]+?&nbsp;\w+?)</td.+?alt="S"\s'
    r'/>(.+?)</s.+?red">(.+?)</s', re.S
)
RE_RESULTS = re.compile(r"</b>\sРезультатов\sпоиска\s(\d{1,4})\s", re.S)
PATTERNS = ("%ssearch/%i/%i/000/0/%s",)

PAGES = 100

# base64 encoded image
ICON = ("AAABAAEAEBAAAAEAGABoAwAAFgAAACgAAAAQAAAAIAAAAAEAGAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAc4AAMwHNdcQ4vsN3fYS2fUY3fUe3fMj4fkk4fco4PYo5fgk7f5gp8Zu"
        "ZZtsa59FIXZEGm4kh74PyeoLGp8NHK4PHrwQHr8VIb8XJL4bJrUcKJ8optEdtPMBGcQAIc"
        "XeZAPVYwdA3MQFf8EDAJoFAMEEAM0AANIAAM4AAM0EAL8CAI8bXaEV1/cBHMsGDNTVWAOo"
        "dTIU5/ELuOAJM6sEALsIAMoEALkCBbgFALUGAKshgMcvpNUTzOoFQNIFANqxQgBpkmgKue"
        "8IT8UUy+8HO7MHPb8Gt+IG3vQHm9YKi84X4foKI7kRl+AWiMwSDYyxjXZAy84HdNYEALcP"
        "guYM+vsL6PgGl/wBWN4K1/EF//8LbdQEALgEVc41zMp0YC+t0N0XxPcCIbwGAMkGGOUGUv"
        "QKPPUEANsIU9ENvvAJw/ULnekGAr8FJcIUzfRycEZwzuMFnuYEArQCAdYDANYHAMQFAMwG"
        "PcwM2vsHU/QKPegLwvYEEckFBrsOt/Y+kYky5/YGgNAGAKkHAc4JMssSoN0GTb0L2/gHYP"
        "kCAPkFKOMP0fIHGc0EAKwLgNAq3OMd/P0Al9ACBqQCAMALbOMG+/8E8v0KjugBAO4CAPAG"
        "Q9MNyPYEB8QBAKQCe8cW9//T+/09+/8Aqd8GIbIFAMAKbuUG6f8Ht/IFFeEAAMYPqeYMhO"
        "EGB6oCgtUY5fuG0tv//vzs+PlQ9fwAw+4CLLoIALgJR+EFU+wEFcweZNAkquMFMrkArOor"
        "4fSrxsvWx8n5/fv5+fn3+/iC8fsLzPIAUscEALMDAL8QPtAsetUFWsUHue1r7/vc6evOzM"
        "fFx8n5/fvy+fj89vb/9/e+9/o44/oNi9kBD54CFKQJg9Qu4vu09vr/+ff89fTIz8rFx8n5"
        "/fvy+fj59vb49vf/+fbh+vtk6vw1rN03suFn6vnl/f3/+fn49vj18/TIz8rFx8n5/fvy+f"
        "j59vb39vf39/f//P3w+fme6/ak8Prv+fj//f369/r39vj18/TIz8rFx8ngBwAA4AMAAMAD"
        "AADAAwAAwAMAAMABAACAAQAAgAEAAAAAAAAAAAAAgAEAAMADAADgBwAA+B8AAPw/AAD"
        "+fwAA")

# setup logging
logging.basicConfig(
    format="%(asctime)s %(name)-12s %(levelname)-8s %(message)s",
    datefmt="%m-%d %H:%M",
    level=logging.DEBUG
)

logger = logging.getLogger(__name__)


def rng(t: int) -> range:
    return range(1, -(-t // PAGES))


class EngineError(Exception):
    ...


@dataclass
class Config:
    # username: str = "USERNAME"
    # password: str = "PASSWORD"
    torrent_date: bool = True
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


class Rutor:
    name = "Rutor"
    url = "http://rutor.info/"
    url_dl = url.replace("//", "//d.") + "download/"
    supported_categories = {"all": 0,
                            "movies": 1,
                            "tv": 6,
                            "music": 2,
                            "games": 8,
                            "anime": 10,
                            "software": 9,
                            "pictures": 3,
                            "books": 11}

    # establish connection
    session = build_opener()

    def search(self, what: str, cat: str = "all") -> None:
        self._catch_errors(self._search, what, cat)

    def download_torrent(self, url: str) -> None:
        self._catch_errors(self._download_torrent, url)

    def searching(self, query: str, first: bool = False) -> int:
        page, torrents_found = self._request(query).decode(), -1
        if first:
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
            torrent_date = ""
            if config.torrent_date:
                # replace names month
                months = ("Янв", "Фев", "Мар", "Апр", "Май", "Июн",
                          "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек")
                ct = [unescape(tor[0].replace(m, f"{i:02d}"))
                      for i, m in enumerate(months, 1) if m in tor[0]][0]
                ct = time.strftime("%y.%m.%d", time.strptime(ct, "%d %m %y"))
                torrent_date = f"[{ct}] "

            prettyPrinter({
                "engine_url": self.url,
                "desc_link": self.url + tor[2],
                "name": torrent_date + unescape(tor[4]),
                "link": tor[1] if config.magnet else self.url_dl + tor[3],
                "size": unescape(tor[5]),
                "seeds": unescape(tor[6]),
                "leech": unescape(tor[7])
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

    def _search(self, what: str, cat: str = "all") -> None:
        query = PATTERNS[0] % (self.url, 0, self.supported_categories[cat],
                               quote(unquote(what)))

        # make first request (maybe it enough)
        t0, total = time.time(), self.searching(query, True)
        # do async requests
        if total > PAGES:
            query = query.replace("h/0", "h/{}")
            qrs = [query.format(x) for x in rng(total)]
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
rutor = Rutor

if __name__ == "__main__":
    if BASEDIR.parent.joinpath("settings_gui.py").exists():
        from settings_gui import EngineSettingsGUI

        EngineSettingsGUI(FILENAME)
    engine = rutor()
    engine.search("doctor")
