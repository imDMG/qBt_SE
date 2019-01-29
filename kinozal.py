# VERSION: 2.0
# AUTHORS: imDMG [imdmgg@gmail.com]

# Kinozal.tv search engine plugin for qBittorrent

import json
import logging
import math
import os
import re
import tempfile
import threading
import time

from urllib.request import build_opener, HTTPCookieProcessor, ProxyHandler
from urllib.parse import urlencode
from urllib.error import URLError, HTTPError
from http.cookiejar import CookieJar
from novaprinter import prettyPrinter

# setup logging into qBittorrent/logs
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                    datefmt='%m-%d %H:%M',
                    filename=os.path.abspath(os.path.join(os.path.dirname(__file__), '../../logs', 'kinozal.log')),
                    filemode='w')

start_time = time.time()


class kinozal(object):
    name = 'Kinozal'
    url = 'http://kinozal.tv'
    supported_categories = {'all': '0',
                            'movies': '1002',
                            'tv': '1001',
                            'music': '1004',
                            'games': '23',
                            'anime': '20',
                            'software': '32'}

    # getting config from kinozal.json
    config = None
    try:
        # try to load user data from file
        with open(os.path.abspath(os.path.join(os.path.dirname(__file__), 'kinozal.json'))) as f:
            config: dict = json.load(f)
    except OSError as e:
        # file not found
        logging.error(e)
        raise e

    def __init__(self):
        logging.info('Initialisation')
        self.result = []
        # establish connection
        #
        # make cookie
        cj = CookieJar()
        self.session = build_opener(HTTPCookieProcessor(cj))

        # avoid endless waiting
        self.blocked = False

        # add proxy handler if needed
        if self.config['proxy'] and any(self.config['proxies'].keys()):
            self.session.add_handler(ProxyHandler(self.config['proxies']))

        # change user-agent
        self.session.addheaders.pop()
        self.session.addheaders.append(('User-Agent', self.config['ua']))

        form_data = {"username": self.config['username'], "password": self.config['password']}
        # so we first encode keys to cp1251 then do default decode whole string
        data_encoded = urlencode({k: v.encode('cp1251') for k, v in form_data.items()}).encode()

        self._catch_error_request(self.url + '/takelogin.php', data_encoded)
        if not self.blocked:
            if 'uid' not in [cookie.name for cookie in cj]:
                logging.warning("we not authorized, please check your credentials")
            else:
                logging.info('We successfully authorized')

    def draw(self, html: str):
        torrents = re.findall(r'nam"><a\s+?href="(.+?)"\s+?class="r\d">(.*?)</a>'
                              r'.+?s\'>.+?s\'>(.*?)<.+?sl_s\'>(\d+)<.+?sl_p\'>(\d+)<', html, re.S)

        for tor in torrents:
            torrent = {"engine_url": self.url,
                       "desc_link": self.url + tor[0],
                       "name": tor[1],
                       "link": 'http://dl.kinozal.tv/download.php?id=' + tor[0].split('=')[1],
                       "size": self.units_convert(tor[2]),
                       "seeds": tor[3],
                       "leech": tor[4]}

            prettyPrinter(torrent)
        del torrents
        # return len(torrents)

    @staticmethod
    def units_convert(unit):
        # replace size units
        find = unit.split()[1]
        replace = {'ТБ': 'TB', 'ГБ': 'GB', 'МБ': 'MB', 'КБ': 'KB'}[find]

        return unit.replace(find, replace)

    def download_torrent(self, url: str):
        if self.blocked:
            return
        # choose download method
        if self.config.get("magnet"):
            res = self._catch_error_request(self.url + "/get_srv_details.php?action=2&id=" + url.split("=")[1])
            # magnet = re.search(":\s([A-Z0-9]{40})\<", res.read().decode())[1]
            magnet = 'magnet:?xt=urn:btih:' + res.read().decode()[18:58]
            # return magnet link
            logging.debug(magnet + " " + url)
            print(magnet + " " + url)
        else:
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
        total = int(re.search(r'</span>Найдено\s+?(\d+)\s+?раздач', page)[1]) if first else -1

        return total

    def search_old(self, what, cat='all'):
        if self.blocked:
            return
        total, current = -1, 0
        while total != current:
            query = '{}/browse.php?s={}&c={}&page={}'.format(self.url, what.replace(" ", "+"),
                                                             self.supported_categories[cat],
                                                             math.ceil(current / 50))
            response = self._catch_error_request(query)
            page = response.read().decode('cp1251')
            if total == -1:
                total = int(re.search(r'</span>Найдено\s+?(\d+)\s+?раздач</td>', page)[1])
            current += self.draw(page)

        logging.debug("--- {} seconds ---".format(time.time() - start_time))
        logging.info("Found torrents: {}".format(total))

    def search(self, what, cat='all'):
        if self.blocked:
            return
        query = '{}/browse.php?s={}&c={}'.format(self.url, what.replace(" ", "+"),
                                                 self.supported_categories[cat])

        # make first request (maybe it enough)
        total = self.searching(query, True)
        # do async requests
        if total > 50:
            tasks = []
            for x in range(1, math.ceil(total / 50)):
                task = threading.Thread(target=self.searching, args=(query + "&page={}".format(x),))
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
    # f = open("result.html", "r")
    kinozal_se = kinozal()
    # kinozal_se.draw(f.read())
    kinozal_se.search('doctor')
    print("--- %s seconds ---" % (time.time() - start_time))
