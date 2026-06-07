from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx

from config import STEAM_STORE_API, STEAMCMD_API, TOKEN_API, DEPOT_KEYS_API_ALT
from core.game_manager import DepotInfo, GameMetadata
from utils.logger import setup_logger

logger = setup_logger(__name__)

class MetadataFetcher:

    def __init__(self, cache_dir: str | Path = ""):
        if cache_dir:
            self._cache_dir = Path(cache_dir)
        else:
            from utils.path_manager import PathManager
            self._cache_dir = PathManager.cache_dir()
        self._cache_dir.mkdir(parents=True, exist_ok=True)

        self._name_cache_path = self._cache_dir / "name_cache.json"
        self._token_cache_path = self._cache_dir / "token_cache.json"
        self._depotkeys_cache_path = self._cache_dir / "depotkeys_cache.json"

        self._name_cache: dict[str, str] = {}
        self._token_cache: dict[str, dict] = {}
        self._depotkeys_cache: dict[str, str] = {}
        self._sudama_all_keys: dict[str, str] = {}
        self._sudama_fetch_time: float = 0.0
        self._load_caches()

        self._http = httpx.Client(
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
            timeout=15.0,
            follow_redirects=True,
        )

    def close(self):
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def fetch_all(self, app_id: str) -> GameMetadata:
        metadata = GameMetadata(app_id=app_id)

        logger.info(f"Fetching metadata for AppID {app_id}...")

        metadata.name = self._get_cached_name(app_id)
        if metadata.name:
            logger.debug(f"  Name from cache: {metadata.name}")

        logger.debug(f"  Fetching from Steam Store API...")
        store_data = self._fetch_store_api(app_id)

        if store_data:
            if not metadata.name and "name" in store_data:
                metadata.name = store_data["name"]
                self._set_cached_name(app_id, store_data["name"])
                logger.info(f"  Game name: {metadata.name}")

            if "dlc" in store_data:
                metadata.dlc_ids = [str(d) for d in store_data["dlc"]]
                logger.debug(f"  Found {len(metadata.dlc_ids)} DLC(s) from Store API")

            if "depots" in store_data:
                metadata.depots = self._parse_depots(store_data["depots"])
                logger.debug(f"  Found {len(metadata.depots)} depot(s) from Store API")

                self._try_extract_store_keys(metadata.depots, store_data["depots"])

            if "workshop" in store_data:
                workshop_data = store_data.get("workshop", {})
                if isinstance(workshop_data, dict):
                    workshop_depot = workshop_data.get("depot", "")
                    if workshop_depot:
                        metadata.workshop_key = str(workshop_depot)
                        logger.debug(f"  Workshop depot: {metadata.workshop_key}")

        logger.debug(f"  Fetching depots from SteamCMD API...")
        steamcmd_depots = self._fetch_steamcmd_api(app_id)

        if not metadata.depots and steamcmd_depots:

            metadata.depots = steamcmd_depots
            logger.debug(f"  Using {len(metadata.depots)} depot(s) from SteamCMD API")
        elif metadata.depots and steamcmd_depots:

            store_depot_ids = {d.depot_id for d in metadata.depots}
            merged_count = 0
            for cmd_depot in steamcmd_depots:
                if cmd_depot.depot_id not in store_depot_ids:
                    metadata.depots.append(cmd_depot)
                    merged_count += 1
            if merged_count > 0:
                logger.debug(
                    f"  Merged {merged_count} additional depot(s) from SteamCMD API "
                    f"(total: {len(metadata.depots)})"
                )

            self._try_enrich_depot_keys(metadata.depots, app_id)

        logger.debug(f"  Fetching depot keys from community key database...")
        self._fetch_depot_keys_from_community(metadata)

        encrypted_count = sum(1 for d in metadata.depots if self._is_depot_encrypted(d))
        depot_missing_keys = sum(1 for d in metadata.depots if self._is_depot_encrypted(d) and not d.depot_key)
        if encrypted_count > 0:
            logger.info(
                f"  Depots: {len(metadata.depots)} total, {encrypted_count} encrypted, "
                f"{depot_missing_keys} still missing keys"
            )

        if metadata.dlc_ids:
            logger.info(f"  Fetching depot info for {len(metadata.dlc_ids)} DLC(s)...")
            metadata.dlc_depots = self._fetch_dlc_depots(metadata.dlc_ids)

            self._fetch_dlc_depot_keys_from_community(metadata)

        logger.debug(f"  Fetching access token...")
        metadata.access_token = self._fetch_token(app_id)
        if metadata.access_token:
            logger.debug(f"  Access token obtained")

        depot_with_keys = sum(1 for d in metadata.depots if d.depot_key)
        depot_with_manifests = sum(1 for d in metadata.depots if d.manifest_gid)
        dlc_depot_count = len(metadata.dlc_depots)
        dlc_depot_with_keys = sum(1 for _, d in metadata.dlc_depots if d.depot_key)
        logger.info(
            f"Metadata fetch complete: name={metadata.name}, "
            f"depots={len(metadata.depots)} ({depot_with_keys} with keys, {depot_with_manifests} with manifests), "
            f"dlcs={len(metadata.dlc_ids)} ({dlc_depot_count} DLC depots, {dlc_depot_with_keys} with keys), "
            f"token={'yes' if metadata.access_token else 'no'}, "
            f"workshop={'yes' if metadata.workshop_key else 'no'}"
        )
        return metadata

    def fetch_name(self, app_id: str) -> str:
        cached = self._get_cached_name(app_id)
        if cached:
            return cached

        store_data = self._fetch_store_api(app_id)
        if store_data and "name" in store_data:
            name = store_data["name"]
            self._set_cached_name(app_id, name)
            return name

        return ""

    def _fetch_store_api(self, app_id: str) -> dict | None:
        try:
            resp = self._http.get(
                f"{STEAM_STORE_API}?appids={app_id}",
                headers={"Accept-Language": "zh-CN,zh;q=0.9"},
                timeout=20.0,
            )
            resp.raise_for_status()
            data = resp.json()

            app_data = data.get(str(app_id), {})
            if not app_data.get("success"):
                logger.debug(f"Steam Store API 返回 success=false for {app_id}")
                return None

            return app_data.get("data", {})

        except httpx.HTTPStatusError as e:
            logger.warning(f"Steam Store API HTTP {e.response.status_code} for {app_id}")
        except (httpx.RequestError, json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Steam Store API 请求失败 for {app_id}: {e}")

        return None

    def _fetch_steamcmd_api(self, app_id: str) -> list[DepotInfo]:
        try:
            resp = self._http.get(
                f"{STEAMCMD_API}/{app_id}",
                timeout=20.0,
            )
            resp.raise_for_status()
            data = resp.json()

            app_info = data.get("data", {}).get(str(app_id), {})
            depots = app_info.get("depots", {})

            if not depots:
                logger.debug(f"SteamCMD API 中 {app_id} 无 depot 信息")
                return []

            return self._parse_depots(depots)

        except httpx.HTTPStatusError as e:
            logger.warning(f"SteamCMD API HTTP {e.response.status_code} for {app_id}")
        except (httpx.RequestError, json.JSONDecodeError, ValueError) as e:
            logger.warning(f"SteamCMD API 请求失败 for {app_id}: {e}")

        return []

    def _fetch_dlc_depots(self, dlc_ids: list[str]) -> list[tuple[str, DepotInfo]]:
        logger.debug(f"  Fetching DLC depot info for {len(dlc_ids)} DLC(s)...")
        all_depots: list[tuple[str, DepotInfo]] = []

        max_workers = min(5, len(dlc_ids))
        failed_count = 0

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self._fetch_single_dlc_depots, dlc_id): dlc_id
                for dlc_id in dlc_ids
            }

            for future in as_completed(futures):
                dlc_id = futures[future]
                try:
                    depots = future.result()
                    if depots:
                        all_depots.extend(depots)
                        logger.debug(f"    DLC {dlc_id}: {len(depots)} depot(s)")
                    else:
                        failed_count += 1
                except Exception as e:
                    logger.debug(f"    DLC {dlc_id}: fetch failed ({e})")
                    failed_count += 1

        if failed_count > 0:
            logger.debug(f"  DLC depot fetch: {failed_count}/{len(dlc_ids)} DLCs had no depot info")
        logger.info(f"  Total DLC depots fetched: {len(all_depots)} from {len(dlc_ids)} DLC(s)")
        return all_depots

    def _fetch_single_dlc_depots(self, dlc_id: str) -> list[tuple[str, DepotInfo]]:
        try:
            resp = self._http.get(
                f"{STEAMCMD_API}/{dlc_id}",
                timeout=15.0,
            )
            resp.raise_for_status()
            data = resp.json()

            app_info = data.get("data", {}).get(str(dlc_id), {})
            depots_data = app_info.get("depots", {})

            if not depots_data:
                return []

            depots = self._parse_depots(depots_data)
            return [(dlc_id, d) for d in depots]

        except (httpx.RequestError, httpx.HTTPStatusError, json.JSONDecodeError, ValueError) as e:
            logger.debug(f"  DLC {dlc_id} depot fetch failed: {e}")
            return []

    def _fetch_token(self, app_id: str) -> str:

        now = time.time()
        if app_id in self._token_cache:
            entry = self._token_cache[app_id]
            if now - entry.get("ts", 0) < 86400:
                return entry.get("token", "")

        try:
            resp = self._http.get(TOKEN_API, timeout=15.0)
            resp.raise_for_status()
            data = resp.json()

            if isinstance(data, dict):
                token = data.get(str(app_id), "")
                if token:
                    self._token_cache[app_id] = {"token": token, "ts": now}
                    self._save_token_cache()
                    logger.info(f"获取到 AppID {app_id} 的 Access Token")
                    return token

        except httpx.HTTPStatusError as e:
            logger.debug(f"Token API HTTP {e.response.status_code}")
        except (httpx.RequestError, json.JSONDecodeError, ValueError) as e:
            logger.debug(f"Token API 请求失败: {e}")

        return ""

    def _fetch_depot_keys_from_community(self, metadata: GameMetadata):
        app_id = metadata.app_id

        sudama_keys = self._get_sudama_all_keys()
        if not sudama_keys:
            logger.debug(f"  No Sudama key data available for AppID {app_id}")
            return

        logger.info(f"  Sudama key database loaded: {len(sudama_keys)} entries")

        app_key = self._extract_key_from_sudama(sudama_keys, app_id)
        if app_key:
            metadata.app_level_key = app_key
            self._depotkeys_cache[str(app_id)] = app_key
            logger.info(f"  App-level key found for {app_id} ({len(app_key)} chars)")
        else:
            logger.debug(f"  No app-level key for {app_id} in Sudama")

        depot_keys_found = 0
        for depot in metadata.depots:
            if depot.depot_key:

                continue
            depot_key = self._extract_key_from_sudama(sudama_keys, depot.depot_id)
            if depot_key:
                depot.depot_key = depot_key
                self._depotkeys_cache[str(depot.depot_id)] = depot_key
                depot_keys_found += 1
                logger.debug(f"  Depot {depot.depot_id}: key found in Sudama")

        if depot_keys_found > 0:
            logger.info(f"  Found {depot_keys_found} depot-specific key(s) from Sudama")

        if app_key or depot_keys_found > 0:
            self._save_depotkeys_cache()

    def _fetch_dlc_depot_keys_from_community(self, metadata: GameMetadata):
        if not metadata.dlc_depots:
            return

        sudama_keys = self._sudama_all_keys
        if not sudama_keys:

            sudama_keys = self._get_sudama_all_keys()
        if not sudama_keys:
            return

        dlc_depot_keys_found = 0
        for dlc_appid, depot in metadata.dlc_depots:
            if depot.depot_key:
                continue
            depot_key = self._extract_key_from_sudama(sudama_keys, depot.depot_id)
            if depot_key:
                depot.depot_key = depot_key
                self._depotkeys_cache[str(depot.depot_id)] = depot_key
                dlc_depot_keys_found += 1
                logger.debug(f"  DLC Depot {depot.depot_id}: key found in Sudama")

        if dlc_depot_keys_found > 0:
            logger.info(f"  Found {dlc_depot_keys_found} DLC depot key(s) from Sudama")
            self._save_depotkeys_cache()

    def _get_sudama_all_keys(self) -> dict[str, str]:
        now = time.time()

        if self._sudama_all_keys and (now - self._sudama_fetch_time) < 86400:
            return self._sudama_all_keys

        cached = self._load_sudama_cache_file()
        if cached:
            self._sudama_all_keys = cached
            self._sudama_fetch_time = now
            logger.debug(f"  Sudama keys loaded from local cache ({len(cached)} entries)")
            return cached

        try:
            resp = self._http.get(DEPOT_KEYS_API_ALT, timeout=60.0)
            resp.raise_for_status()
            data = resp.json()

            if not isinstance(data, dict):
                logger.warning("  Sudama API returned non-dict data")
                return {}

            clean_data: dict[str, str] = {}
            for k, v in data.items():
                if isinstance(v, str) and len(v) >= 16:
                    clean_data[str(k)] = v
                elif isinstance(v, list):

                    for item in v:
                        if isinstance(item, dict) and "key" in item:
                            key_val = item["key"]
                            if isinstance(key_val, str) and len(key_val) >= 16:
                                clean_data[str(k)] = key_val
                                break

            self._sudama_all_keys = clean_data
            self._sudama_fetch_time = now
            logger.info(f"  Sudama keys downloaded: {len(clean_data)} entries")

            self._save_sudama_cache_file(clean_data)

            return clean_data

        except Exception as e:
            logger.warning(f"  Sudama API download failed: {e}")

            if self._sudama_all_keys:
                return self._sudama_all_keys
            return {}

    def _load_sudama_cache_file(self) -> dict[str, str]:
        cache_path = self._cache_dir / "sudama_cache.json"
        if not cache_path.exists():
            return {}
        try:
            raw = json.loads(cache_path.read_text(encoding="utf-8"))

            if isinstance(raw, dict) and "data" in raw:
                data = raw["data"]

            elif isinstance(raw, dict):
                data = raw
            else:
                return {}

            clean: dict[str, str] = {}
            for k, v in data.items():
                if isinstance(v, str) and len(v) >= 16:
                    clean[str(k)] = v
                elif isinstance(v, list):
                    for item in v:
                        if isinstance(item, dict) and "key" in item:
                            key_val = item["key"]
                            if isinstance(key_val, str) and len(key_val) >= 16:
                                clean[str(k)] = key_val
                                break
            return clean
        except Exception:
            return {}

    def _save_sudama_cache_file(self, data: dict[str, str]):
        cache_path = self._cache_dir / "sudama_cache.json"
        try:
            cache_data = {
                "timestamp": time.time(),
                "data": data,
            }
            cache_path.write_text(
                json.dumps(cache_data, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            pass

    @staticmethod
    def _extract_key_from_sudama(sudama_keys: dict[str, str], target_id: str) -> str:
        key = sudama_keys.get(str(target_id), "")
        if isinstance(key, str) and len(key) >= 16:
            return key
        return ""

    @staticmethod
    def _try_extract_store_keys(depots: list[DepotInfo], raw_depots: dict):
        _STORE_KEY_FIELDS = (
            "depotkey", "depot_key", "decryption_key",
            "encrypteddepotkey", "encrypted_depot_key",
            "sharedsecret",
        )
        for depot_info in depots:
            raw = raw_depots.get(depot_info.depot_id, {})
            if not isinstance(raw, dict) or depot_info.depot_key:
                continue
            for field in _STORE_KEY_FIELDS:
                val = raw.get(field, "")
                if val:
                    depot_info.depot_key = str(val)
                    logger.debug(
                        f"  Depot {depot_info.depot_id}: Store API key via '{field}'"
                    )
                    break

    def _try_enrich_depot_keys(self, depots: list[DepotInfo], app_id: str):
        try:
            steamcmd_data = self._fetch_steamcmd_api_raw(app_id)
            if not steamcmd_data:
                return

            app_info = steamcmd_data.get("data", {}).get(str(app_id), {})
            cmd_depots = app_info.get("depots", {})

            _KEY_FIELD_NAMES = (
                "depotkey",
                "depot_key",
                "depotKey",
                "decryption_key",
                "decryptionkey",
                "DecryptionKey",
                "key",
                "sharedsecret",
            )

            for depot_info in depots:
                depot_data = cmd_depots.get(depot_info.depot_id, {})
                if not isinstance(depot_data, dict):
                    continue

                for field in _KEY_FIELD_NAMES:
                    val = depot_data.get(field, "")
                    if val and not depot_info.depot_key:
                        depot_info.depot_key = str(val)
                        logger.info(
                            f"  Depot {depot_info.depot_id}: found key via field '{field}'"
                        )
                        break

                if not depot_info.depot_key:
                    config = depot_data.get("config", {})
                    if isinstance(config, dict):
                        for field in _KEY_FIELD_NAMES:
                            val = config.get(field, "")
                            if val:
                                depot_info.depot_key = str(val)
                                logger.info(
                                    f"  Depot {depot_info.depot_id}: found key via config.{field}"
                                )
                                break

                if not depot_info.depot_key:
                    available_fields = [k for k in depot_data.keys() if not k.startswith("_")]
                    logger.debug(
                        f"  Depot {depot_info.depot_id}: no key found "
                        f"(available fields: {available_fields[:10]})"
                    )
        except Exception as e:
            logger.debug(f"Failed to enrich depot keys: {e}")

    def _fetch_steamcmd_api_raw(self, app_id: str) -> dict | None:
        try:
            resp = self._http.get(
                f"{STEAMCMD_API}/{app_id}",
                timeout=20.0,
            )
            resp.raise_for_status()
            return resp.json()
        except (httpx.RequestError, httpx.HTTPStatusError, json.JSONDecodeError, ValueError) as e:
            logger.debug(f"SteamCMD API raw fetch failed for {app_id}: {e}")
            return None

    @staticmethod
    def _is_depot_encrypted(depot: DepotInfo) -> bool:

        if depot.depot_key:
            return False

        if depot.manifest_gid:

            return depot.manifest_gid != "0" and len(depot.manifest_gid) > 4
        return False

    @staticmethod
    def _parse_depots(depots: dict) -> list[DepotInfo]:

        _SKIP_DEPOT_PATTERNS = ("config", "sharedinstall", "shareddepot")

        result: list[DepotInfo] = []
        for depot_id, info in depots.items():
            if not isinstance(info, dict):
                continue

            depot_name = str(info.get("name", "")).lower()
            if any(p in depot_name for p in _SKIP_DEPOT_PATTERNS):
                continue

            manifests = info.get("manifests", {})
            manifest_gid = ""
            size = 0
            if isinstance(manifests, dict):
                for branch_name, branch_data in manifests.items():
                    if isinstance(branch_data, dict):
                        gid = branch_data.get("gid", "")
                        if gid:
                            manifest_gid = str(gid)
                            size = int(branch_data.get("download", 0)) if branch_data.get("download") else 0
                            break

            depot_key = ""
            for key_name in ("decryption_key", "depot_key", "key", "depotkey", "depotDecryptionKey"):
                candidate = info.get(key_name, "")
                if candidate:
                    depot_key = str(candidate)
                    break

            config = info.get("config", {})
            if isinstance(config, dict) and config.get("encrypted"):
                if not depot_key:
                    logger.debug(
                        f"  Depot {depot_id}: encrypted=True, but no depot_key available"
                    )

            result.append(DepotInfo(
                depot_id=str(depot_id),
                manifest_gid=str(manifest_gid) if manifest_gid else "",
                size=size,
                depot_key=depot_key,
            ))

        logger.debug(f"  Parsed {len(result)} depot(s) from {len(depots)} entries")
        return result

    def _get_cached_name(self, app_id: str) -> str:
        return self._name_cache.get(str(app_id), "")

    def _set_cached_name(self, app_id: str, name: str):
        if name:
            self._name_cache[str(app_id)] = name
            self._save_name_cache()

    def _load_caches(self):
        for path, target, name in (
            (self._name_cache_path, "_name_cache", "名称"),
            (self._token_cache_path, "_token_cache", "Token"),
            (self._depotkeys_cache_path, "_depotkeys_cache", "Depot Keys"),
        ):
            try:
                if path.exists():
                    setattr(self, target,
                        json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                setattr(self, target, {})

    def _save_cache(self, path, data):
        try:
            path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass

    def _save_name_cache(self):
        self._save_cache(self._name_cache_path, self._name_cache)

    def _save_token_cache(self):
        self._save_cache(self._token_cache_path, self._token_cache)

    def _save_depotkeys_cache(self):
        self._save_cache(self._depotkeys_cache_path, self._depotkeys_cache)
