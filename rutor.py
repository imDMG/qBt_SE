# VERSION: 1.3
# AUTHORS: imDMG [imdmgg@gmail.com]

# Rutor.org search engine plugin for qBittorrent

import base64
import json
import logging
import re
import socket
import sys
import time
from concurrent.futures.thread import ThreadPoolExecutor
from html import unescape
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.error import URLError, HTTPError
from urllib.parse import unquote
from urllib.request import build_opener, ProxyHandler

try:
    from novaprinter import prettyPrinter
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent.absolute()))
    from novaprinter import prettyPrinter

# default config
config = {
    "torrentDate": True,
    "username": "USERNAME",
    "password": "PASSWORD",
    "proxy": False,
    "proxies": {
        "http": "",
        "https": ""
    },
    "ua": "Mozilla/5.0 (X11; Linux i686; rv:38.0) Gecko/20100101 Firefox/38.0 "
}

FILE = Path(__file__)
BASEDIR = FILE.parent.absolute()

FILENAME = FILE.name[:-3]
FILE_J, FILE_C = [BASEDIR / (FILENAME + fl) for fl in ['.json', '.cookie']]

PAGES = 100


def rng(t):
    return range(1, -(-t // PAGES))


RE_TORRENTS = re.compile(
    r'(?:gai|tum)"><td>(.+?)</td.+?href="/(torrent/(\d+).+?)">(.+?)</a.+?right"'
    r'>([.\d]+&nbsp;\w+)</td.+?alt="S"\s/>(.+?)</s.+?red">(.+?)</s', re.S
)
RE_RESULTS = re.compile(r'</b>\sРезультатов\sпоиска\s(\d{1,4})\s', re.S)
PATTERNS = ('%ssearch/%i/%i/000/0/%s',)

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

try:
    config = json.loads(FILE_J.read_text())
    logger.debug("Config is loaded.")
except OSError as e:
    logger.error(e)
    # if file doesn't exist, we'll create it
    FILE_J.write_text(json.dumps(config, indent=4, sort_keys=False))
    # also write/rewrite ico file
    (BASEDIR / (FILENAME + '.ico')).write_bytes(base64.b64decode(ICON))
    logger.debug("Write files.")


class Rutor:
    name = 'Rutor'
    url = 'http://rutor.info/'
    url_dl = url.replace("//", "//d.") + "download/"
    supported_categories = {'all': 0,
                            'movies': 1,
                            'tv': 6,
                            'music': 2,
                            'games': 8,
                            'anime': 10,
                            'software': 9,
                            'pictures': 3,
                            'books': 11}

    def __init__(self):
        # error message
        self.error = None

        # establish connection
        self.session = build_opener()

        # add proxy handler if needed
        if config['proxy']:
            if any(config['proxies'].values()):
                self.session.add_handler(ProxyHandler(config['proxies']))
                logger.debug("Proxy is set!")
            else:
                self.error = "Proxy enabled, but not set!"

        # change user-agent
        self.session.addheaders = [('User-Agent', config['ua'])]

    def search(self, what, cat='all'):
        if self.error:
            self.pretty_error(what)
            return None
        query = PATTERNS[0] % (self.url, 0, self.supported_categories[cat],
                               what.replace(" ", "+"))

        # make first request (maybe it enough)
        t0, total = time.time(), self.searching(query, True)
        if self.error:
            self.pretty_error(what)
            return None
        # do async requests
        if total > PAGES:
            query = query.replace('h/0', 'h/%i')
            qrs = [query % x for x in rng(total)]
            with ThreadPoolExecutor(len(qrs)) as executor:
                executor.map(self.searching, qrs, timeout=30)

        logger.debug(f"--- {time.time() - t0} seconds ---")
        logger.info(f"Found torrents: {total}")

    def download_torrent(self, url: str):
        # Download url
        response = self._catch_error_request(url)
        if self.error:
            self.pretty_error(url)
            return None

        # Create a torrent file
        with NamedTemporaryFile(suffix='.torrent', delete=False) as fd:
            fd.write(response)

            # return file path
            logger.debug(fd.name + " " + url)
            print(fd.name + " " + url)

    def searching(self, query, first=False):
        response = self._catch_error_request(query)
        if not response:
            return None
        page, torrents_found = response.decode(), -1
        if first:
            # firstly we check if there is a result
            torrents_found = int(RE_RESULTS.search(page)[1])
            if not torrents_found:
                return 0
        self.draw(page)

        return torrents_found

    def draw(self, html: str):
        torrents = RE_TORRENTS.findall(html)
        for tor in torrents:
            torrent_date = ""
            if config['torrentDate']:
                # replace names month
                months = ('Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн',
                          'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек')
                ct = [unescape(tor[0].replace(m, f"{i:02d}"))
                      for i, m in enumerate(months, 1) if m in tor[0]][0]
                ct = time.strftime("%y.%m.%d", time.strptime(ct, "%d %m %y"))
                torrent_date = f'[{ct}] '

            prettyPrinter({
                "engine_url": self.url,
                "desc_link": self.url + tor[1],
                "name": torrent_date + unescape(tor[3]),
                "link": self.url_dl + tor[2],
                "size": unescape(tor[4]),
                "seeds": unescape(tor[5]),
                "leech": unescape(tor[6])
            })
        del torrents

    def _catch_error_request(self, url=None, data=None, repeated=False):
        url = url or self.url

        try:
            with self.session.open(url, data, 5) as r:
                # checking that tracker isn't blocked
                if r.url.startswith((self.url, self.url_dl)):
                    return r.read()
                raise URLError(f"{self.url} is blocked. Try another proxy.")
        except (socket.error, socket.timeout) as err:
            if not repeated:
                return self._catch_error_request(url, data, True)
            logger.error(err)
            self.error = f"{self.url} is not response! Maybe it is blocked."
            if "no host given" in err.args:
                self.error = "Proxy is bad, try another!"
        except (URLError, HTTPError) as err:
            logger.error(err.reason)
            self.error = err.reason
            if hasattr(err, 'code'):
                self.error = f"Request to {url} failed with status: {err.code}"

        return None

    def pretty_error(self, what):
        prettyPrinter({"engine_url": self.url,
                       "desc_link": "https://github.com/imDMG/qBt_SE",
                       "name": f"[{unquote(what)}][Error]: {self.error}",
                       "link": self.url + "error",
                       "size": "1 TB",  # lol
                       "seeds": 100,
                       "leech": 100})

        self.error = None


# pep8
rutor = Rutor

if __name__ == "__main__":
    if BASEDIR.parent.joinpath('settings_gui.py').exists():
        from settings_gui import EngineSettingsGUI

        EngineSettingsGUI(FILENAME)
    engine = rutor()
    engine.search('doctor')
