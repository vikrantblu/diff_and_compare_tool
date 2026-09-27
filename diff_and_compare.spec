# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['app\\main.py'],
    pathex=[],
    datas=[('assets', 'assets')],
    hiddenimports=[
        'tree_sitter',
        'tree_sitter_python',
        'tree_sitter_javascript',
        'blake3',
        'pyarrow',
        'pyarrow.parquet',
        'fitz',
        'jsonpath_ng',
        'openpyxl',
        'yaml'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt6', 'PyQt5', 'tkinter', 'kivy', 'kivymd', 'pygame', 'yt_dlp', 'scipy', 'torch', 'torchvision', 'torchaudio', 'matplotlib', 'pandas', 'IPython', 'jupyter'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='diff_and_compare',
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
    icon='assets\\app_icon.ico',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='diff_and_compare',
)
