[![Python 3.7+](https://img.shields.io/badge/python-%3E%3D%20v3.7-blue)](https://www.python.org/downloads/release/python-370/)
# qBittorrent plugins

## Rutracker.org ![v1.16](https://img.shields.io/badge/v1.16-blue)
Biggest russian torrent tracker.

## Rutor.org ![v1.16](https://img.shields.io/badge/v1.16-blue)
Popular free russian torrent tracker. http://rutor.info/ and http://rutor.is/ - actual domains at this time.

## Kinozal.tv ![v2.19](https://img.shields.io/badge/v2.19-blue)
Russian torrent tracker mostly directed on movies, but have other categories.

The site has a restriction on downloading torrent files (10 by default or so), so I added the ability to open the magnet link instead the file.
You can turn off the magnet link: in `kinozal.json` switch `"magnet": true` to `"magnet": false`

## NNM-Club.me ![v2.20](https://img.shields.io/badge/v2.20-blue)
One of biggest russian torrent tracker.

_Note: the tracker is very sensitive to your proxy, if something doesn’t suit it, it turns on ddos protection and return 403 error. Use `proxychecker.py` to check your proxy_

## Installation
**For fresh installation.**
According of the name of search plugin:
* Save `*.py` file on your computer
* Then follow [official tutorial](https://github.com/qbittorrent/search-plugins/wiki/Install-search-plugins).
* _After installation you can change your settings with `*.json` file which will be created automatically in:_
  * Windows: `%localappdata%\qBittorrent\nova3\engines`
  * Linux: `~/.local/share/qBittorrent/nova3/engines`
  * OS X: `~/Library/Application Support/qBittorrent/nova3/engines`
* ... or you can put `settings_gui.py` into parent folder (nova3) and after this you can double-click on `*.py` file, or `Open with... -> Python`, and you should see graphic interface of your data :)

Description of `*.json` file:
```
{
    "username": "USERNAME", <- your USERNAME of torrent tracker
    "password": "PASSWORD", <- your PASSWORD of torrent tracker
    "torrentDate": true, <- creation date of torrent in search list (true/false)
    "proxy": false, <- switchng proxy (true/false)
    "proxies": {
        "http": "", <- ex. "proxy.example.org:8080"
        "https": "" <- ex. "127.0.0.1:3128" or "socks5://127.0.0.1:9050"
    },
    "magnet": false, <- switching magnet download (true/false)
    "ua": "Mozilla/5.0 (X11; Linux i686; rv:38.0) Gecko/20100101 Firefox/38.0 " <- browser User-Agent
}
```

For **NNM-Club** there is no `password` field anymore. You must obtain a `cookie` from your browser dev tools:
1. Go to the site (https://nnmclub.to/)
2. Open dev tools
3. Select Network tab
4. Successfully Login
5. Find any request with *new* `cookie`, example:
   ![curl 'https://nnmclub.to/forum/index.php?sid=...' \
   -H 'cookie: phpbb2mysql_4_t=a%3A24...............8' \
   -H 'user-agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'](https://i.imgur.com/U8j1pvi.png)
6. Select it fully (but without `cookie: `) and copy
7. Paste into the above JSON file [nnmclub.json](/home/username/.local/share/qBittorrent/nova3/engines/nnmclub.json) in
   a new field `cookie`
   ```JSON
   {
     "username": "USERNAME",
     "cookie": "phpbb2mysql_4_sid=0....; php....",
     "...rest": "fields..."
   }
   ```
_*make sure that your proxy work with right protocol_

**For update just reinstall `*.py` file.**

## Troubleshooting
All errors will appear directly in qBittorrent as a searching result. For error details right-click on a result Copy→Description page URL, then paste in your web-browser address bar.
* torrent tracker return 403 error:
  - Some sites, sometimes, enable protection like CloudFlare, that required JavaScript. Vanilla Python has no implementation of JavaScript, it means that search engine will be return 403 error.
