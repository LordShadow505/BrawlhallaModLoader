# -*- mode: python ; coding: utf-8 -*-
import os
import glob
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_all

# --- MSVC runtime DLLs for clean Windows PCs ---
sys32 = Path(os.environ.get("SystemRoot", "C:\\Windows")) / "System32"
msvc_binaries = []
for name in ["vcruntime140.dll", "vcruntime140_1.dll", "msvcp140.dll", "msvcp140_1.dll", "msvcp140_2.dll"]:
    p = sys32 / name
    if p.exists():
        msvc_binaries.append((str(p), "."))

# --- Explicitly collect .pyd binary extensions that collect_all misses ---
# These C-extension packages have compiled .pyd files that PyInstaller won't
# auto-detect without being listed in binaries with their correct destination.
import site
_sp = Path(site.getsitepackages()[0])

def _collect_pkg_binaries(pkg_name):
    """Return (src, dest_dir) tuples for all .pyd files in a package."""
    pkg_dir = _sp / pkg_name
    result = []
    for pyd in pkg_dir.rglob("*.pyd"):
        dest = str(pyd.parent.relative_to(_sp)).replace("\\", "/")
        result.append((str(pyd), dest))
    return result

pyd_binaries = []
for pkg in ['bcj', 'pyppmd', 'inflate64']:
    pyd_binaries.extend(_collect_pkg_binaries(pkg))

# --- Hidden imports: submodules + explicit entries ---
loader_hidden_imports = [
    'win32api', 'win32con', 'win32gui', 'win32process',
    'core', 'core.worker', 'core.worker.brawlhalla', 'core.worker.config',
    'requests', 'yarl', 'encodings.idna', 'encodings.utf_8',
    'markdown', 'markdown.extensions.tables', 'markdown.extensions.fenced_code',
    'markdown.extensions.sane_lists',
    'rarfile', 'jpype', '_jpype',
    # bcj submodules
    'bcj', 'bcj._bcj', 'bcj._bcjfilter',
    # pyppmd
    'pyppmd', 'pyppmd.c',
    # inflate64
    'inflate64',
    # multivolumefile
    'multivolumefile',
]
for mod_name in ['py7zr', 'multivolumefile', 'Cryptodome', 'pybanana']:
    try:
        loader_hidden_imports.extend(collect_submodules(mod_name))
    except Exception:
        pass

# --- Client (tiny IPC helper) ---
client_a = Analysis(['client.py'],
                    binaries=[],
                    datas=[],
                    hiddenimports=[],
                    hookspath=[],
                    runtime_hooks=[],
                    excludes=['unittest', 'email', 'html', 'http', 'urllib',
                              'xml', 'pydoc', 'doctest', 'datetime', 'zipfile',
                              'pickle', 'calendar', 'tkinter', 'bz2', 'getopt',
                              'string', 'quopri', 'copy', 'imp', 'aioflask',
                              'aiohttp', 'cairo', 'cython', 'flask', 'PIL', 'wand',
                              'java.lang', 'xml.parsers', 'java'],
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

# --- Main loader app ---
_qt_excludes = [
    'tkinter', '_tkinter',
    'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineQuick', 'PySide6.QtWebEngineWidgets',
    'PySide6.Qt3DCore', 'PySide6.Qt3DRender', 'PySide6.Qt3DInput', 'PySide6.Qt3DLogic',
    'PySide6.Qt3DAnimation', 'PySide6.Qt3DExtras', 'PySide6.QtDesigner',
    'PySide6.QtDesignerComponents', 'PySide6.QtGraphs', 'PySide6.QtLocation',
    'PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets', 'PySide6.QtPdf',
    'PySide6.QtPdfWidgets', 'PySide6.QtPositioning', 'PySide6.QtQml',
    'PySide6.QtQuick', 'PySide6.QtQuick3D', 'PySide6.QtQuickControls2',
    'PySide6.QtQuickWidgets', 'PySide6.QtRemoteObjects', 'PySide6.QtScxml',
    'PySide6.QtSensors', 'PySide6.QtSerialBus', 'PySide6.QtSerialPort',
    'PySide6.QtSpatialAudio', 'PySide6.QtSql', 'PySide6.QtStateMachine',
    'PySide6.QtTest', 'PySide6.QtTextToSpeech', 'PySide6.QtVirtualKeyboard',
]

app_a = Analysis(['run.py'],
                 binaries=msvc_binaries + pyd_binaries,
                 datas=[],
                 hiddenimports=loader_hidden_imports,
                 hookspath=[],
                 runtime_hooks=[],
                 excludes=_qt_excludes,
                 win_no_prefer_redirects=False,
                 win_private_assemblies=False,
                 noarchive=False)

app_a.datas += [('file_icon.ico', 'file_icon.ico', 'DATA'),
                (os.path.split(client_exe.name)[1], client_exe.name, 'DATA'),
                ('unrar.exe', 'libs\\unrar.exe', 'DATA')]
app_a.datas += Tree("ui", "ui", excludes=["*.ttf", "*.ui", "*.txt", "*.pyc", "*.pyo"])
app_a.datas += Tree("core", "core", excludes=["*.pyc", "*.pyo"])

app_pyz = PYZ(app_a.pure, app_a.zipped_data)

app_splash = Splash('splash.png',
                    binaries=app_a.binaries,
                    datas=app_a.datas,
                    text_pos=(192, 290),
                    text_font="ui/ui_sources/resources/fonts/Bespoke/Bespoke.ttf",
                    text_size=12,
                    text_color='#FFFFFF')

app_exe = EXE(app_pyz,
              app_a.scripts,
              app_a.binaries,
              app_a.zipfiles,
              app_a.datas,
              app_splash,
              app_splash.binaries,
              name='Brawlhalla Mod Loader',
              debug=False,
              bootloader_ignore_signals=False,
              strip=False,
              upx=False,
              upx_exclude=['vcruntime140.dll', 'ucrtbase.dll'],
              runtime_tmpdir=None,
              version='version.spec',
              console=False,
              icon='ui/ui_sources/resources/icons/App.ico')
