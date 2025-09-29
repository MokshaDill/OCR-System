# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.building.build_main import Tree


# Bundle poppler if present in project folder
datas = []
if os.path.isdir('poppler-25.07.0'):
    datas += Tree('poppler-25.07.0', prefix='poppler-25.07.0').toc
if os.path.isdir('poppler'):
    datas += Tree('poppler', prefix='poppler').toc
if os.path.isfile('README.md'):
    datas.append(('README.md', 'README.md', 'DATA'))
if os.path.isfile('newicon.ico'):
    datas.append(('newicon.ico', 'newicon.ico', 'DATA'))


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
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
    a.binaries,
    a.datas,
    [],
    name='main',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['newicon.ico'],
)
