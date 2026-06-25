<h1 align="center">OpenSteamTool-Desktop</h1>

<p align="center">
  A Steam game library management desktop tool powered by <a href="https://github.com/OpenSteam001/OpenSteamTool">OpenSteamTool</a><br>
  Windows 11 Fluent Design GUI for all-in-one game unlocking and management
</p>

<p align="center">
  <img src="https://img.shields.io/badge/platform-Windows%2010%20%7C%2011-blue?logo=windows" alt="Platform">
  <img src="https://img.shields.io/badge/Steam-Required-1b2838?logo=steam" alt="Steam Required">
  <img src="https://img.shields.io/badge/GUI-Fluent%20Design-0078D4?logo=microsoft" alt="GUI">
  <img src="https://img.shields.io/github/v/release/yong0512/OpenSteamToolDesktop?color=green" alt="Release">
  <img src="https://img.shields.io/github/downloads/yong0512/OpenSteamToolDesktop/total" alt="Downloads">
</p>

<p align="center">
  <a href="README.md">中文</a>
</p>

---

> ⚠️ **Windows 10 / Windows 11 64-bit only.** Steam client must be installed and logged in. macOS / Linux are not supported.

---

## Download

Go to the [Releases](https://github.com/yong0512/OpenSteamToolDesktop/releases) page to download the latest version.

---

## Table of Contents

- [Features](#features)
- [OpenSteamTool Core Capabilities](#opensteamtool-core-capabilities)
- [Dashboard Overview](#dashboard-overview)
- [Usage Guide](#usage-guide)
- [In-Library Result](#in-library-result)
- [Antivirus Notice](#antivirus-notice)
- [FAQ](#faq)
- [Developer Guide](#developer-guide)
- [Disclaimer](#disclaimer)
- [License](#license)

---

## Features

| Feature                   | Description                                                                                         |
| ------------------------- | --------------------------------------------------------------------------------------------------- |
| **Injection Manager**     | One-click deploy/remove OpenSteamTool DLLs with triple-layer verification, plus quick Steam restart |
| **Game Search & Add**     | Search Steam games by AppID or English name; auto-fetch metadata and generate library config        |
| **Full DLC Unlock**       | Automatically detects all DLCs associated with a game and unlocks them in one click                 |
| **Depot Decryption Keys** | Automatically retrieves decryption keys for each encrypted Depot to enable normal downloads         |
| **Game Library Manager**  | Card-style browsing with sorting, search, and right-click actions (view/copy/remove)                |
| **Auto Update**           | Checks GitHub Releases on startup and guides you to the latest version                              |

---

## OpenSteamTool Core Capabilities

OpenSteamTool is a C++ engine that injects into the Steam client via DLL. This tool provides a graphical interface for it. Once injected, you gain:

| Capability               | Description                                                                    |
| ------------------------ | ------------------------------------------------------------------------------ |
| **Game Unlocking**       | Unlock games and all DLCs you don't own                                        |
| **Depot Decryption**     | Auto-inject depot decryption keys for normal file downloads                    |
| **Manifest Download**    | Auto-download depot manifests with version locking to prevent unwanted updates |
| **Access Token**         | Support for protected games/DLCs that require access tokens                    |
| **Stats & Achievements** | Enable Steam stats and achievements for unowned games                          |
| **Hot Reload**           | Lua config changes take effect instantly without restarting Steam              |

---

## Dashboard Overview

Automatically detects Steam installation status, injection status, and library overview on startup:

![Dashboard](assets/2026-06-03-13-38-03-image.png)

---

## Usage Guide

### Step 1: Inject into Steam

1. Go to the **Injection Manager** page
2. Click the **Inject Steam** button
3. Restart the Steam client to take effect

> If Steam is currently running, the app will prompt you to close it first.

![Injection Manager](assets/2026-06-03-13-38-34-image.png)

### Step 2: Search and Add Games

1. Go to the **Search & Add** page
2. Enter a game **AppID** (e.g., `730` = CS2) or **English game name**
3. Click **Add to Library** — the tool automatically fetches metadata, DLC lists, and decryption keys, then generates the config

![Search & Add](assets/2026-06-03-13-38-55-image.png)

### Step 3: Manage Your Game Library

1. Go to the **Game Library** page to view all added games
2. Sort by name/AppID or search to filter
3. Right-click a game card to: copy AppID, copy game name, view on Steam, or remove from library

![Game Library](assets/2026-06-03-13-39-06-image.png)

---

## In-Library Result

Once added, the game appears directly in your Steam library:

![In-Library](assets/2026-06-03-13-49-34-image.png)

---

## Antivirus Notice

If Windows Security flags the program as a threat (DLL injection may trigger false positives), follow these steps:

1. Open **Windows Security**

![Windows Security](assets/2026-06-03-14-16-28-image.png)

2. Go to **Virus & threat protection** → **Manage settings**

![Manage Settings](assets/2026-06-03-14-27-30-image.png)

3. Turn off **Real-time protection**. Windows Security is prone to false positives with DLL injection tools — disabling it prevents the program from being blocked.

![Real-time protection](assets/2026-06-03-14-27-05-image.png)

---

## FAQ

### Steam shows no change after injection?

Make sure you have **restarted Steam**. DLL injection only takes effect at Steam startup. Use the **Verify Injection** button on the Injection Manager page to check the status.

### Game shows "Content still encrypted" after adding?

This occurs when some Depots are missing decryption keys. The tool automatically fetches them — if the issue persists, check your network connection.

### How do I uninstall the injection?

Click **Remove Injection** on the Injection Manager page, then restart Steam. You can also manually delete the three DLL files from your Steam root directory.

---

## Developer Guide

This is an open-source project — contributions and debugging are welcome. Follow the steps below to set up a local development environment.

### Prerequisites

| Requirement | Version |
|-------------|---------|
| OS | Windows 10 / 11 (64-bit) |
| Python | **3.10+** (3.12 or 3.13 recommended) |
| Steam Client | Installed and logged in |
| Git | Any version |

### 1. Clone the Repository

```bash
git clone https://github.com/yong0512/OpenSteamToolDesktop.git
cd OpenSteamToolDesktop
```

### 2. Create a Virtual Environment

```bash
# Create .venv in the project root
python -m venv .venv

# Activate it
.venv\Scripts\activate
```

> The command prompt prefix will show `(.venv)` once activated.

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

Key dependencies:

| Package | Purpose |
|---------|---------|
| `PyQt6` | GUI framework |
| `PyQt6-Fluent-Widgets` | Windows 11 Fluent Design component library |
| `httpx` | HTTP client (API requests, cover downloads) |
| `requests` | Fallback HTTP client |
| `pytest` | Unit testing |

### 4. Run & Debug

```bash
# Launch the app
python main.py
```

On startup, the app automatically:
- Detects the Steam installation path (via registry)
- Checks and downloads the required DLL (if missing)
- Checks for app updates
- Loads the game library

**Debugging tips:**

- Logs: `~/.OpenSteamToolDesktop/logs/main.log`
- Config: `~/.OpenSteamToolDesktop/config.json`
- DLL cache: `~/.OpenSteamToolDesktop/DLL/`
- Lua configs: `~/.OpenSteamToolDesktop/config/lua/`

### 5. IDE Debugging

<details>
<summary><b>VS Code</b></summary>

1. Install the [Python extension](https://marketplace.visualstudio.com/items?itemName=ms-python.python)
2. Open the project root folder
3. Select interpreter: `Ctrl+Shift+P` → `Python: Select Interpreter` → choose the `.venv` Python
4. Press `F5` to debug, or add this to `launch.json`:

```json
{
    "name": "OpenSteamToolDesktop",
    "type": "python",
    "request": "launch",
    "program": "${workspaceFolder}/main.py",
    "console": "integratedTerminal",
    "justMyCode": false
}
```

</details>

<details>
<summary><b>PyCharm</b></summary>

1. `File → Open` the project root directory
2. `File → Settings → Project → Python Interpreter` → select `.venv\Scripts\python.exe`
3. Right-click `main.py` → `Debug 'main'` to set breakpoints and debug

</details>

### 6. Run Tests

```bash
# Run all tests
pytest

# Run a single test file
pytest tests/test_game_manager.py

# Verbose output
pytest -v
```

### 7. Project Structure

```
OpenSteamToolDesktop/
├── main.py                  # Application entry point
├── config.py                # Global config constants (URLs, colors, HTTP, etc.)
├── requirements.txt         # Runtime dependencies
├── build_exe.py             # Build script (PyInstaller / Nuitka)
├── OpenSteamToolDesktop.spec # PyInstaller spec
├── core/                    # Core business logic
│   ├── steam_bridge.py      #   Steam bridge (DLL management, injection)
│   ├── game_manager.py      #   Lua game config generation & management
│   ├── metadata_fetcher.py  #   Steam metadata fetching
│   ├── dll_manager.py       #   DLL download & version management
│   ├── dll_injector.py      #   DLL injection & verification
│   ├── version_checker.py   #   App version checking
│   └── ...
├── gui/                     # UI layer
│   ├── main_window.py       #   Main window
│   ├── home_page.py         #   Dashboard page
│   ├── search_page.py       #   Search & add page
│   ├── library_page.py      #   Game library page
│   ├── inject_page.py       #   Injection manager page
│   ├── accelerate_page.py   #   Network acceleration page
│   └── widgets/             #   Custom widgets
├── utils/                   # Utility modules
│   ├── http_client.py       #   Unified HTTP client
│   ├── async_worker.py      #   QThread async task wrapper
│   ├── logger.py            #   Logging module
│   └── ...
├── resources/               # Static resources
│   └── fallback_dlls/       #   Built-in fallback DLLs
├── assets/                  # Screenshots, icons
└── tests/                   # Unit tests
```

### 8. Build & Package

```bash
# Install build tool
pip install pyinstaller

# PyInstaller build (default, produces dist/ + Zip)
python build_exe.py

# Nuitka build (C++ compilation, stronger code protection)
python build_exe.py --nuitka

# Clean build artifacts only
python build_exe.py --clean

# Build without generating Zip
python build_exe.py --no-zip
```

Build output goes to `dist/`, and a `OpenSteamToolDesktop-{version}.zip` is generated in the project root.

---

## Disclaimer

This project is for **educational and research purposes only**. Please adhere to the following:

- This tool does not provide game download functionality
- Respect the work of game developers and support genuine purchases
- Any consequences arising from the use of this tool are borne solely by the user
- Commercial use of this tool is strictly prohibited

---

## License

This project is powered by the [OpenSteamTool](https://github.com/OpenSteam001/OpenSteamTool) engine.

---

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=yong0512/OpenSteamToolDesktop&type=Date)](https://star-history.com/#yong0512/OpenSteamToolDesktop&Date)

---

<p align="center">
  <sub>Made with ❤️ for the Steam community</sub>
</p>
