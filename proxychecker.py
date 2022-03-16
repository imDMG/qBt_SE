import asyncio
import functools
import time
import threading
from concurrent.futures.thread import ThreadPoolExecutor
from urllib.request import build_opener, ProxyHandler

HOST = "http://rutor.info"
SCHEME = HOST[:HOST.rfind("://")]
PROXY_FILE = "proxylist.txt"  # one address per line


async def is_good_proxy_aio(proxy: str) -> bool:
    try:
        await asyncio.sleep(.1)
        opener = build_opener(ProxyHandler({f"{SCHEME}": proxy}))
        opener.addheaders = [("User-agent", "Mozilla/5.0")]
        _part = functools.partial(opener.open, HOST, timeout=3)
        # res = await loop.run_in_executor(None, _part)
        if not _part().geturl().startswith(HOST):
            raise Exception()
        print(proxy)
        return True
    except OSError:
        return False


async def run_aio(proxies):
    await asyncio.gather(*[is_good_proxy(proxy) for proxy in proxies])


def run_thread(proxies: list) -> None:
    tasks = []
    for proxy in proxies:
        task = threading.Thread(target=is_good_proxy, args=(proxy,))
        task.start()
        tasks.append(task)
    for t in tasks:
        t.join()


def run_pool(proxies: list) -> None:
    with ThreadPoolExecutor(len(proxies)) as executor:
        executor.map(is_good_proxy, proxies, timeout=3)


def is_good_proxy(proxy: str) -> bool:
    try:
        opener = build_opener(ProxyHandler({f"{SCHEME}": proxy}))
        opener.addheaders = [("User-agent", "Mozilla/5.0")]
        with opener.open(HOST, timeout=3) as r:
            if not r.geturl().startswith(HOST):
                raise Exception()
    except OSError:
        return False
    else:
        print(proxy)
        return True


def main():
    t0 = time.time()

    if PROXY_FILE.startswith("http"):
        opener = build_opener()
        with opener.open(PROXY_FILE) as r:
            proxy_list = [x.rstrip().decode("utf-8") for x in r]
    else:
        with open(PROXY_FILE) as f:
            proxy_list = [x.rstrip() for x in f]

    print("Working proxies:")
    # run_thread(proxy_list)
    run_pool(proxy_list)
    # asyncio.run(run_aio(proxy_list))
    print(time.time() - t0)


if __name__ == '__main__':
    main()
