[![Python 3.7+](https://img.shields.io/badge/python-%3E%3D%20v3.7-blue)](https://www.python.org/downloads/release/python-370/)
# qBittorrent plugins

## Rutracker.org ![v1.7](https://img.shields.io/badge/v1.7-blue)
Biggest russian torrent tracker.

## Rutor.org ![v1.5](https://img.shields.io/badge/v1.5-blue)
Popular free russian torrent tracker.

## Kinozal.tv ![v2.9](https://img.shields.io/badge/v2.9-blue)
Russian torrent tracker mostly directed on movies, but have other categories.

The site has a restriction on downloading torrent files (10 by default or so), so I added the ability to open the magnet link instead the file.
You can turn off the magnet link: in `kinozal.json` switch `"magnet": true` to `"magnet": false`

## NNM-Club.me ![v2.9](https://img.shields.io/badge/v2.9-blue)
One of biggest russian torrent tracker.

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
        "https": "" <- ex. "127.0.0.1:3128"
    },
    "magnet": false, <- switching magnet download (true/false)
    "ua": "Mozilla/5.0 (X11; Linux i686; rv:38.0) Gecko/20100101 Firefox/38.0 " <- browser User-Agent
}
```
_*make sure that your proxy work with right protocol_

**For update just reinstall `*.py` file.**

## Troubleshooting
All errors will appear directly in qBittorrent as searching result.
* torrent tracker return 403 error:
  - Some sites, sometimes, enable protection like CloudFlare, that required JavaScript. Vanilla Python has no implementation of JavaScript, it means that search engine will be return 403 error. 
