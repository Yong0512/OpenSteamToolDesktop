from __future__ import annotations

import os
from pathlib import Path

APP_NAME: str = "OpenSteamToolDesktop"
APP_VERSION: str = "1.0.0"

CONFIG_DIR: str = str(Path.home() / f".{APP_NAME}")
os.makedirs(CONFIG_DIR, exist_ok=True)
CONFIG_FILE: str = os.path.join(CONFIG_DIR, "config.json")

GITHUB_REPO_OWNER: str = "yong0512"
GITHUB_REPO_NAME: str = "OpenSteamToolDesktop"
GITHUB_REPO_URL: str = f"https://github.com/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}"
GITHUB_RELEASES_URL: str = f"{GITHUB_REPO_URL}/releases"
GITHUB_ISSUES_URL: str = f"{GITHUB_REPO_URL}/issues/new"
GITHUB_API_LATEST_RELEASE: str = f"https://api.github.com/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/releases/latest"
GITHUB_API_LATEST: str = GITHUB_API_LATEST_RELEASE

STEAM_DOWNLOAD_URL: str = "https://store.steampowered.com/about/"

STEAM_STORE_API: str = "https://store.steampowered.com/api/appdetails"
STEAM_STORE_SEARCH_API: str = "https://store.steampowered.com/api/storesearch"
STEAM_STORE_SEARCH_RESULTS: str = "https://store.steampowered.com/search/results/"
STEAM_CDN_BASE: str = "https://cdn.akamai.steamstatic.com/steam/apps"
STEAM_CDN_API: str = (
    "https://api.steampowered.com/IContentServerDirectoryService/"
    "GetServersForSteamPipe/v1/?cell_id=33&max_servers=30"
)
STEAMCMD_API: str = "https://api.steamcmd.net/v1/info"
SUDAMA_API_DEPOT_KEYS: str = "https://api.sudama.app/v1/depotkeys"
TOKEN_API: str = "https://api.993499094.xyz/appaccesstokens.json"
DEPOT_KEYS_API_ALT: str = "https://api.993499094.xyz/depotkeys.json"

DEFAULT_THEME_MODE: str = "dark"
DEFAULT_THEME_COLOR: str = "#0078d4"
COLOR_PRIMARY: str = DEFAULT_THEME_COLOR

DEFAULT_LANGUAGE: str = "zh_CN"

LOG_LEVEL: str = "INFO"
CRASH_LOG_ENABLED: bool = False

HTTP_DEFAULT_TIMEOUT: float = 15.0
HTTP_COVER_TIMEOUT: float = 5.0
HTTP_MAX_RETRIES: int = 2

STEAM_USER_AGENT: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/91.0.4472.124 Safari/537.36"
)

LUA_DIR_RELATIVE: str = "config/lua"

COLOR_SUCCESS: str = "#52c41a"
COLOR_ERROR: str = "#f5222d"
COLOR_WARNING: str = "#ff9800"

TEXT_COLOR: str = "#FFFFFF"

FALLBACK_CDN_HOSTS: list[str] = [
    "cache1-steamcontent.com",
    "cache2-steamcontent.com",
    "cache3-steamcontent.com",
    "cache4-steamcontent.com",
    "cache5-steamcontent.com",
    "cache6-steamcontent.com",
    "cache7-steamcontent.com",
    "cache8-steamcontent.com",
    "cache9-steamcontent.com",
    "cache10-steamcontent.com",
]
