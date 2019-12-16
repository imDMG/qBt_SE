# qBittorrent plugins

## Rutracker.org
Biggest russian torrent tracker.

## Kinozal.tv
Russian torrent tracker mostly directed on movies, but have other categories.

The site has a restriction on downloading torrent files (10 by default or so), so I added the ability to open the magnet link instead the file.
You can turn off the magnet link: in `kinozal.json` switch `"magnet": true` to `"magnet": false`

## NNM-Club.me
One of biggest russian torrent tracker.

## Installation
**For fresh installation.**
According of the name of search plugin:
* Save (`*.py`) file on your computer
* Then open `*.py` file and find from above the section with `config = { ... }`. Replace `USERNAME` and `PASSWORD` with your torrent tracker username and password. If tracker is blocked in your country, in same section:
  * find `"proxy": False` and switch in `True` (`"proxy": True`)
  * add proxy links working for you in `proxies` (`{"http": "proxy.example.org:8080"}`)
  * *make sure that your proxy work with right protocol*
* Then follow [official tutorial](https://github.com/qbittorrent/search-plugins/wiki/Install-search-plugins).
* _After installation you can change your settings with `*.json` file which will be created automatically in:_
  * Windows: `%localappdata%\qBittorrent\logs\`
  * Linux: `~/.local/share/data/qBittorrent/logs/`
  * OS X: `~/Library/Application Support/qBittorrent/logs/`_

**For update just reinstall `*.py` file.**

## Troubleshooting
All errors will appear directly in qBittorrent as searching result.
