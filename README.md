# qBittorrent plugins

## Kinozal.tv
Russian torrent tracker mostly directed on movies, but have other categories

## NNM-Club.me
One of biggest russian torrent tracker

## Installation
According of the name of search plugin:
* Edit `*.json` file by replacing `USERNAME` and `PASSWORD` with your torrent tracker username and password.
* If tracker is blocked in your country, in same file:
  * find `"proxy": false` and switch in `true` (`"proxy": true`)
  * add proxy links working for you in `proxies` (`{'http': 'proxy.example.org:8080'}`) 
  * *make sure that your proxy work with right protocol*
* Move `*.json` and `*.png` to qBittorrent search engines directory:
  * Windows: `%localappdata%\qBittorrent\nova3\engines\`
  * Linux: `~/.local/share/data/qBittorrent/nova3/engines/`
  * OS X: `~/Library/Application Support/qBittorrent/nova3/engines/`
* Then follow [official tutorial](https://github.com/qbittorrent/search-plugins/wiki/Install-search-plugins).
