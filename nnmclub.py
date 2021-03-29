# VERSION: 2.7
# AUTHORS: imDMG [imdmgg@gmail.com]

# NoNaMe-Club search engine plugin for qBittorrent

import base64
import json
import logging
import re
import socket
import time
from concurrent.futures import ThreadPoolExecutor
from html import unescape
from http.cookiejar import Cookie, MozillaCookieJar
from pathlib import Path
from tempfile import NamedTemporaryFile
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
    "magnet": True,
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
    r'topictitle"\shref="(.+?)"><b>(.+?)</b>.+?href="(d.+?)".+?<u>(\d+?)</u>.+?'
    r'<b>(\d+)</b>.+?<b>(\d+)</b>.+?<u>(\d+)</u>', re.S
)
RE_RESULTS = re.compile(r'TP_VER">(?:Результатов\sпоиска:\s(\d{1,3}))?\s', re.S)
RE_CODE = re.compile(r'name="code"\svalue="(.+?)"', re.S)
PATTERNS = ('%stracker.php?nm=%s&%s', "%s&start=%s")

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


class NNMClub:
    name = 'NoNaMe-Club'
    url = 'https://nnmclub.to/forum/'
    url_dl = 'https://nnm-club.ws/'
    url_login = url + 'login.php'
    supported_categories = {'all': '-1',
                            'movies': '14',
                            'tv': '27',
                            'music': '16',
                            'games': '17',
                            'anime': '24',
                            'software': '21'}

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
            key = 'phpbb2mysql_4_data'
            if [True for c in mcj if c.name == key and c.expires > time.time()]:
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
        c = self.supported_categories[cat]
        query = PATTERNS[0] % (self.url, what.replace(" ", "+"),
                               "f=-1" if c == "-1" else "c=" + c)

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
        # if we wanna use https we mast add ssl=enable_ssl to cookie
        mcj.set_cookie(Cookie(0, "ssl", "enable_ssl", None, False,
                              ".nnmclub.to", True, False, "/", True,
                              False, None, False, None, None, {}))
        self.session.add_handler(HTTPCookieProcessor(mcj))

        response = self._catch_error_request(self.url_login)
        if not response:
            return None
        code = RE_CODE.search(response.decode('cp1251'))[1]
        form_data = {"username": config['username'],
                     "password": config['password'],
                     "autologin": "on",
                     "code": code,
                     "login": "Вход"}
        # so we first encode vals to cp1251 then do default decode whole string
        data_encoded = urlencode(
            {k: v.encode('cp1251') for k, v in form_data.items()}
        ).encode()

        self._catch_error_request(self.url_login, data_encoded)
        if self.error:
            return None
        logger.debug(f"That we have: {[cookie for cookie in mcj]}")
        if 'phpbb2mysql_4_sid' in [cookie.name for cookie in mcj]:
            mcj.save(FILE_C, ignore_discard=True, ignore_expires=True)
            logger.info('We successfully authorized')
        else:
            self.error = "We not authorized, please check your credentials!"
            logger.warning(self.error)

    def draw(self, html: str):
        torrents = RE_TORRENTS.findall(html)

        for tor in torrents:
            torrent_date = ""
            if config['torrentDate']:
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
        del torrents

    def searching(self, query, first=False):
        response = self._catch_error_request(query)
        if not response:
            return None
        page, torrents_found = response.decode('cp1251'), -1
        if first:
            # check login status
            if f'Выход [ {config["username"]} ]' not in page:
                logger.debug("Looks like we lost session id, lets login")
                self.login(MozillaCookieJar())
                if self.error:
                    return None
            # firstly we check if there is a result
            torrents_found = int(RE_RESULTS.search(page)[1] or 0)
            if not torrents_found:
                return 0
        self.draw(page)

        return torrents_found

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
nnmclub = NNMClub

if __name__ == "__main__":
    engine = nnmclub()
    engine.search('doctor')
