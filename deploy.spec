# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['xlsx_to_csv_converter.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('SOLID_STRUCTURE.ico', '.'),
        ('SOLID_STRUCTURE.png', '.'),
    ],
    hiddenimports=[
        'pandas',
        'tkinter',
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        'openpyxl',
        'xlrd',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['app_user_model_id_hook.py'],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='SOLID_STRUCTURE',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='SOLID_STRUCTURE.ico',
    version_file=None,
)

