# qBittorrent plugins

## Kinozal.tv
Russian torrent tracker mostly directed on movies, but have other categories

## Installation
* Edit `kinozal.json` by replacing `USERNAME` and `PASSWORD` with your Kinozal username and password.
* If kinozal.tv is blocked in your country, in same file:
  * find `"proxy": false` and switch in `true` (`"proxy": true`)
  * add proxy links working for you in `proxies` (`{'http': 'proxy.example.org:8080'}`) 
  * *make sure that your proxy work with right protocol*
* Move `kinozal.json` and `kinozal.png` to qBittorrent search engines directory:
  * Windows: `%localappdata%\qBittorrent\nova3\engines\`
  * Linux: `~/.local/share/data/qBittorrent/nova3/engines/`
  * OS X: `~/Library/Application Support/qBittorrent/nova3/engines/`
* Then follow [official tutorial](https://github.com/qbittorrent/search-plugins/wiki/Install-search-plugins).
