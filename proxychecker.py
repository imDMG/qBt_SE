from concurrent.futures.thread import ThreadPoolExecutor
from urllib.request import build_opener, ProxyHandler

HOST = "http://kinozal.tv/"
SCHEME = HOST[:4]
PROXY_FILE = "proxylist.txt"  # one address per line


def print_good_proxy(proxy):
    try:
        opener = build_opener(ProxyHandler({f"{SCHEME}": proxy}))
        opener.addheaders = [("User-agent", "Mozilla/5.0")]
        req = opener.open(HOST, timeout=30)
        if not req.geturl().startswith(HOST):
            raise Exception()
    except Exception as e:
        return e

    print(proxy)


def main():
    with open(PROXY_FILE) as f:
        proxy_list = [x.rstrip() for x in f]

    print("Working proxies:")
    with ThreadPoolExecutor(len(proxy_list)) as executor:
        executor.map(print_good_proxy, proxy_list, timeout=30)


if __name__ == '__main__':
    main()
