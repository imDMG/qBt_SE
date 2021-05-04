# VERSION: 1.5
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
from html import unescape
from http.cookiejar import Cookie, MozillaCookieJar
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
    "ua": "Mozilla/5.0 (X11; Linux i686; rv:38.0) Gecko/20100101 Firefox/38.0 "
}

FILE = Path(__file__)
BASEDIR = FILE.parent.absolute()

FILENAME = FILE.name[:-3]
FILE_J, FILE_C = [BASEDIR / (FILENAME + fl) for fl in ['.json', '.cookie']]

PAGES = 50


def rng(t):
    return range(PAGES, -(-t // PAGES) * PAGES, PAGES)


RE_TORRENTS = re.compile(
    r'data-topic_id="(\d+?)".+?">(.+?)</a.+?tor-size"\sdata-ts_text="(\d+?)">'
    r'.+?data-ts_text="([-0-9]+?)">.+?Личи">(\d+?)</.+?data-ts_text="(\d+?)">',
    re.S
)
RE_RESULTS = re.compile(r'Результатов\sпоиска:\s(\d{1,3})\s<span', re.S)
PATTERNS = ('%s/tracker.php?nm=%s&c=%s', "%s&start=%s")

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


class Rutracker:
    name = 'Rutracker'
    url = 'https://rutracker.org/forum/'
    url_dl = url + 'dl.php?t='
    url_login = url + 'login.php'
    supported_categories = {'all': '-1'}

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
            if 'bb_session' in [cookie.name for cookie in mcj]:
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

    def login(self, mcj):
        if self.error:
            return None
        # if we wanna use https we mast add bb_ssl=1 to cookie
        mcj.set_cookie(Cookie(0, "bb_ssl", "1", None, False, ".rutracker.org",
                              True, True, "/forum/", True, True,
                              None, False, None, None, {}))
        self.session.add_handler(HTTPCookieProcessor(mcj))

        form_data = {"login_username": config['username'],
                     "login_password": config['password'],
                     "login": "Вход"}
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
        if 'bb_session' in [cookie.name for cookie in mcj]:
            mcj.save(FILE_C, ignore_discard=True, ignore_expires=True)
            logger.info("We successfully authorized")
        else:
            self.error = "We not authorized, please check your credentials!"
            logger.warning(self.error)

    def searching(self, query, first=False):
        response = self._catch_error_request(query)
        if not response:
            return None
        page, torrents_found = response.decode('cp1251'), -1
        if first:
            if "log-out-icon" not in page:
                logger.debug("Looks like we lost session id, lets login")
                self.login(MozillaCookieJar())
                if self.error:
                    return None
                # retry request because guests cant search
                response = self._catch_error_request(query)
                if not response:
                    return None
                page = response.decode('cp1251')
            # firstly we check if there is a result
            torrents_found = int(RE_RESULTS.search(page)[1])
            if not torrents_found:
                return 0
        self.draw(page)

        return torrents_found

    def draw(self, html: str):
        torrents = RE_TORRENTS.findall(html)
        for tor in torrents:
            local = time.strftime("%y.%m.%d", time.localtime(int(tor[5])))
            torrent_date = f"[{local}] " if config['torrentDate'] else ""

            prettyPrinter({
                "engine_url": self.url,
                "desc_link": self.url + "viewtopic.php?t=" + tor[0],
                "name": torrent_date + unescape(tor[1]),
                "link": self.url_dl + tor[0],
                "size": tor[2],
                "seeds": max(0, int(tor[3])),
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
rutracker = Rutracker

if __name__ == "__main__":
    if BASEDIR.parent.joinpath('settings_gui.py').exists():
        from settings_gui import EngineSettingsGUI

        EngineSettingsGUI(FILENAME)
    engine = rutracker()
    engine.search('doctor')
