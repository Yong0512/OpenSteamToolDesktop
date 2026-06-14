
"""
游戏库管理器 — 基于 Lua 配置文件的真实实现

管理 OpenSteamTool 的 Lua 配置文件：
- 扫描 <lua_dir>/*.lua
- 解析 addappid/addtoken/setManifestid/setAppTicket/setStat
- 支持添加/删除/搜索游戏
- 支持带完整元数据的入库（depot info、DLC、token）
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from utils.logger import setup_logger

logger = setup_logger(__name__)


# ── 数据类 ──────────────────────────────────────────────────


@dataclass
class DepotInfo:
    """单个 Depot 的元数据"""
    depot_id: str
    manifest_gid: str = ""
    size: int = 0
    depot_key: str = ""  # Depot 解密密钥（HEX 字符串）


@dataclass
class GameMetadata:
    """游戏的完整入库元数据"""
    app_id: str
    name: str = ""
    depots: list[DepotInfo] = field(default_factory=list)
    dlc_ids: list[str] = field(default_factory=list)
    dlc_depots: list[tuple[str, DepotInfo]] = field(default_factory=list)
    access_token: str = ""
    workshop_key: str = ""
    app_level_key: str = ""  # 应用级密钥（来自 Sudama，打在 addappid(app_id, 0, key) 主游戏行）


@dataclass
class GameInfo:
    """Lua 配置文件对应的游戏信息"""
    app_id: str
    name: str = ""
    has_token: bool = False
    has_manifest: bool = False
    has_appticket: bool = False
    lua_path: str = ""


class LuaGameManager:
    """基于 Lua 配置文件的游戏库管理器"""

    def __init__(self, lua_dir: str = ""):
        """初始化游戏管理器

        Args:
            lua_dir: OpenSteamTool Lua 配置目录路径
        """
        self._lua_dir: str = lua_dir
        self._games: list[GameInfo] = []
        logger.debug(f"LuaGameManager initialized with lua_dir: {lua_dir or '(empty)'}")

    # ---- 目录管理 ----

    def set_lua_dir(self, path: str) -> None:
        """设置 Lua 配置目录并自动创建

        Args:
            path: 目录路径
        """
        logger.debug(f"Setting Lua directory: {path}")
        self._lua_dir = path
        if path and not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
            logger.info(f"Created Lua directory: {path}")

    def get_lua_dir(self) -> str:
        """获取当前 Lua 配置目录"""
        return self._lua_dir

    # ---- 游戏查询 ----

    def refresh(self) -> list[GameInfo]:
        """重新扫描 Lua 目录，返回最新游戏列表"""
        logger.debug(f"Refreshing game list from: {self._lua_dir or '(no directory)'}")
        old_count = len(self._games)
        self._games = self._scan_lua_dir()
        new_count = len(self._games)
        logger.info(f"Game list refreshed: {old_count} -> {new_count} games")
        return self._games

    def get_games(self) -> list[GameInfo]:
        """获取游戏列表（优先返回缓存，首次调用时扫描）"""
        if not self._games and self._lua_dir:
            logger.debug("Game list empty, triggering refresh...")
            self.refresh()
        return list(self._games)

    def has_game(self, app_id: str) -> bool:
        """检查游戏是否已在库中（优先内存，减少文件系统访问）"""
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
        """按名称或 AppID 搜索游戏"""
        keyword_lower = keyword.lower()
        games = self.get_games()
        return [
            g for g in games
            if keyword_lower in g.name.lower() or keyword_lower in g.app_id
        ]

    # ---- 游戏管理 ----

    def add_game(
        self,
        app_id: str,
        name: str = "",
        token: str = "",
        manifest_id: str = "",
    ) -> bool:
        """将游戏加入库中（写入 Lua 文件）— 简单模式，向后兼容

        Args:
            app_id: Steam AppID
            name: 游戏名称（写入注释）
            token: PICS 访问令牌（可选）
            manifest_id: 已废弃，请使用 add_game_with_metadata

        Returns:
            是否写入成功
        """
        logger.debug(f"add_game called: app_id={app_id}, name={name}, token={'yes' if token else 'no'}, manifest_id={manifest_id or 'none'}")
        metadata = GameMetadata(
            app_id=app_id,
            name=name,
            access_token=token,
        )
        # 旧 manifest_id 是 app_id 级别的，转为 depot（兼容但标记废弃）
        if manifest_id:
            logger.warning(f"manifest_id parameter is deprecated, use add_game_with_metadata instead")
            metadata.depots = [DepotInfo(depot_id=app_id, manifest_gid=manifest_id)]
        return self.add_game_with_metadata(metadata)

    def add_game_basic(self, app_id: str, name: str = "") -> bool:
        """即时入库（仅记录 app_id + name，不写 Lua 文件）

        Lua 文件在后续后台 fetch metadata 时写入。
        """
        if not any(g.app_id == app_id for g in self._games):
            info = GameInfo(
                app_id=app_id,
                name=name,
                lua_path="",  # Lua 尚未生成
            )
            self._games.append(info)
            logger.info(f"Game {app_id} ({name or 'unknown'}) added to library (basic)")
            return True
        logger.debug(f"Game {app_id} already in library")
        return False

    def add_game_with_metadata(self, metadata: GameMetadata) -> bool:
        """将游戏加入库中（写入 Lua 文件）— 完整元数据模式

        Args:
            metadata: 包含 depots、dlcs、token 等完整元数据

        Returns:
            是否写入成功
        """
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

            # 增量更新内存列表
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
                # 更新已有条目的元数据标记
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
        """将游戏移出库（删除 Lua 文件）

        Args:
            app_id: Steam AppID

        Returns:
            是否删除成功
        """
        if not self._lua_dir:
            logger.error("Cannot remove game: lua_dir is not set")
            return False

        filepath = os.path.join(self._lua_dir, f"{app_id}.lua")
        logger.info(f"Removing game {app_id}, file: {filepath}")
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                # 增量更新内存列表
                self._games = [g for g in self._games if g.app_id != app_id]
                logger.debug(f"Game {app_id} removed from memory list")
            else:
                logger.warning(f"Lua file not found for {app_id}: {filepath}")
            return True
        except OSError as e:
            logger.error(f"Failed to remove game {app_id}: {e}")
            return False

    def clear_all(self) -> int:
        """清空所有游戏（删除所有 .lua 文件）

        Returns:
            成功删除的游戏数量
        """
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

    # ---- 内部方法 ----

    def _scan_lua_dir(self) -> list[GameInfo]:
        """扫描 Lua 目录，解析所有 .lua 文件"""
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
        """解析单个 Lua 文件提取游戏信息

        解析规则：
        - 文件名作为 AppID（必须为纯数字）
        - 第一行注释提取游戏名称
        - 检测 addtoken / setManifestid / setAppTicket / setStat 调用
        """
        app_id = os.path.splitext(os.path.basename(path))[0]
        if not app_id.isdigit():
            logger.debug(f"Skipping non-numeric file: {os.path.basename(path)}")
            return None

        info = GameInfo(app_id=app_id, lua_path=path)
        logger.debug(f"Parsing Lua file: {os.path.basename(path)}")

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            # 从第一行有效注释提取名称
            name_match = re.search(
                r'^--\s*(.+?)(?:\s*\(.*?\))?\s*$',
                content, re.MULTILINE,
            )
            if name_match:
                raw_name = name_match.group(1).strip()
                # 排除管理标记
                if "由" not in raw_name:
                    info.name = raw_name
                    logger.debug(f"  Game name: {raw_name}")

            # 检测配置调用（大小写不敏感）
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
        """构建完整的 Lua 文件内容

        格式遵循 OpenSteamTool README（行 52-61）+ 参考项目验证：

        ```lua
        -- 游戏名 (由 OpenSteamToolDesktop 管理)
        addappid(730, 0, "app_level_key")              -- 主应用 + 应用级密钥（可选）
        addappid(731, 0, "depot_specific_key")          -- Depot 专属密钥
        addappid(732)                                    -- Depot 无密钥
        addtoken(730, "accessToken")                     -- Access Token
        addappid(12345)                                  -- DLC
        addappid(12346, 0, "dlc_depot_key")             -- DLC Depot 密钥
        ```

        1. app_level_key 打在主游戏行 addappid(app_id, 0, key)，NOT 作为 depot 回退
        2. depot 专属密钥只打在有对应密钥的 depot 行，无密钥的 depot 只写 addappid(depot_id)
        3. 不使用 setManifestid（由 DLL 通过 steamrun/wudrm 自动下载 manifest）
        """
        logger.debug(f"Building Lua content for {metadata.app_id} ({metadata.name or 'unknown'})")
        lines: list[str] = []

        # ── 注释行 ──
        if metadata.name:
            lines.append(f"-- {metadata.name} (由 OpenSteamToolDesktop 管理)")
        else:
            lines.append(f"-- AppID: {metadata.app_id} (由 OpenSteamToolDesktop 管理)")

        # ── 主游戏入库 ──
        # OpenSteamTool README 行 52: addappid(appid) 无密钥形式
        # OpenSteamTool README 行 54: addappid(depot_id, 0, "key") 带密钥形式
        if metadata.app_level_key:
            lines.append(f'addappid({metadata.app_id}, 0, "{metadata.app_level_key}")')
            logger.debug(f"  Main app: addappid({metadata.app_id}, 0, \"...\") [with app-level key]")
        else:
            lines.append(f"addappid({metadata.app_id})")
            logger.debug(f"  Main app: addappid({metadata.app_id}) [no key]")

        # ── Depot 密钥 ──
        # 关键修复：不再将 app_level_key 作为 depot 回退密钥！
        # 每个 depot 有自己唯一的加密密钥，必须从 Sudama 按 depot_id 单独查找
        main_depot_with_key = 0
        main_depot_without_key = 0
        for depot in metadata.depots:
            if depot.depot_key:
                # 有专属 depot 密钥 → 带密钥注册
                lines.append(f'addappid({depot.depot_id}, 0, "{depot.depot_key}")')
                main_depot_with_key += 1
            else:
                # 无密钥 → 仅注册 depot（DLL 可能通过其他方式获取密钥）
                lines.append(f"addappid({depot.depot_id})")
                main_depot_without_key += 1
        logger.debug(f"  Main depots: {main_depot_with_key} with keys, {main_depot_without_key} without keys")

        # ── Access Token ──
        if metadata.access_token:
            lines.append(f'addtoken({metadata.app_id}, "{metadata.access_token}")')

        # ── DLC 入库 ──
        dlc_count = 0
        for dlc_id in sorted(set(metadata.dlc_ids), key=int):
            if dlc_id == metadata.app_id:
                continue
            lines.append(f"addappid({dlc_id})")
            dlc_count += 1
        if dlc_count > 0:
            logger.debug(f"  Added {dlc_count} DLC(s)")

        # ── DLC Depot 密钥 ──
        dlc_depot_with_key = 0
        for dlc_appid, depot in metadata.dlc_depots:
            if depot.depot_key:
                lines.append(f'addappid({depot.depot_id}, 0, "{depot.depot_key}")')
                dlc_depot_with_key += 1
            # 无密钥的 DLC depot 不单独注册（已通过 DLC appid 行注册）
        if dlc_depot_with_key > 0:
            logger.debug(f"  Added {dlc_depot_with_key} DLC depot key(s)")

        lines.append("")
        logger.debug(f"Lua content built: {len(lines)} lines")
        return "\n".join(lines)

    
