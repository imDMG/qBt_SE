# VERSION: 2.1
# AUTHORS: imDMG [imdmgg@gmail.com]

# NoNaMe-Club search engine plugin for qBittorrent

import json
import logging
import os
import re
import tempfile
import threading
import time

from urllib.request import build_opener, HTTPCookieProcessor, ProxyHandler
from urllib.parse import urlencode  # , parse_qs
from urllib.error import URLError, HTTPError
from http.cookiejar import Cookie, MozillaCookieJar
from novaprinter import prettyPrinter


class nnmclub(object):
    name = 'NoNaMe-Club'
    url = 'https://nnmclub.to/forum/'
    supported_categories = {'all': '-1',
                            'movies': '14',
                            'tv': '27',
                            'music': '16',
                            'games': '17',
                            'anime': '24',
                            'software': '21'}

    # default config for nnmclub.json
    config = {
        "version": 2,
        "torrentDate": False,
        "username": "USERNAME",
        "password": "PASSWORD",
        "proxy": False,
        "proxies": {
            "http": "",
            "https": ""
        },
        "ua": "Mozilla/5.0 (X11; Linux i686; rv:38.0) Gecko/20100101 Firefox/38.0"
    }

    def __init__(self):
        # setup logging into qBittorrent/logs
        logging.basicConfig(handlers=[logging.FileHandler(self.path_to('../../logs', 'nnmclub.log'), 'w', 'utf-8')],
                            level=logging.DEBUG,
                            format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                            datefmt='%m-%d %H:%M')

        try:
            # try to load user data from file
            with open(self.path_to('nnmclub.json'), 'r+') as f:
                config = json.load(f)
                if "version" not in config.keys():
                    config.update({"version": 2, "torrentDate": False})
                    f.seek(0)
                    f.write(json.dumps(config, indent=4, sort_keys=False))
                    f.truncate()
                self.config = config
        except OSError as e:
            logging.error(e)
            # if file doesn't exist, we'll create it
            with open(self.path_to('nnmclub.json'), 'w') as f:
                f.write(json.dumps(self.config, indent=4, sort_keys=False))

        # establish connection
        self.session = build_opener()

        # add proxy handler if needed
        if self.config['proxy'] and any(self.config['proxies'].keys()):
            self.session.add_handler(ProxyHandler(self.config['proxies']))

        # change user-agent
        self.session.addheaders.pop()
        self.session.addheaders.append(('User-Agent', self.config['ua']))

        # avoid endless waiting
        self.blocked = False

        mcj = MozillaCookieJar()
        cookie_file = self.path_to('nnmclub.cookie')
        # load local cookies
        if os.path.isfile(cookie_file):
            mcj.load(cookie_file, ignore_discard=True)
            if 'phpbb2mysql_4_sid' in [cookie.name for cookie in mcj]:
                # if cookie.expires < int(time.time())
                logging.info("Local cookies is loaded")
                self.session.add_handler(HTTPCookieProcessor(mcj))
            else:
                logging.info("Local cookies expired or bad")
                logging.debug(f"That we have: {[cookie for cookie in mcj]}")
                mcj.clear()
                self.login(mcj, cookie_file)
        else:
            self.login(mcj, cookie_file)

    def login(self, mcj, cookie_file):
        # if we wanna use https we mast add ssl=enable_ssl to cookie
        mcj.set_cookie(Cookie(0, 'ssl', "enable_ssl", None, False, '.nnmclub.to', True,
                              False, '/', True, False, None, 'ParserCookie', None, None, None))
        self.session.add_handler(HTTPCookieProcessor(mcj))

        response = self._catch_error_request(self.url + 'login.php')
        if not self.blocked:
            code = re.search(r'code"\svalue="(.+?)"', response.read().decode('cp1251'))[1]
            form_data = {"username": self.config['username'],
                         "password": self.config['password'],
                         "autologin": "on",
                         "code": code,
                         "login": "Вход"}
            # so we first encode keys to cp1251 then do default decode whole string
            data_encoded = urlencode({k: v.encode('cp1251') for k, v in form_data.items()}).encode()

            self._catch_error_request(self.url + 'login.php', data_encoded)
            if 'phpbb2mysql_4_sid' not in [cookie.name for cookie in mcj]:
                logging.warning("we not authorized, please check your credentials")
            else:
                mcj.save(cookie_file, ignore_discard=True, ignore_expires=True)
                logging.info('We successfully authorized')

    def draw(self, html: str):
        torrents = re.findall(r'd\stopic.+?href="(.+?)".+?<b>(.+?)</b>.+?href="(d.+?)"'
                              r'.+?/u>\s(.+?)<.+?b>(\d+)</.+?b>(\d+)<.+?<u>(\d+)</u>', html, re.S)

        for tor in torrents:
            torrent_date = ""
            if self.config['torrentDate']:
                torrent_date = f'[{time.strftime("%d.%m.%y", time.localtime(int(tor[6])))}] '
            torrent = {"engine_url": self.url,
                       "desc_link": self.url + tor[0],
                       "name": torrent_date + tor[1],
                       "link": self.url + tor[2],
                       "size": tor[3].replace(',', '.'),
                       "seeds": tor[4],
                       "leech": tor[5]}

            prettyPrinter(torrent)
        del torrents
        # return len(torrents)

    def path_to(self, *file):
        return os.path.abspath(os.path.join(os.path.dirname(__file__), *file))

    def download_torrent(self, url):
        if self.blocked:
            return
        # Create a torrent file
        file, path = tempfile.mkstemp('.torrent')
        file = os.fdopen(file, "wb")

        # Download url
        response = self._catch_error_request(url)

        # Write it to a file
        file.write(response.read())
        file.close()

        # return file path
        logging.debug(path + " " + url)
        print(path + " " + url)

    def searching(self, query, first=False):
        response = self._catch_error_request(query)
        page = response.read().decode('cp1251')
        self.draw(page)
        total = int(re.search(r'(\d{1,3})\s\(max:', page)[1]) if first else -1

        return total

    def search(self, what, cat='all'):
        if self.blocked:
            return
        c = self.supported_categories[cat]
        query = f'{self.url}tracker.php?nm={what.replace(" ", "+")}&{"f=-1" if c == "-1" else "c=" + c}'

        # make first request (maybe it enough)
        total = self.searching(query, True)
        # do async requests
        if total > 50:
            tasks = []
            for x in range(1, -(-total//50)):
                task = threading.Thread(target=self.searching, args=(query + f"&start={x * 50}",))
                tasks.append(task)
                task.start()

            # wait slower request in stack
            for task in tasks:
                task.join()
            del tasks

        logging.debug(f"--- {time.time() - start_time} seconds ---")
        logging.info(f"Found torrents: {total}")

    def _catch_error_request(self, url='', data=None):
        url = url or self.url

        try:
            response = self.session.open(url, data)
            # Only continue if response status is OK.
            if response.getcode() != 200:
                logging.error('Unable connect')
                raise HTTPError(response.geturl(), response.getcode(),
                                f"HTTP request to {url} failed with status: {response.getcode()}",
                                response.info(), None)
        except (URLError, HTTPError) as e:
            logging.error(e)
            raise e

        # checking that tracker is'nt blocked
        self.blocked = False
        if self.url not in response.geturl():
            print(response.geturl())
            logging.warning(f"{self.url} is blocked. Try proxy or another proxy")
            self.blocked = True

        return response


if __name__ == "__main__":
    # benchmark start
    start_time = time.time()
    # nnmclub_se = nnmclub()
    # nnmclub_se.search('bird')
    print(f"--- {time.time() - start_time} seconds ---")
    # benchmark end
