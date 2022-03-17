[![Python 3.7+](https://img.shields.io/badge/python-%3E%3D%20v3.7-blue)](https://www.python.org/downloads/release/python-370/)
# qBittorrent plugins

## Rutracker.org ![v1.5](https://img.shields.io/badge/v1.5-blue)
Biggest russian torrent tracker.

## Rutor.org ![v1.3](https://img.shields.io/badge/v1.3-blue)
Popular free russian torrent tracker.

## Kinozal.tv ![v2.7](https://img.shields.io/badge/v2.7-blue)
Russian torrent tracker mostly directed on movies, but have other categories.

The site has a restriction on downloading torrent files (10 by default or so), so I added the ability to open the magnet link instead the file.
You can turn off the magnet link: in `kinozal.json` switch `"magnet": true` to `"magnet": false`

## NNM-Club.me ![v2.8](https://img.shields.io/badge/v2.8-blue)
One of biggest russian torrent tracker.

## Installation
**For fresh installation.**
According of the name of search plugin:
* Save `*.py` file on your computer
* Then open `*.py` file and find from above the section with `config = { ... }`. Replace `USERNAME` and `PASSWORD` with your torrent tracker username and password. If tracker is blocked in your country, in same section:
  * find `"proxy": False` and switch in `True` (`"proxy": True`)
  * add proxy links working for you in `proxies` (`{"http": "proxy.example.org:8080"}`)
  * *make sure that your proxy work with right protocol*
* Then follow [official tutorial](https://github.com/qbittorrent/search-plugins/wiki/Install-search-plugins).
* _After installation you can change your settings with `*.json` file which will be created automatically in:_
  * Windows: `%localappdata%\qBittorrent\nova3\engines`
  * Linux: `~/.local/share/qBittorrent/nova3/engines`
  * OS X: `~/Library/Application Support/qBittorrent/nova3/engines`

**For update just reinstall `*.py` file.**

## Troubleshooting
All errors will appear directly in qBittorrent as searching result.
