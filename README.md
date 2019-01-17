# qBittorrent plugins

## Kinozal.tv
Russian torrent tracker mostly directed on movies, but have other categories

## Installation
* Edit `kinozal.py` by replacing `KINOZAL_USERNAME` and `KINOZAL_PASSWORD` with your Kinozal username and password.
* If kinozal.tv is blocked in your country, in same file:
  * find `proxy = False` and switch in `True` (`proxy = True`)
  * add proxy links working for you in `proxies` (`proxies = {'http': 'proxy.example.org:8080'}`) 
  * *make sure that your proxy work with right protocol*
* Move `kinozal.py` and `kinozal.png` to qBittorrent search engines directory:
  * Windows: `%localappdata%\qBittorrent\nova3\engines\`
  * Linux: `~/.local/share/data/qBittorrent/nova3/engines/`
  * OS X: `~/Library/Application Support/qBittorrent/nova3/engines/`
* Kinozal search engine should now be available in qBittorrent.
