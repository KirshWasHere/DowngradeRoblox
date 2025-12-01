# Roblox Downgrader

Download and install any Roblox version with protocol handler support.

## Requirements

- Python 3.7+
- Windows

## Installation

Run `run.bat` or `python Downloader.py`

## Features

- Download latest/previous versions
- Custom version by hash
- Auto-install to Roblox directory
- Protocol handler registration (launch from web)
- Delete all versions
- Launch Roblox directly

## Menu

```
1. Install Roblox
2. Delete All Versions
3. Register Protocol Handlers
4. Remove Protocol Handlers
5. Launch Roblox
6. Exit
```

## How It Works

1. Fetches version from Roblox [DeployHistory.txt](https://setup.rbxcdn.com/DeployHistory.txt)
2. Downloads manifest from Roblox CDN
3. Downloads and packages all files
4. Installs to Roblox directory
5. Registers protocol handlers for web launch

## Protocol Handlers

After registering, you can launch Roblox from:
- roblox:// links
- roblox-player:// links
- Roblox.com website

## Credits

Based on RDD by Latte Softworks: https://github.com/latte-soft/rdd

## License

MIT License
