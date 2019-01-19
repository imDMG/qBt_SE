# VERSION: 1.0
# AUTHORS: imDMG

# NoNaMe-Club search engine plugin for qBittorrent

import tempfile
import os
import logging
import json
import time

from urllib.request import build_opener, HTTPCookieProcessor, ProxyHandler
from urllib.parse import urlencode  # , parse_qs
from urllib.error import URLError, HTTPError
from http.cookiejar import Cookie, CookieJar
from html.parser import HTMLParser
from novaprinter import prettyPrinter

# setup logging into qBittorrent/logs
logging.basicConfig(level=logging.DEBUG,
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
            config = json.load(f)
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

        # add proxy handler if needed
        if self.config['proxy'] and any(self.config['proxies'].keys()):
            self.session.add_handler(ProxyHandler(self.config['proxies']))

        # change user-agent
        self.session.addheaders.pop()
        self.session.addheaders.append(('User-Agent', self.config['ua']))

        response = self._catch_error_request(self.url + 'login.php')
        parser = self.WorstParser(self.url, True)
        parser.feed(response.read().decode('cp1251'))
        parser.close()

        form_data = {"username": self.config['username'],
                     "password": self.config['password'],
                     "autologin": "on",
                     "code": parser.login_code,
                     "login": "Вход"}
        # so we first encode keys to cp1251 then do default decode whole string
        data_encoded = urlencode({k: v.encode('cp1251') for k, v in form_data.items()}).encode()

        self._catch_error_request(self.url + 'login.php', data_encoded)

        if 'phpbb2mysql_4_sid' not in [cookie.name for cookie in cj]:
            logging.warning("we not authorized, please check your credentials")
        else:
            logging.info('We successfully authorized')

    class WorstParser(HTMLParser):
        def __init__(self, url='', login=False):
            HTMLParser.__init__(self)
            self.url = url
            self.login = login
            self.torrent = {'link': '',
                            'name': '',
                            'size': '',
                            'seeds': '',
                            'leech': '',
                            'desc_link': '', }

            self.login_code = None

            # we need a page markup to know when stop and collect data,
            # because available methods, in this class, do not communicate each other
            # as a result, we make markup to transfer information
            # from one method to another, along a chain
            #
            # markup on result table
            self.result_table = False  # table with results is found
            self.torrent_row = False  # found torrent row for collect data
            self.index_td = 0  # td counter in torrent row
            self.write = None  # trigger to detecting when to collect data

            # markup pagination
            self.paginator = False  # found more pages in result
            self.pages = 0  # page counter

            self.search_id = 0
            self.found_torrents = 0

        def handle_starttag(self, tag, attrs):
            # login
            if self.login and tag == 'input':
                tmp = dict(attrs)
                if tmp.get('name') == 'code':
                    self.login_code = tmp['value']
                    return

            # search result table by class tablesorter
            if tag == 'table':
                for name, value in attrs:
                    if name == 'class' and 'tablesorter' in value:
                        self.result_table = True

            # search for torrent row by class prow
            if self.result_table and tag == 'tr':
                for name, value in attrs:
                    if name == 'class' and 'prow' in value:
                        self.torrent_row = True

            # count td for find right td
            if self.torrent_row and tag == 'td':
                if self.index_td == 5:
                    self.write = "size"
                elif self.index_td == 7:
                    self.write = "seeds"
                elif self.index_td == 8:
                    self.write = "leech"

                self.index_td += 1

            # search for torrent link by classes r0 or r1
            if self.torrent_row and tag == 'a':
                if self.index_td == 3:
                    self.torrent['desc_link'] = self.url + attrs[1][1]
                    self.write = "name"

                if self.index_td == 5:
                    self.torrent['link'] = self.url + attrs[0][1]

            # search for right div with class paginator
            if self.found_torrents == 50 and tag == 'span':
                for name, value in attrs:
                    if name == 'class' and value == 'nav':
                        self.paginator = True

            # search for block with page numbers
            if self.paginator and tag == 'a':
                # if not self.pages:
                    # parsing for search_id
                    # self.search_id = parse_qs(attrs[0][1].split('?')[1])['search_id']
                self.pages += 1

        def handle_endtag(self, tag):
            # detecting that torrent row is closed and print all collected data
            if self.torrent_row and tag == 'tr':
                self.torrent["engine_url"] = self.url
                logging.debug('torrent row: ' + str(self.torrent))
                prettyPrinter(self.torrent)
                self.torrent = {key: '' for key in self.torrent}
                self.index_td = 0
                self.torrent_row = False
                self.found_torrents += 1

            # detecting that table with result is close
            if self.result_table and tag == 'table':
                self.result_table = False

            # detecting that we found all pagination
            if self.paginator and tag == 'span':
                self.paginator = False

        def handle_data(self, data: str):
            # detecting that we need write data at this moment
            if self.write and self.result_table:
                if data.startswith('<b>'):
                    data = data[3:-5]
                if self.index_td == 5:
                    data = data.split('</u>')[1].strip()
                self.torrent[self.write] = data.strip()
                self.write = None

        def error(self, message):
            pass

    def download_torrent(self, url):
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

    def search(self, what, cat='all'):
        c = self.supported_categories[cat]
        query = '{}tracker.php?nm={}&{}'.format(self.url, what.replace(" ", "+"), "f=-1" if c == '-1' else "c=" + c)
        response = self._catch_error_request(query)
        parser = self.WorstParser(self.url)
        parser.feed(response.read().decode('cp1251'))
        parser.close()

        # if first request return that we have pages, we do cycle
        if parser.pages:
            for x in range(1, parser.pages):
                response = self._catch_error_request('{}&start={}'.format(query,      # &search_id=
                                                                                      # parser.search_id,
                                                                                      parser.found_torrents,
                                                                                      self.supported_categories[cat]))
                parser.feed(response.read().decode('cp1251'))
                parser.close()

        logging.info("Found torrents: %s" % parser.found_torrents)

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

        return response


if __name__ == "__main__":
    nnmclub_se = nnmclub()
    nnmclub_se.search('supernatural')
    print("--- %s seconds ---" % (time.time() - start_time))
