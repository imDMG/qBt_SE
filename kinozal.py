# VERSION: 2.1
# AUTHORS: imDMG [imdmgg@gmail.com]

# Kinozal.tv search engine plugin for qBittorrent

import json
import logging
import os
import re
import tempfile
import threading
import time

from urllib.request import build_opener, HTTPCookieProcessor, ProxyHandler
from urllib.parse import urlencode
from urllib.error import URLError, HTTPError
from http.cookiejar import MozillaCookieJar
from novaprinter import prettyPrinter


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

    # default config for kinozal.json
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
        "ua": "Mozilla/5.0 (X11; Linux i686; rv:38.0) Gecko/20100101 Firefox/38.0"
    }

    def __init__(self):
        # setup logging into qBittorrent/logs
        logging.basicConfig(handlers=[logging.FileHandler(self.path_to('../../logs', 'kinozal.log'), 'w', 'utf-8')],
                            level=logging.DEBUG,
                            format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                            datefmt='%m-%d %H:%M')

        try:
            # try to load user data from file
            with open(self.path_to('kinozal.json'), 'r+') as f:
                config = json.load(f)
                if "version" not in config.keys():
                    config.update({"version": 2, "torrentDate": True})
                    f.seek(0)
                    f.write(json.dumps(config, indent=4, sort_keys=False))
                    f.truncate()
                self.config = config
        except OSError as e:
            logging.error(e)
            # if file doesn't exist, we'll create it
            with open(self.path_to('kinozal.json'), 'w') as f:
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
        cookie_file = os.path.abspath(os.path.join(os.path.dirname(__file__), 'kinozal.cookie'))
        # load local cookies
        if os.path.isfile(cookie_file):
            mcj.load(cookie_file, ignore_discard=True)
            if 'uid' in [cookie.name for cookie in mcj]:
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
        self.session.add_handler(HTTPCookieProcessor(mcj))

        form_data = {"username": self.config['username'], "password": self.config['password']}
        # so we first encode keys to cp1251 then do default decode whole string
        data_encoded = urlencode({k: v.encode('cp1251') for k, v in form_data.items()}).encode()

        self._catch_error_request(self.url + '/takelogin.php', data_encoded)
        if 'uid' not in [cookie.name for cookie in mcj]:
            logging.warning("we not authorized, please check your credentials")
        else:
            mcj.save(cookie_file, ignore_discard=True, ignore_expires=True)
            logging.info('We successfully authorized')

    def draw(self, html: str):
        torrents = re.findall(r'nam"><a\s+?href="(.+?)"\s+?class="r\d">(.*?)</a>'
                              r'.+?s\'>.+?s\'>(.*?)<.+?sl_s\'>(\d+)<.+?sl_p\'>(\d+)<.+?s\'>(.*?)</td>', html, re.S)
        today, yesterday = time.strftime("%y.%m.%d"), time.strftime("%y.%m.%d", time.localtime(time.time()-86400))
        for tor in torrents:
            torrent_date = ""
            if self.config['torrentDate']:
                ct = tor[5].split()[0]
                if "сегодня" in ct:
                    torrent_date = today
                elif "вчера" in ct:
                    # yeah this is yesterday
                    torrent_date = yesterday
                else:
                    torrent_date = time.strftime("%y.%m.%d", time.strptime(ct, "%d.%m.%Y"))
                torrent_date = f'[{torrent_date}] '
            torrent = {"engine_url": self.url,
                       "desc_link": self.url + tor[0],
                       "name": torrent_date + tor[1],
                       "link": "http://dl.kinozal.tv/download.php?id=" + tor[0].split("=")[1],
                       "size": self.units_convert(tor[2]),
                       "seeds": tor[3],
                       "leech": tor[4]}

            prettyPrinter(torrent)
        del torrents
        # return len(torrents)

    def path_to(self, *file):
        return os.path.abspath(os.path.join(os.path.dirname(__file__), *file))

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
            # magnet = re.search(":\s([A-Z0-9]{40})<", res.read().decode())[1]
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

    def search(self, what, cat='all'):
        if self.blocked:
            return
        query = f'{self.url}/browse.php?s={what.replace(" ", "+")}&c={self.supported_categories[cat]}'

        # make first request (maybe it enough)
        total = self.searching(query, True)
        # do async requests
        if total > 50:
            tasks = []
            for x in range(1, -(-total//50)):
                task = threading.Thread(target=self.searching, args=(query + f"&page={x}",))
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
            logging.warning(f"{self.url} is blocked. Try proxy or another proxy")
            self.blocked = True

        return response


if __name__ == "__main__":
    # benchmark start
    start_time = time.time()
    kinozal_se = kinozal()
    kinozal_se.search('doctor')
    print("--- %s seconds ---" % (time.time() - start_time))
    # benchmark end
