import asyncio
import functools
import json
import threading
import time
from concurrent.futures.thread import ThreadPoolExecutor
from typing import TypedDict
from urllib.request import ProxyHandler, build_opener


HOST = "https://nnmclub.to/forum/viewforum.php?f=954"
SCHEME = HOST[: HOST.rfind("://")]
PROXY_FILE = "proxylist.txt"  # one address per line


class Proxifly(TypedDict):
    proxy: str
    protocol: str
    ip: str
    port: int
    https: bool
    anonymity: str
    score: int
    geolocation: dict[str, str]


def get_proxies() -> None:
    print("Loading proxies...")
    opener = build_opener()
    with opener.open(
        "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/all/data.json",
        # "https://raw.githubusercontent.com/proxifly/free-proxy-list/refs/heads/main/proxies/all/data.json",
        timeout=3,
    ) as r:
        with open("proxylist.json", "w") as f:
            f.write(r.read().decode("utf-8"))


async def is_good_proxy_aio(proxy: str) -> bool:
    try:
        await asyncio.sleep(0.1)
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


async def run_aio(proxies: list[str]) -> None:
    await asyncio.gather(*[is_good_proxy_aio(proxy) for proxy in proxies])


def run_thread(proxies: list[str]) -> None:
    tasks: list[threading.Thread] = []
    for proxy in proxies:
        task = threading.Thread(target=is_good_proxy, args=(proxy,))
        task.start()
        tasks.append(task)
    for t in tasks:
        t.join()


def run_pool(proxies: list[str]) -> None:
    with ThreadPoolExecutor(len(proxies)) as executor:
        executor.map(is_good_proxy, proxies, timeout=3)


def is_good_proxy(proxy: str) -> bool:
    try:
        opener = build_opener(ProxyHandler({f"{SCHEME}": proxy}))
        opener.addheaders = [("User-agent", "Mozilla/5.0")]
        with opener.open(HOST, timeout=3) as r:
            # print(r.getcode())
            if not r.geturl().startswith(HOST):
                raise Exception()
            print(proxy)
            return True
    except OSError:
        return False


def main():
    t0 = time.time()

    if PROXY_FILE.startswith("http"):
        opener = build_opener()
        with opener.open(PROXY_FILE) as r:
            proxy_list = [x.rstrip().decode("utf-8") for x in r]
    else:
        with open(PROXY_FILE) as f:
            if PROXY_FILE.endswith(".json"):
                proxy_dict: list[Proxifly] = json.loads(f.read())
                # filter
                proxy_list = [
                    x["proxy"] for x in proxy_dict if x["https"] is True
                ]
            else:
                proxy_list = [x.rstrip() for x in f]

    get_proxies()
    print("Working proxies:")
    # run_thread(proxy_list)
    run_pool(proxy_list)
    # asyncio.run(run_aio(proxy_list))
    print(time.time() - t0)


if __name__ == "__main__":
    main()
