
from pathlib import Path

block_cipher = None
project_root = Path(SPECPATH)

a = Analysis(
    [str(project_root / 'main.py')],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        (str(project_root / 'assets'), 'assets'),
    ],
    hiddenimports=[
        'PyQt6.QtWidgets',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtNetwork',
        'PyQt6.QtSvg',
        'PyQt6.sip',
        'qfluentwidgets',
        'httpx',
        'httpcore',
        'hpack',
        'hyperframe',
        'anyio',
        'sniffio',
        'certifi',
        'idna',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'scipy',
        'pandas',
        'PIL',
        'cv2',
        'pytest',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='OpenSteamToolDesktop',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / 'gui' / 'icon.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='OpenSteamToolDesktop',
)
