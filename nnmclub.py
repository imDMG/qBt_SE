# VERSION: 2.0
# AUTHORS: imDMG [imdmgg@gmail.com]

# NoNaMe-Club search engine plugin for qBittorrent

import json
import logging
import math
import os
import re
import tempfile
import threading
import time

from urllib.request import build_opener, HTTPCookieProcessor, ProxyHandler
from urllib.parse import urlencode  # , parse_qs
from urllib.error import URLError, HTTPError
from http.cookiejar import Cookie, CookieJar
from novaprinter import prettyPrinter

# setup logging into qBittorrent/logs
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                    datefmt='%m-%d %H:%M',
                    filename=os.path.abspath(os.path.join(os.path.dirname(__file__), '../../logs', 'nnmclub.log')),
                    filemode='w')

# benchmark
start_time = time.time()


class nnmclub(object):
    name = 'NoNaMe-Club'
    url = 'https://nnm-club.me/forum/'
    supported_categories = {'all': '-1',
                            'movies': '14',
                            'tv': '27',
                            'music': '16',
                            'games': '17',
                            'anime': '24',
                            'software': '21'}

    # getting config from kinozal.json
    config = None
    try:
        # try to load user data from file
        with open(os.path.abspath(os.path.join(os.path.dirname(__file__), 'nnmclub.json'))) as f:
            config: dict = json.load(f)
    except OSError as e:
        # file not found
        logging.error(e)
        raise e

    def __init__(self):
        # establish connection
        #
        # make cookie
        cj = CookieJar()
        # if we wanna use https we mast add ssl=enable_ssl to cookie
        c = Cookie(0, 'ssl', "enable_ssl", None, False, '.nnm-club.me',
                   True, False, '/', True, False, None, 'ParserCookie', None, None, None)
        cj.set_cookie(c)
        self.session = build_opener(HTTPCookieProcessor(cj))

        # avoid endless waiting
        self.blocked = False

        # add proxy handler if needed
        if self.config['proxy'] and any(self.config['proxies'].keys()):
            self.session.add_handler(ProxyHandler(self.config['proxies']))

        # change user-agent
        self.session.addheaders.pop()
        self.session.addheaders.append(('User-Agent', self.config['ua']))

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

            if 'phpbb2mysql_4_sid' not in [cookie.name for cookie in cj]:
                logging.warning("we not authorized, please check your credentials")
            else:
                logging.info('We successfully authorized')

    def draw(self, html: str):
        torrents = re.findall(r'd\stopic.+?href="(.+?)".+?<b>(.+?)</b>.+?href="(d.+?)"'
                              r'.+?/u>\s(.+?)<.+?b>(\d+)</.+?b>(\d+)<', html, re.S)

        for tor in torrents:
            torrent = {"engine_url": self.url,
                       "desc_link": self.url + tor[0],
                       "name": tor[1],
                       "link": self.url + tor[2],
                       "size": tor[3].replace(',', '.'),
                       "seeds": tor[4],
                       "leech": tor[5]}

            prettyPrinter(torrent)
        del torrents
        # return len(torrents)

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
        total = int(re.search(r'\(max:\s(\d{1,3})\)', page)[1]) if first else -1

        return total

    def search(self, what, cat='all'):
        if self.blocked:
            return
        c = self.supported_categories[cat]
        query = '{}tracker.php?nm={}&{}'.format(self.url, what.replace(" ", "+"), "f=-1" if c == '-1' else "c=" + c)

        # make first request (maybe it enough)
        total = self.searching(query, True)
        # do async requests
        if total > 50:
            tasks = []
            for x in range(1, math.ceil(total / 50)):
                task = threading.Thread(target=self.searching, args=(query + "&start={}".format(x * 50),))
                tasks.append(task)
                task.start()

            # wait slower request in stack
            for task in tasks:
                task.join()
            del tasks

        logging.debug("--- {} seconds ---".format(time.time() - start_time))
        logging.info("Found torrents: {}".format(total))

    def _catch_error_request(self, url='', data=None):
        url = url if url else self.url

        try:
            response = self.session.open(url, data)
            # Only continue if response status is OK.
            if response.getcode() != 200:
                logging.error('Unable connect')
                raise HTTPError(response.geturl(), response.getcode(),
                                "HTTP request to {} failed with status: {}".format(url, response.getcode()),
                                response.info(), None)
        except (URLError, HTTPError) as e:
            logging.error(e)
            raise e

        # checking that tracker is'nt blocked
        self.blocked = False
        if self.url not in response.geturl():
            logging.warning("{} is blocked. Try proxy or another proxy".format(self.url))
            self.blocked = True

        return response


if __name__ == "__main__":
    nnmclub_se = nnmclub()
    nnmclub_se.search('supernatural')
