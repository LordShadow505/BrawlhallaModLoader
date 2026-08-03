# -*- mode: python ; coding: utf-8 -*-
import os

client_a = Analysis(['client.py'],
                    binaries=[],
                    datas=[],
                    hiddenimports=[],
                    hookspath=[],
                    runtime_hooks=[],
                    excludes=['unittest', 'email', 'html', 'http', 'urllib',
                    'xml', 'pydoc', 'doctest', 'datetime', 'zipfile',
                    'pickle', 'calendar', 'tkinter',
                    'bz2', 'getopt', 'string', 'quopri', 'copy', 'imp',
                    'aioflask', 'aiohttp', 'cairo', 'cython', 'flask', 'PIL', 'wand',
                    'java.lang', 'xml.parsers', 'datetime', 'java', 'pickle'],
                    win_no_prefer_redirects=False,
                    win_private_assemblies=False,
                    noarchive=False)

client_pyz = PYZ(client_a.pure, client_a.zipped_data, cipher=None)

client_exe = EXE(client_pyz,
                 client_a.scripts,
                 client_a.binaries,
                 client_a.zipfiles,
                 client_a.datas,
                 name='ModLoaderClient',
                 debug=False,
                 bootloader_ignore_signals=False,
                 strip=False,
                 upx=True,
                 upx_exclude=['vcruntime140.dll', 'ucrtbase.dll'],
                 runtime_tmpdir=None,
                 console=False)
