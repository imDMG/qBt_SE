# VERSION: 2.6
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
from functools import partial
from html import unescape
from http.cookiejar import MozillaCookieJar
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.error import URLError, HTTPError
from urllib.parse import urlencode, unquote
from urllib.request import build_opener, HTTPCookieProcessor, ProxyHandler

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
    "magnet": True,
    "ua": "Mozilla/5.0 (X11; Linux i686; rv:38.0) Gecko/20100101 Firefox/38.0 "
}

FILE = Path(__file__)
BASEDIR = FILE.parent.absolute()

FILENAME = FILE.name[:-3]
FILE_J, FILE_C = [BASEDIR / (FILENAME + fl) for fl in ['.json', '.cookie']]

PAGES = 50


def rng(t):
    return range(1, -(-t // PAGES))


RE_TORRENTS = re.compile(
    r'nam"><a\s+?href="/(.+?)"\s+?class="r\d">(.+?)</a>.+?s\'>.+?s\'>(.+?)<.+?'
    r'sl_s\'>(\d+?)<.+?sl_p\'>(\d+?)<.+?s\'>(.+?)</td>', re.S
)
RE_RESULTS = re.compile(r'</span>Найдено\s+?(\d+?)\s+?раздач', re.S)
PATTERNS = ('%sbrowse.php?s=%s&c=%s', "%s&page=%s")

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


class Kinozal:
    name = 'Kinozal'
    url = 'http://kinozal.tv/'
    url_dl = url.replace("//", "//dl.")
    url_login = url + 'takelogin.php'
    supported_categories = {'all': '0',
                            'movies': '1002',
                            'tv': '1001',
                            'music': '1004',
                            'games': '23',
                            'anime': '20',
                            'software': '32'}

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

        # load local cookies
        mcj = MozillaCookieJar()
        try:
            mcj.load(FILE_C, ignore_discard=True)
            if 'uid' in [cookie.name for cookie in mcj]:
                # if cookie.expires < int(time.time())
                logger.info("Local cookies is loaded")
                self.session.add_handler(HTTPCookieProcessor(mcj))
            else:
                logger.info("Local cookies expired or bad")
                logger.debug(f"That we have: {[cookie for cookie in mcj]}")
                mcj.clear()
                self.login(mcj)
        except FileNotFoundError:
            self.login(mcj)

    def search(self, what, cat='all'):
        if self.error:
            self.pretty_error(what)
            return None
        query = PATTERNS[0] % (self.url, what.replace(" ", "+"),
                               self.supported_categories[cat])

        # make first request (maybe it enough)
        t0, total = time.time(), self.searching(query, True)
        if self.error:
            self.pretty_error(what)
            return None
        # do async requests
        if total > PAGES:
            qrs = [PATTERNS[1] % (query, x) for x in rng(total)]
            with ThreadPoolExecutor(len(qrs)) as executor:
                executor.map(self.searching, qrs, timeout=30)

        logger.debug(f"--- {time.time() - t0} seconds ---")
        logger.info(f"Found torrents: {total}")

    def download_torrent(self, url: str):
        # choose download method
        if config.get("magnet"):
            url = "%sget_srv_details.php?action=2&id=%s" % (self.url,
                                                            url.split('=')[1])

        response = self._catch_error_request(url)
        if self.error:
            self.pretty_error(url)
            return None

        if config.get("magnet"):
            if response.startswith(b"\x1f\x8b\x08"):
                response = gzip.decompress(response)
            path = 'magnet:?xt=urn:btih:' + response.decode()[18:58]
        else:
            # Create a torrent file
            with NamedTemporaryFile(suffix='.torrent', delete=False) as fd:
                fd.write(response)
                path = fd.name

        # return magnet link / file path
        logger.debug(path + " " + url)
        print(path + " " + url)

    def login(self, mcj):
        if self.error:
            return None
        self.session.add_handler(HTTPCookieProcessor(mcj))

        form_data = {"username": config['username'],
                     "password": config['password']}
        logger.debug(f"Login. Data before: {form_data}")
        # so we first encode vals to cp1251 then do default decode whole string
        data_encoded = urlencode(
            {k: v.encode('cp1251') for k, v in form_data.items()}
        ).encode()
        logger.debug(f"Login. Data after: {data_encoded}")

        self._catch_error_request(self.url_login, data_encoded)
        if self.error:
            return None
        logger.debug(f"That we have: {[cookie for cookie in mcj]}")
        if 'uid' in [cookie.name for cookie in mcj]:
            mcj.save(FILE_C, ignore_discard=True, ignore_expires=True)
            logger.info('We successfully authorized')
        else:
            self.error = "We not authorized, please check your credentials!"
            logger.warning(self.error)

    def searching(self, query, first=False):
        response = self._catch_error_request(query)
        if not response:
            return None
        if response.startswith(b"\x1f\x8b\x08"):
            response = gzip.decompress(response)
        page, torrents_found = response.decode('cp1251'), -1
        if first:
            # firstly we check if there is a result
            torrents_found = int(RE_RESULTS.search(page)[1])
            if not torrents_found:
                return 0
        self.draw(page)

        return torrents_found

    def draw(self, html: str):
        torrents = RE_TORRENTS.findall(html)
        _part = partial(time.strftime, "%y.%m.%d")
        # yeah this is yesterday
        yesterday = _part(time.localtime(time.time() - 86400))
        for tor in torrents:
            torrent_date = ""
            if config['torrentDate']:
                ct = tor[5].split()[0]
                if "сегодня" in ct:
                    torrent_date = _part()
                elif "вчера" in ct:
                    torrent_date = yesterday
                else:
                    torrent_date = _part(time.strptime(ct, "%d.%m.%Y"))
                torrent_date = f'[{torrent_date}] '

            # replace size units
            table = {'Т': 'T', 'Г': 'G', 'М': 'M', 'К': 'K', 'Б': 'B'}

            prettyPrinter({
                "engine_url": self.url,
                "desc_link": self.url + tor[0],
                "name": torrent_date + unescape(tor[1]),
                "link": f"{self.url_dl}download.php?id={tor[0].split('=')[-1]}",
                "size": tor[2].translate(tor[2].maketrans(table)),
                "seeds": tor[3],
                "leech": tor[4]
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
kinozal = Kinozal

if __name__ == "__main__":
    if BASEDIR.parent.joinpath('settings_gui.py').exists():
        from settings_gui import EngineSettingsGUI

        EngineSettingsGUI(FILENAME)
    engine = kinozal()
    engine.search('doctor')
