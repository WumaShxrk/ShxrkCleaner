# � ShxrkCleaner

Windows system cleaner — fast, minimal, 27 targets, CLI-first.

## Quick Start

```cmd
cd "C:\Users\WumaShxrk\Downloads\Clean Tools"
python run.py
```

```cmd
shxrkcleaner.bat --quick
shxrkcleaner.bat --deep -y
```

### Install as CLI command

```cmd
pip install -e .
shxrkcleaner --deep
```

## Usage

```cmd
shxrkcleaner              # Interactive menu
shxrkcleaner --quick      # Quick clean (6 targets)
shxrkcleaner --deep       # Deep clean (all 27 targets)
shxrkcleaner --deep -y    # Skip confirmation
shxrkcleaner --browser --discord --steam   # Individual targets
```

## All 27 Targets

| Flag | Target |
|---|---|
| `--temp` | Windows & User temp files |
| `--prefetch` | Prefetch data |
| `--recycle` | Recycle Bin |
| `--junk` | Junk / log / cache files (.tmp, .log, .dmp, .bak, .etl) |
| `--browser` | Browser cache (Chrome, Edge, Brave, Opera, Opera GX) |
| `--dns` | DNS resolver cache flush |
| `--winupdate` | Windows Update download cache |
| `--discord` | Discord / Canary / PTB cache |
| `--spotify` | Spotify cache (desktop + UWP) |
| `--steam` | Steam shader, depot, http cache, logs |
| `--eventlogs` | Windows Event Logs |
| `--fontcache` | Font cache + FNTCACHE.DAT |
| `--nvidia` | NVIDIA DX/GL/Compute/NV cache |
| `--teams` | Microsoft Teams cache (classic + new) |
| `--pip` | pip package cache |
| `--npm` | npm package cache |
| `--thumbnails` | Windows thumbnail & icon cache |
| `--installer` | Windows Installer $PatchCache$ |
| `--recent` | Recent files & jump lists |
| `--crashdumps` | Minidump, MEMORY.DMP, LiveKernelReports |
| `--vscode` | VS Code / Insiders cache |
| `--java` | Java / Gradle / Maven cache |
| `--dxcache` | DirectX / AMD / Intel shader cache |
| `--delivery` | Delivery Optimization cache |
| `--telegram` | Telegram Desktop cache |
| `--wer` | Windows Error Reports |

## Build as .exe

```cmd
pip install pyinstaller
pyinstaller --onefile --name shxrkcleaner --icon=img/logo.ico run.py
```

Output: `dist/shxrkcleaner.exe`

## Requirements

- Windows 10/11
- Python 3.8+
- Run as Administrator for full capability

## Safety

- Protected system files are never touched
- Permission errors are silently skipped
- Confirmation prompt before any destructive action
- Close browsers/apps before cleaning their cache for best results
