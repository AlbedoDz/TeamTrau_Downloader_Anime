# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['E:/_Tools/TeamTrau_Downloader_Anime/src/ui/app_window.py'],
    pathex=['E:/_Tools/TeamTrau_Downloader_Anime/src'],
    binaries=[],
    datas=[('E:/_Tools/TeamTrau_Downloader_Anime/src/ui/index.html', 'ui'), ('E:/_Tools/TeamTrau_Downloader_Anime/src/ui/assets', 'ui/assets'), ('E:/_Tools/TeamTrau_Downloader_Anime/src/ui/tokens', 'ui/tokens'), ('E:/_Tools/TeamTrau_Downloader_Anime/ffmpeg', 'ffmpeg')],
    hiddenimports=['webview', 'webview.platforms.winforms', 'clr_loader', 'sqlite3', 'curl_cffi', 'cryptography'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='TeamTrauDownloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['E:/_Tools/TeamTrau_Downloader_Anime/src/ui/assets/icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='TeamTrauDownloader',
)
