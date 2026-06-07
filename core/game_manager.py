
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from utils.logger import setup_logger

logger = setup_logger(__name__)

@dataclass
class DepotInfo:
    depot_id: str
    manifest_gid: str = ""
    size: int = 0
    depot_key: str = ""

@dataclass
class GameMetadata:
    app_id: str
    name: str = ""
    depots: list[DepotInfo] = field(default_factory=list)
    dlc_ids: list[str] = field(default_factory=list)
    dlc_depots: list[tuple[str, DepotInfo]] = field(default_factory=list)
    access_token: str = ""
    workshop_key: str = ""
    app_level_key: str = ""

@dataclass
class GameInfo:
    app_id: str
    name: str = ""
    has_token: bool = False
    has_manifest: bool = False
    has_appticket: bool = False
    lua_path: str = ""

class LuaGameManager:

    def __init__(self, lua_dir: str = ""):
        self._lua_dir: str = lua_dir
        self._games: list[GameInfo] = []
        logger.debug(f"LuaGameManager initialized with lua_dir: {lua_dir or '(empty)'}")

    def set_lua_dir(self, path: str) -> None:
        logger.debug(f"Setting Lua directory: {path}")
        self._lua_dir = path
        if path and not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
            logger.info(f"Created Lua directory: {path}")

    def get_lua_dir(self) -> str:
        return self._lua_dir

    def refresh(self) -> list[GameInfo]:
        logger.debug(f"Refreshing game list from: {self._lua_dir or '(no directory)'}")
        old_count = len(self._games)
        self._games = self._scan_lua_dir()
        new_count = len(self._games)
        logger.info(f"Game list refreshed: {old_count} -> {new_count} games")
        return self._games

    def get_games(self) -> list[GameInfo]:
        if not self._games and self._lua_dir:
            logger.debug("Game list empty, triggering refresh...")
            self.refresh()
        return list(self._games)

    def has_game(self, app_id: str) -> bool:
        if self._games:
            found = any(g.app_id == app_id for g in self._games)
            logger.debug(f"Checking game {app_id} in memory: {found}")
            return found
        if not self._lua_dir:
            logger.debug(f"Checking game {app_id}: no lua_dir, returning False")
            return False
        file_exists = os.path.exists(os.path.join(self._lua_dir, f"{app_id}.lua"))
        logger.debug(f"Checking game {app_id} on disk: {file_exists}")
        return file_exists

    def search_games(self, keyword: str) -> list[GameInfo]:
        keyword_lower = keyword.lower()
        games = self.get_games()
        return [
            g for g in games
            if keyword_lower in g.name.lower() or keyword_lower in g.app_id
        ]

    def add_game(
        self,
        app_id: str,
        name: str = "",
        token: str = "",
        manifest_id: str = "",
    ) -> bool:
        logger.debug(f"add_game called: app_id={app_id}, name={name}, token={'yes' if token else 'no'}, manifest_id={manifest_id or 'none'}")
        metadata = GameMetadata(
            app_id=app_id,
            name=name,
            access_token=token,
        )

        if manifest_id:
            logger.warning(f"manifest_id parameter is deprecated, use add_game_with_metadata instead")
            metadata.depots = [DepotInfo(depot_id=app_id, manifest_gid=manifest_id)]
        return self.add_game_with_metadata(metadata)

    def add_game_basic(self, app_id: str, name: str = "") -> bool:
        if not any(g.app_id == app_id for g in self._games):
            info = GameInfo(
                app_id=app_id,
                name=name,
                lua_path="",
            )
            self._games.append(info)
            logger.info(f"Game {app_id} ({name or 'unknown'}) added to library (basic)")
            return True
        logger.debug(f"Game {app_id} already in library")
        return False

    def add_game_with_metadata(self, metadata: GameMetadata) -> bool:
        if not self._lua_dir:
            logger.error("Cannot add game: lua_dir is not set")
            return False

        filepath = os.path.join(self._lua_dir, f"{metadata.app_id}.lua")
        logger.info(f"Adding game {metadata.app_id} ({metadata.name or 'unknown'})")
        logger.debug(f"Lua file path: {filepath}")
        depot_keys_count = sum(1 for d in metadata.depots if d.depot_key)
        logger.debug(f"Metadata: {len(metadata.depots)} depots ({depot_keys_count} with keys), "
                     f"{len(metadata.dlc_ids)} DLCs, token={'yes' if metadata.access_token else 'no'}, "
                     f"workshop_key={'yes' if metadata.workshop_key else 'no'}")

        content = self._build_lua_content(metadata)
        logger.debug(f"Lua content generated ({len(content)} chars)")

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"Game {metadata.app_id} added successfully")

            if not any(g.app_id == metadata.app_id for g in self._games):
                info = GameInfo(
                    app_id=metadata.app_id,
                    name=metadata.name,
                    lua_path=filepath,
                )
                if metadata.access_token:
                    info.has_token = True
                if metadata.depots:
                    info.has_manifest = True
                self._games.append(info)
                logger.debug(f"Added game {metadata.app_id} to memory list")
            else:

                for g in self._games:
                    if g.app_id == metadata.app_id:
                        if metadata.access_token:
                            g.has_token = True
                        if metadata.depots:
                            g.has_manifest = True
                        if metadata.name:
                            g.name = metadata.name
                        logger.debug(f"Updated game {metadata.app_id} in memory list")
                        break
            return True
        except OSError as e:
            logger.error(f"Failed to write Lua file for {metadata.app_id}: {e}")
            return False

    def remove_game(self, app_id: str) -> bool:
        if not self._lua_dir:
            logger.error("Cannot remove game: lua_dir is not set")
            return False

        filepath = os.path.join(self._lua_dir, f"{app_id}.lua")
        logger.info(f"Removing game {app_id}, file: {filepath}")
        try:
            if os.path.exists(filepath):
                os.remove(filepath)

                self._games = [g for g in self._games if g.app_id != app_id]
                logger.debug(f"Game {app_id} removed from memory list")
            else:
                logger.warning(f"Lua file not found for {app_id}: {filepath}")
            return True
        except OSError as e:
            logger.error(f"Failed to remove game {app_id}: {e}")
            return False

    def clear_all(self) -> int:
        if not self._lua_dir or not os.path.isdir(self._lua_dir):
            logger.warning("Cannot clear games: lua_dir not set or not a directory")
            return 0

        logger.info(f"Clearing all games from: {self._lua_dir}")
        count = 0
        try:
            for fname in os.listdir(self._lua_dir):
                if fname.endswith(".lua"):
                    filepath = os.path.join(self._lua_dir, fname)
                    try:
                        os.remove(filepath)
                        count += 1
                        logger.debug(f"Deleted: {fname}")
                    except OSError as e:
                        logger.error(f"Failed to delete {fname}: {e}")
            self._games.clear()
            logger.info(f"Cleared {count} games")
        except OSError as e:
            logger.error(f"Failed to clear games: {e}")

        return count

    def _scan_lua_dir(self) -> list[GameInfo]:
        if not self._lua_dir or not os.path.isdir(self._lua_dir):
            logger.debug(f"Cannot scan: lua_dir is empty or not a directory")
            return []

        logger.debug(f"Scanning Lua directory: {self._lua_dir}")
        games: list[GameInfo] = []
        try:
            lua_files = [f for f in os.listdir(self._lua_dir) if f.endswith(".lua")]
            logger.debug(f"Found {len(lua_files)} .lua files")
            for fname in lua_files:
                path = os.path.join(self._lua_dir, fname)
                info = self._parse_lua_file(path)
                if info:
                    games.append(info)
            logger.debug(f"Parsed {len(games)} games from Lua files")
        except OSError as e:
            logger.error(f"Failed to scan Lua directory: {e}")

        return games

    def _parse_lua_file(self, path: str) -> GameInfo | None:
        app_id = os.path.splitext(os.path.basename(path))[0]
        if not app_id.isdigit():
            logger.debug(f"Skipping non-numeric file: {os.path.basename(path)}")
            return None

        info = GameInfo(app_id=app_id, lua_path=path)
        logger.debug(f"Parsing Lua file: {os.path.basename(path)}")

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            name_match = re.search(
                r'^--\s*(.+?)(?:\s*\(.*?\))?\s*$',
                content, re.MULTILINE,
            )
            if name_match:
                raw_name = name_match.group(1).strip()

                if "由" not in raw_name:
                    info.name = raw_name
                    logger.debug(f"  Game name: {raw_name}")

            content_lower = content.lower()
            if re.search(r'\baddtoken\s*\(', content_lower):
                info.has_token = True
                logger.debug(f"  Found: addtoken")
            if re.search(r'\bsetmanifestid\s*\(', content_lower):
                info.has_manifest = True
                logger.debug(f"  Found: setManifestid")
            if re.search(r'\bsetappticket\s*\(', content_lower):
                info.has_appticket = True
                logger.debug(f"  Found: setAppTicket")

        except (OSError, UnicodeDecodeError) as e:
            logger.error(f"Failed to parse Lua file {path}: {e}")
            return None

        logger.debug(f"Parsed game {app_id}: name={info.name}, token={info.has_token}, manifest={info.has_manifest}")
        return info

    @staticmethod
    def _build_lua_content(metadata: GameMetadata) -> str:
        logger.debug(f"Building Lua content for {metadata.app_id} ({metadata.name or 'unknown'})")
        lines: list[str] = []

        if metadata.name:
            lines.append(f"-- {metadata.name} (由 OpenSteamToolDesktop 管理)")
        else:
            lines.append(f"-- AppID: {metadata.app_id} (由 OpenSteamToolDesktop 管理)")

        if metadata.app_level_key:
            lines.append(f'addappid({metadata.app_id}, 0, "{metadata.app_level_key}")')
            logger.debug(f"  Main app: addappid({metadata.app_id}, 0, \"...\") [with app-level key]")
        else:
            lines.append(f"addappid({metadata.app_id})")
            logger.debug(f"  Main app: addappid({metadata.app_id}) [no key]")

        main_depot_with_key = 0
        main_depot_without_key = 0
        for depot in metadata.depots:
            if depot.depot_key:

                lines.append(f'addappid({depot.depot_id}, 0, "{depot.depot_key}")')
                main_depot_with_key += 1
            else:

                lines.append(f"addappid({depot.depot_id})")
                main_depot_without_key += 1
        logger.debug(f"  Main depots: {main_depot_with_key} with keys, {main_depot_without_key} without keys")

        if metadata.access_token:
            lines.append(f'addtoken({metadata.app_id}, "{metadata.access_token}")')

        dlc_count = 0
        for dlc_id in sorted(set(metadata.dlc_ids), key=int):
            if dlc_id == metadata.app_id:
                continue
            lines.append(f"addappid({dlc_id})")
            dlc_count += 1
        if dlc_count > 0:
            logger.debug(f"  Added {dlc_count} DLC(s)")

        dlc_depot_with_key = 0
        for dlc_appid, depot in metadata.dlc_depots:
            if depot.depot_key:
                lines.append(f'addappid({depot.depot_id}, 0, "{depot.depot_key}")')
                dlc_depot_with_key += 1

        if dlc_depot_with_key > 0:
            logger.debug(f"  Added {dlc_depot_with_key} DLC depot key(s)")

        lines.append("")
        logger.debug(f"Lua content built: {len(lines)} lines")
        return "\n".join(lines)
