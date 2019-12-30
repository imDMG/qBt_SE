# VERSION: 1.0
# AUTHORS: imDMG [imdmgg@gmail.com]

# rutracker.org search engine plugin for qBittorrent

import base64
import json
import logging
import os
import re
import socket
import tempfile
import time

from concurrent.futures import ThreadPoolExecutor
from html import unescape
from http.cookiejar import Cookie, MozillaCookieJar
from urllib.error import URLError, HTTPError
from urllib.parse import urlencode, unquote
from urllib.request import build_opener, HTTPCookieProcessor, ProxyHandler

from novaprinter import prettyPrinter

# default config
config = {
    "version": 2,
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


def path_to(*file):
    return os.path.abspath(os.path.join(os.path.dirname(__file__), *file))


def rng(t):
    return range(50, -(-t // 50) * 50, 50)


PATTERNS = (r'(\d{1,3})\s<span',
            r'bold"\shref="(viewtopic\.php\?t=\d+)">(.+?)</a.+?(dl\.php\?t=\d+)'
            r'" >(.+?)\s&.+?data-ts_text="(.+?)">.+?Личи">(\d+)</.+?data-ts_'
            r'text="(\d+)"', '%s/tracker.php?nm=%s&c=%s', "%s&start=%s")

FILENAME = __file__[__file__.rfind('/') + 1:-3]
FILE_J, FILE_C = [path_to(FILENAME + fl) for fl in ['.json', '.cookie']]

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
    datefmt="%m-%d %H:%M")
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

try:
    # try to load user data from file
    with open(FILE_J, 'r+') as f:
        config = json.load(f)
    # logger.debug("Config is loaded.")
except OSError as e:
    logger.error(e)
    # if file doesn't exist, we'll create it
    with open(FILE_J, 'w') as f:
        f.write(json.dumps(config, indent=4, sort_keys=False))
    # also write/rewrite ico file
    with open(path_to(FILENAME + '.ico'), 'wb') as f:
        f.write(base64.b64decode(ICON))
    logger.debug("Write files.")


class rutracker:
    name = 'Rutracker'
    url = 'https://rutracker.org/forum/'
    supported_categories = {'all': '-1'}

    #                         'movies': '2',
    #                         'tv': '3',
    #                         'music': '4',
    #                         'games': '5',
    #                         'anime': '6',
    #                         'software': '7'}

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
        self.session.addheaders.pop()
        self.session.addheaders.append(('User-Agent', config['ua']))

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
            return
        query = PATTERNS[2] % (self.url, what.replace(" ", "+"),
                               self.supported_categories[cat])

        # make first request (maybe it enough)
        t0, total = time.time(), self.searching(query, True)
        if self.error:
            self.pretty_error(what)
            return
        # do async requests
        if total > 50:
            qrs = [PATTERNS[3] % (query, x) for x in rng(total)]
            with ThreadPoolExecutor(len(qrs)) as executor:
                executor.map(self.searching, qrs, timeout=30)

        logger.debug(f"--- {time.time() - t0} seconds ---")
        logger.info(f"Found torrents: {total}")

    def download_torrent(self, url: str):
        # Download url
        response = self._catch_error_request(url)
        if self.error:
            self.pretty_error(url)
            return

        # Create a torrent file
        file, path = tempfile.mkstemp('.torrent')
        with os.fdopen(file, "wb") as fd:
            # Write it to a file
            fd.write(response.read())

        # return file path
        logger.debug(path + " " + url)
        print(path + " " + url)

    def login(self, mcj):
        if self.error:
            return
        # if we wanna use https we mast add ssl=enable_ssl to cookie
        mcj.set_cookie(Cookie(0, 'ssl', "enable_ssl", None, False,
                              '.rutracker.org', True, False, '/', True,
                              False, None, 'ParserCookie', None, None, None))
        self.session.add_handler(HTTPCookieProcessor(mcj))

        form_data = {"login_username": config['username'],
                     "login_password": config['password'],
                     "login": "вход"}
        logger.debug(f"Login. Data before: {form_data}")
        # so we first encode vals to cp1251 then do default decode whole string
        data_encoded = urlencode(
            {k: v.encode('cp1251') for k, v in form_data.items()}).encode()
        logger.debug(f"Login. Data after: {data_encoded}")
        self._catch_error_request(self.url + 'login.php', data_encoded)
        if self.error:
            return
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
        page = response.read().decode('cp1251')
        self.draw(page)

        return int(re.search(PATTERNS[0], page)[1]) if first else -1

    def draw(self, html: str):
        torrents = re.findall(PATTERNS[1], html, re.S)
        for tor in torrents:
            local = time.strftime("%y.%m.%d", time.localtime(int(tor[6])))
            torrent_date = f"[{local}] " if config['torrentDate'] else ""

            prettyPrinter({
                "engine_url": self.url,
                "desc_link": self.url + tor[0],
                "name": torrent_date + unescape(tor[1]),
                "link": self.url + tor[2],
                "size": unescape(tor[3]),
                "seeds": tor[4] if tor[4].isdigit() else '0',
                "leech": tor[5]
            })
        del torrents

    def _catch_error_request(self, url='', data=None, retrieve=False):
        url = url or self.url

        try:
            response = self.session.open(url, data, 5)
            # checking that tracker is'nt blocked
            if self.url not in response.geturl():
                raise URLError(f"{self.url} is blocked. Try another proxy.")
        except (socket.error, socket.timeout) as err:
            if not retrieve:
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
        else:
            return response

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


if __name__ == "__main__":
    engine = rutracker()
    engine.search('doctor')
