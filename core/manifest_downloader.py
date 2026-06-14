"""
Manifest 下载器 — 从 Steam CDN 下载 Depot Manifest 文件到 depotcache

项目的实现：
1. 从 Steam 官方 API 获取 CDN 服务器列表
2. 下载 manifest ZIP 文件并解压提取 payload
3. 存储到 {SteamPath}/depotcache/{DepotID}_{ManifestID}.manifest
4. 自动清理同一 DepotID 的旧版本 manifest

这是解决"游戏启动提示文件缺失"问题的关键模块。
"""
from __future__ import annotations

import io
import logging
import os
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Optional

import httpx

from utils.logger import setup_logger

from config import STEAM_CDN_API, SSL_VERIFY

logger = setup_logger(__name__)

# 常用 Steam CDN 备用列表（API 不可用时使用）
_FALLBACK_CDN_HOSTS = [
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
    "cache1-lax1.steamcontent.com",
    "cache2-lax1.steamcontent.com",
]


@dataclass
class ManifestDownloadResult:
    """单个 Manifest 的下载结果"""
    depot_id: str
    manifest_gid: str
    success: bool
    message: str = ""
    file_path: str = ""


@dataclass
class ManifestBatchResult:
    """批量下载结果"""
    total: int = 0
    success: int = 0
    skipped: int = 0
    failed: int = 0
    results: list[ManifestDownloadResult] = field(default_factory=list)


class ManifestDownloader:
    """Depot Manifest 下载器

    用法：
        downloader = ManifestDownloader(steam_path)
        result = downloader.download_manifests(depots, app_id)
        print(f"Downloaded {result.success}/{result.total}")
    """

    _CDN_CACHE: list[str] = []          # CDN 主机缓存
    _CDN_CACHE_TIME: float = 0
    _CDN_CACHE_TTL: float = 1800.0      # 30 分钟

    def __init__(self, steam_path: str, max_workers: int = 4):
        """初始化下载器

        Args:
            steam_path: Steam 安装根目录
            max_workers: 并发下载线程数
        """
        self._steam_path = steam_path
        self._depotcache_dir = os.path.join(steam_path, "depotcache") if steam_path else ""
        self._max_workers = max_workers

        # HTTP 客户端
        self._http = httpx.Client(
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            },
            timeout=30.0,
            follow_redirects=True,
            verify=SSL_VERIFY,  # Windows 兼容性：禁用 SSL 证书验证
        )

        logger.debug(f"ManifestDownloader initialized: steam_path={steam_path}")

    def close(self):
        """释放 HTTP 资源"""
        self._http.close()

    # ── 公开接口 ──────────────────────────────────────────

    def download_manifests(
        self,
        depots: list[tuple[str, str, int]],  # [(depot_id, manifest_gid, size), ...]
        app_id: str = "",
    ) -> ManifestBatchResult:
        """批量下载 Depot Manifest 文件

        Args:
            depots: [(depot_id, manifest_gid, size), ...] 列表
            app_id: 游戏 AppID（用于日志）

        Returns:
            ManifestBatchResult: 批量下载结果
        """
        if not self._depotcache_dir:
            logger.error("Cannot download manifests: depotcache directory not set")
            return ManifestBatchResult()

        # 确保 depotcache 目录存在
        os.makedirs(self._depotcache_dir, exist_ok=True)

        logger.info(f"Downloading {len(depots)} manifest(s) for AppID {app_id or 'unknown'}")

        # 过滤：去掉 manifest_gid 为空的
        valid_depots = [
            (did, gid, size) for did, gid, size in depots if gid
        ]

        if not valid_depots:
            logger.debug("No valid depots (all missing manifest_gid)")
            return ManifestBatchResult(total=len(depots), skipped=len(depots))

        logger.debug(f"Valid depots to download: {len(valid_depots)}")

        # 获取 CDN 服务器列表
        cdn_hosts = self._get_cdn_hosts()
        if not cdn_hosts:
            logger.error("No CDN hosts available, cannot download manifests")
            return ManifestBatchResult(
                total=len(depots),
                failed=len(valid_depots),
            )

        # 并发下载
        result = ManifestBatchResult(total=len(depots), skipped=len(depots) - len(valid_depots))

        with ThreadPoolExecutor(max_workers=min(self._max_workers, len(valid_depots))) as executor:
            futures = {}
            for depot_id, manifest_gid, size in valid_depots:
                future = executor.submit(
                    self._download_single, depot_id, manifest_gid, size, cdn_hosts
                )
                futures[future] = (depot_id, manifest_gid)

            for future in as_completed(futures):
                depot_id, manifest_gid = futures[future]
                try:
                    dl_result = future.result()
                    result.results.append(dl_result)
                    if dl_result.success:
                        result.success += 1
                    else:
                        result.failed += 1
                except Exception as e:
                    logger.error(f"Download failed for depot {depot_id}/{manifest_gid}: {e}")
                    result.results.append(ManifestDownloadResult(
                        depot_id=depot_id,
                        manifest_gid=manifest_gid,
                        success=False,
                        message=str(e),
                    ))
                    result.failed += 1

        logger.info(
            f"Manifest download complete for AppID {app_id or 'unknown'}: "
            f"{result.success} success, {result.skipped} skipped, {result.failed} failed"
        )
        return result

    def check_manifest_exists(self, depot_id: str, manifest_gid: str) -> bool:
        """检查 manifest 文件是否已存在于 depotcache"""
        if not self._depotcache_dir:
            return False
        filepath = os.path.join(self._depotcache_dir, f"{depot_id}_{manifest_gid}.manifest")
        return os.path.isfile(filepath) and os.path.getsize(filepath) > 0

    def verify_game_manifests(
        self,
        depots: list[tuple[str, str, int]],
    ) -> tuple[bool, list[str]]:
        """验证游戏的 Depot Manifest 文件是否完整

        Returns:
            (全部就绪, 缺失的 manifest 列表)
        """
        missing = []
        for depot_id, manifest_gid, _size in depots:
            if not manifest_gid:
                continue
            if not self.check_manifest_exists(depot_id, manifest_gid):
                missing.append(f"{depot_id}_{manifest_gid}")
                logger.debug(f"Missing manifest: depot={depot_id}, gid={manifest_gid}")

        all_ready = len(missing) == 0
        if not all_ready:
            logger.info(f"Found {len(missing)} missing manifests: {missing[:5]}...")
        return all_ready, missing

    # ── 私有方法 ──────────────────────────────────────────

    def _download_single(
        self,
        depot_id: str,
        manifest_gid: str,
        size: int,
        cdn_hosts: list[str],
    ) -> ManifestDownloadResult:
        """下载单个 Depot Manifest（支持多 CDN 重试）"""
        target_path = os.path.join(self._depotcache_dir, f"{depot_id}_{manifest_gid}.manifest")

        # 如已存在则跳过
        if os.path.isfile(target_path) and os.path.getsize(target_path) > 0:
            logger.debug(f"Manifest exists, skipping: {depot_id}_{manifest_gid}")
            return ManifestDownloadResult(
                depot_id=depot_id,
                manifest_gid=manifest_gid,
                success=True,
                message="already exists",
                file_path=target_path,
            )

        # 尝试从各个 CDN 下载
        for host in cdn_hosts:
            url = self._build_manifest_url(host, depot_id, manifest_gid, size)
            logger.debug(f"Trying CDN: {host} for depot {depot_id}/{manifest_gid}")

            try:
                resp = self._http.get(url, timeout=30.0)
                if resp.status_code == 200:
                    # Steam CDN 返回 ZIP 格式的 manifest
                    manifest_data = self._extract_manifest_payload(resp.content)
                    if manifest_data:
                        # 写入文件
                        with open(target_path, "wb") as f:
                            f.write(manifest_data)

                        # 清理同 Depot 的旧版本 manifest
                        self._clean_old_manifests(depot_id, manifest_gid)

                        logger.info(
                            f"Manifest downloaded: {depot_id}_{manifest_gid} "
                            f"({len(manifest_data)} bytes)"
                        )
                        return ManifestDownloadResult(
                            depot_id=depot_id,
                            manifest_gid=manifest_gid,
                            success=True,
                            message=f"Downloaded ({len(manifest_data)} bytes)",
                            file_path=target_path,
                        )
                    else:
                        logger.debug(f"Empty/Invalid ZIP payload from {host} for {depot_id}")
                        continue
                elif resp.status_code == 404:
                    logger.debug(f"Manifest not found on {host} (404): {depot_id}_{manifest_gid}")
                    continue
                else:
                    logger.debug(f"HTTP {resp.status_code} from {host} for {depot_id}_{manifest_gid}")

            except (httpx.RequestError, httpx.TimeoutException) as e:
                logger.debug(f"CDN {host} failed: {e}")
                continue

        logger.warning(f"All CDNs failed for depot {depot_id}/{manifest_gid}")
        return ManifestDownloadResult(
            depot_id=depot_id,
            manifest_gid=manifest_gid,
            success=False,
            message="All CDNs exhausted",
        )

    @staticmethod
    def _extract_manifest_payload(data: bytes) -> bytes | None:
        """从 Steam CDN 返回的 ZIP 数据中提取 manifest payload

        Steam CDN 将 manifest 数据包装为 ZIP 文件，内部包含名为 'z' 的文件。
        如果解析 ZIP 失败，则原样返回数据（可能已经是原始 payload）。
        """
        if not data:
            return None

        try:
            with zipfile.ZipFile(io.BytesIO(data), "r") as zf:
                # 查找名为 'z' 的内部文件（Steam 标准格式）
                for name in zf.namelist():
                    # 提取匹配的文件名（通常为 'z' 或类似短名）
                    with zf.open(name) as f:
                        payload = f.read()
                        if payload:
                            logger.debug(f"Extracted manifest payload from ZIP: {len(payload)} bytes")
                            return payload
                logger.debug("ZIP parsed but no valid payload found")
                return None
        except (zipfile.BadZipFile, OSError) as e:
            # ZIP 解析失败，可能是原始数据
            logger.debug(f"ZIP parse failed ({e}), using raw data ({len(data)} bytes)")
            return data
        except Exception as e:
            logger.warning(f"Unexpected error extracting manifest: {e}")
            return None

    def _clean_old_manifests(self, depot_id: str, current_gid: str):
        """清理同一 DepotID 的旧版本 manifest 文件（保留当前版本）"""
        if not self._depotcache_dir:
            return
        try:
            current_file = f"{depot_id}_{current_gid}.manifest"
            for fname in os.listdir(self._depotcache_dir):
                if fname.startswith(f"{depot_id}_") and fname.endswith(".manifest"):
                    if fname != current_file:
                        old_path = os.path.join(self._depotcache_dir, fname)
                        try:
                            os.remove(old_path)
                            logger.debug(f"Removed old manifest: {fname}")
                        except OSError:
                            pass
        except OSError:
            pass

    @staticmethod
    def _build_manifest_url(host: str, depot_id: str, manifest_gid: str, size: int = 0) -> str:
        """构建 Steam CDN manifest 下载 URL

        Steam CDN URL 格式：
        - 主模式：/{host}/depot/{depot_id}/manifest/{manifest_gid}/5/{size or 0}
        """
        return f"https://{host}/depot/{depot_id}/manifest/{manifest_gid}/5/{size or 0}"

    def _get_cdn_hosts(self) -> list[str]:
        """获取 Steam CDN 服务器列表（带缓存）

        优先从 Steam 官方 API 获取，失败时使用备用列表。
        """
        # 检查缓存
        now = time.time()
        if self._CDN_CACHE and (now - self._CDN_CACHE_TIME) < self._CDN_CACHE_TTL:
            logger.debug(f"Using cached CDN hosts ({len(self._CDN_CACHE)} hosts)")
            return self._CDN_CACHE

        hosts = self._fetch_cdn_from_api()
        if hosts:
            self._CDN_CACHE = hosts
            self._CDN_CACHE_TIME = now
            logger.info(f"Fetched {len(hosts)} CDN hosts from Steam API")
            return hosts

        # 降级：使用备用列表
        logger.warning("Failed to fetch CDN hosts from API, using fallback list")
        self._CDN_CACHE = _FALLBACK_CDN_HOSTS
        self._CDN_CACHE_TIME = now
        return _FALLBACK_CDN_HOSTS

    def _fetch_cdn_from_api(self) -> list[str]:
        """从 Steam 官方 API 获取 CDN 服务器列表"""
        try:
            resp = self._http.get(STEAM_CDN_API, timeout=10.0)
            resp.raise_for_status()
            data = resp.json()

            servers = data.get("response", {}).get("servers", [])

            # 过滤：优先选择 type="SteamCache" 或 type="CDN" 且加权负载=130 的
            hosts = []
            for server in servers:
                if isinstance(server, dict):
                    srv_type = server.get("type", "")
                    host = server.get("host", "")

                    if not host:
                        continue

                    # SteamCache 类型优先
                    if srv_type == "SteamCache":
                        hosts.append(host)
                    # CDN 类型中负载正常的
                    elif srv_type == "CDN":
                        weighted_load = server.get("weighted_load", 0)
                        if weighted_load == 130:
                            hosts.append(host)

            # 按 HTTPS 支持排序（HTTPS 优先）
            # 简单的启发式：以数字开头的域名通常是 cache 主机
            logger.debug(f"Filtered {len(hosts)} usable CDN hosts from {len(servers)} total")
            return hosts

        except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as e:
            logger.warning(f"Failed to fetch CDN hosts from Steam API: {e}")
            return []
