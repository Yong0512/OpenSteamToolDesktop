"""
OpenSteamToolDesktop 打包脚本
==============================

用法:
    python build_exe.py              # PyInstaller 打包（默认）
    python build_exe.py --nuitka     # Nuitka 编译打包（代码保护更强）
    python build_exe.py --clean      # 清理构建产物
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"
SPEC_FILE = PROJECT_ROOT / "OpenSteamToolDesktop.spec"
ICON_PATH = PROJECT_ROOT / "assets" / "icon.ico"


def clean():
    """清理构建产物"""
    for d in [DIST_DIR, BUILD_DIR]:
        if d.exists():
            print(f"Removing {d}")
            shutil.rmtree(d)

    nuitka_build = PROJECT_ROOT / "main.build"
    nuitka_dist = PROJECT_ROOT / "main.dist"
    for d in [nuitka_build, nuitka_dist]:
        if d.exists():
            print(f"Removing {d}")
            shutil.rmtree(d)

    pycache = list(PROJECT_ROOT.rglob("__pycache__"))
    for p in pycache:
        print(f"Removing {p}")
        shutil.rmtree(p, ignore_errors=True)

    print("Clean complete.")


def build_pyinstaller(*, no_zip: bool = False):
    """执行 PyInstaller 打包"""
    if not SPEC_FILE.exists():
        print(f"Error: {SPEC_FILE} not found.")
        sys.exit(1)

    print("=" * 60)
    print("OpenSteamToolDesktop PyInstaller Build")
    print("=" * 60)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        str(SPEC_FILE),
    ]

    print(f"Running: {' '.join(cmd)}")
    print()

    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))

    if result.returncode != 0:
        print(f"\nBuild failed with return code {result.returncode}")
        sys.exit(result.returncode)

    exe_path = DIST_DIR / "OpenSteamToolDesktop" / "OpenSteamToolDesktop.exe"
    if not exe_path.exists():
        print(f"\nBuild finished, but exe not found at expected path: {exe_path}")
        sys.exit(1)

    dll_src = PROJECT_ROOT / "resources/fallback_dlls"
    dll_dst = DIST_DIR / "OpenSteamToolDesktop" / "_internal" / "resources/fallback_dlls"
    if dll_src.is_dir():
        if dll_dst.exists():
            shutil.rmtree(dll_dst)
        shutil.copytree(dll_src, dll_dst)
        print(f"\nCopied resources/fallback_dlls DLLs -> {dll_dst}")
    else:
        print(f"\nWarning: {dll_src} not found, DLLs not bundled!")

    size_mb = exe_path.stat().st_size / (1024 * 1024)
    print(f"\nBuild successful!")
    print(f"Output: {exe_path}  ({size_mb:.1f} MB)")

    if not no_zip:
        zip_dist()


def build_nuitka(*, no_zip: bool = False):
    """执行 Nuitka 编译打包（C++ 编译，单文件，代码保护更强）"""
    print("=" * 60)
    print("OpenSteamToolDesktop Nuitka Onefile Build")
    print("=" * 60)

    icon_arg = f"--windows-icon-from-ico={ICON_PATH}" if ICON_PATH.exists() else ""

    cmd = [
        sys.executable, "-m", "nuitka",
        "--onefile",
        "--enable-plugin=pyqt6",
        "--windows-console-mode=disable",
        f"--include-data-dir={PROJECT_ROOT / 'resources/fallback_dlls'}=resources/fallback_dlls",
        f"--include-data-dir={PROJECT_ROOT / 'assets'}=assets",
        f"--include-data-files={PROJECT_ROOT / 'resources/fallback_dlls' / 'OpenSteamTool.dll'}=resources/fallback_dlls/OpenSteamTool.dll",
        f"--include-data-files={PROJECT_ROOT / 'resources/fallback_dlls' / 'dwmapi.dll'}=resources/fallback_dlls/dwmapi.dll",
        f"--include-data-files={PROJECT_ROOT / 'resources/fallback_dlls' / 'xinput1_4.dll'}=resources/fallback_dlls/xinput1_4.dll",
        "--output-filename=OpenSteamToolDesktop.exe",
        f"--output-dir={DIST_DIR}",
        "--company-name=OpenSteamToolDesktop",
        "--product-name=OpenSteamToolDesktop",
        "--file-version=1.0.0",
        "--product-version=1.0.0",
        "--file-description=OpenSteamToolDesktop Application",
        "--assume-yes-for-downloads",
        "--nofollow-import-to=tests",
    ]

    if icon_arg:
        cmd.append(icon_arg)

    cmd.append(str(PROJECT_ROOT / "main.py"))

    print(f"Running: {' '.join(cmd)}")
    print()

    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))

    if result.returncode != 0:
        print(f"\nBuild failed with return code {result.returncode}")
        sys.exit(result.returncode)

    exe_path = DIST_DIR / "OpenSteamToolDesktop.exe"
    if not exe_path.exists():
        print(f"\nBuild finished, but exe not found at expected path: {exe_path}")
        sys.exit(1)

    size_mb = exe_path.stat().st_size / (1024 * 1024)
    print(f"\nBuild successful!")
    print(f"Output: {exe_path}  ({size_mb:.1f} MB)")

    if not no_zip:
        zip_dist()


def get_version() -> str:
    """从 config.py 读取版本号"""
    config_py = PROJECT_ROOT / "config.py"
    if config_py.exists():
        for line in config_py.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("APP_VERSION") or line.startswith("VERSION"):
                # APP_VERSION: str = "1.0.2"  或  VERSION = "v1.0.1"
                val = line.split("=", 1)[-1].strip().strip("\"'")
                return val
    return "unknown"


def zip_dist():
    """将打包产物压缩为 Zip 包"""
    version = get_version()
    zip_name = f"OpenSteamToolDesktop-{version}.zip"
    zip_path = PROJECT_ROOT / zip_name

    # PyInstaller 产物：dist/OpenSteamToolDesktop/ 目录
    pyinstaller_dir = DIST_DIR / "OpenSteamToolDesktop"
    # Nuitka 产物：dist/OpenSteamToolDesktop.exe 单文件
    nuitka_exe = DIST_DIR / "OpenSteamToolDesktop.exe"

    if pyinstaller_dir.is_dir():
        source_dir = pyinstaller_dir
        arc_root = f"OpenSteamToolDesktop-{version}"
        print(f"\nZipping: {source_dir} -> {zip_path.name}")

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(source_dir):
                for file in files:
                    full_path = os.path.join(root, file)
                    # 归档名：arc_root/相对路径
                    arc_name = arc_root + "/" + os.path.relpath(full_path, source_dir)
                    zf.write(full_path, arc_name)

    elif nuitka_exe.exists():
        print(f"\nZipping: {nuitka_exe.name} -> {zip_path.name}")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            arc_name = f"OpenSteamToolDesktop-{version}/OpenSteamToolDesktop.exe"
            zf.write(nuitka_exe, arc_name)

    else:
        print("\nNothing to zip: dist/ is empty.")
        return

    zip_size = zip_path.stat().st_size / (1024 * 1024)
    print(f"Zip created: {zip_path}  ({zip_size:.1f} MB)")


def main():
    parser = argparse.ArgumentParser(description="OpenSteamToolDesktop Build Script")
    parser.add_argument("--clean", action="store_true", help="Clean build artifacts only")
    parser.add_argument("--nuitka", action="store_true", help="Use Nuitka (C++ compile, stronger protection)")
    parser.add_argument("--no-zip", action="store_true", help="Skip creating zip package after build")
    args = parser.parse_args()

    if args.clean:
        clean()
    else:
        clean()
        if args.nuitka:
            build_nuitka(no_zip=args.no_zip)
        else:
            build_pyinstaller(no_zip=args.no_zip)


if __name__ == "__main__":
    main()
