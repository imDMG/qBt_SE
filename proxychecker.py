import asyncio
import functools
import time
import threading
from concurrent.futures.thread import ThreadPoolExecutor
from urllib.request import build_opener, ProxyHandler

HOST = "https://rutracker.org/forum/"
SCHEME = HOST[:HOST.rfind("://")]
PROXY_FILE = "proxylist1.txt"  # one address per line


async def is_good_proxy_aio(loop, proxy: str) -> bool:
    try:
        opener = build_opener(ProxyHandler({f"{SCHEME}": proxy}))
        opener.addheaders = [("User-agent", "Mozilla/5.0")]
        _part = functools.partial(opener.open, HOST, timeout=3)
        res = await loop.run_in_executor(None, _part)
        if not res.geturl().startswith(HOST):
            raise Exception()
        print(proxy)
        return True
    except Exception as e:
        # print(e)
        return False


async def run_aio(proxies):
    loop = asyncio.get_event_loop()
    for proxy in proxies:
        await is_good_proxy_aio(loop, proxy)


def run_thread(proxies):
    tasks = []
    for proxy in proxies:
        task = threading.Thread(target=is_good_proxy, args=(proxy,))
        task.start()
        tasks.append(task)
    for t in tasks:
        t.join()


def run_pool(proxies):
    with ThreadPoolExecutor(len(proxies)) as executor:
        executor.map(is_good_proxy, proxies, timeout=30)


def is_good_proxy(proxy):
    try:
        opener = build_opener(ProxyHandler({f"{SCHEME}": proxy}))
        opener.addheaders = [("User-agent", "Mozilla/5.0")]
        req = opener.open(HOST, timeout=3)
        if not req.geturl().startswith(HOST):
            raise Exception()
    except Exception as e:
        # print(e)
        return False
    else:
        print(proxy)
        return True


def main():
    t0 = time.time()
    with open(PROXY_FILE) as f:
        proxy_list = [x.rstrip() for x in f]

    print("Working proxies:")
    # run_thread(proxy_list)
    run_pool(proxy_list)
    # asyncio.run(run_aio(proxy_list))
    print(time.time() - t0)


if __name__ == '__main__':
    main()
