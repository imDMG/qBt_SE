# qBittorrent plugins

## Kinozal.tv
Russian torrent tracker mostly directed on movies, but have other categories.

The site has a restriction on downloading torrent files (10 by default or so), so I added the ability to open the magnet link instead the file.
You can turn off the magnet link: in `kinozal.json` switch `"magnet": true` to `"magnet": false`

## NNM-Club.me
One of biggest russian torrent tracker.

## Installation
**For fresh installation.**
According of the name of search plugin:
* Copy the plugin (`*.py`) to the directory according to your operating system:
  * Windows: `%localappdata%\qBittorrent\nova3\engines\`
  * Linux: `~/.local/share/data/qBittorrent/nova3/engines/`
  * OS X: `~/Library/Application Support/qBittorrent/nova3/engines/`
* Then open copied `*.py` file and find from above the section with `config = { ... }` and replace `USERNAME` and `PASSWORD` with your torrent tracker username and password.
* If tracker is blocked in your country, in same file:
  * find `"proxy": false` and switch in `true` (`"proxy": true`)
  * add proxy links working for you in `proxies` (`{"http": "proxy.example.org:8080"}`)
  * *make sure that your proxy work with right protocol*
* **_Optionally_**: move `*.ico` to same directory.
* Then follow [official tutorial](https://github.com/qbittorrent/search-plugins/wiki/Install-search-plugins).
* _After installation you can change your settings with `*.json` file which will be created automatically in same directory._

**For update just reinstall `*.py` file.**

## Troubleshooting
:warning: If the plugin is't installed with a message about the incompatibility of the plugin:
 * if torrent tracker is't avalaible for you in web - configure the proxy in `*.json` file

All other errors and warnings you can see in log file `*.log`:
  * Windows: `%localappdata%\qBittorrent\logs\`
  * Linux: `~/.local/share/data/qBittorrent/logs/`
  * OS X: `~/Library/Application Support/qBittorrent/logs/`
