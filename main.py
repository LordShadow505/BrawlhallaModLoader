import os
import sys

class NullWriter:
    def write(self, s): pass
    def flush(self): pass

if sys.stdout is None:
    sys.stdout = NullWriter()
if sys.stderr is None:
    sys.stderr = NullWriter()

import ssl
try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass

import time
import py7zr
import urllib
import rarfile
import zipfile
import traceback
import threading
import webbrowser
import subprocess
import requests
import multiprocessing

import urllib3
try:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass

# (https://stackoverflow.com/questions/9144724/unknown-encoding-idna-in-python-requests)
import encodings.idna


def global_excepthook(exctype, value, tb):
    try:
        if sys.stderr and sys.stderr is not None:
            traceback.print_exception(exctype, value, tb)
    except Exception:
        pass

sys.excepthook = global_excepthook



class FlowTracer:
    load_session_id = 0

    @classmethod
    def log(cls, func_name: str, details: str = ""):
        try:
            caller_frame = inspect.stack()[1]
            caller_name = caller_frame.function
            caller_file = os.path.basename(caller_frame.filename)
            caller_line = caller_frame.lineno
        except Exception:
            pass


    @classmethod
    def new_session(cls, reason: str = ""):
        cls.load_session_id += 1
        print(f"\n==================== [START LOAD SESSION #{cls.load_session_id}: {reason}] ====================")



# Auto-detect unrar.exe for RAR file extraction
for _unrar in [
    r"C:\Program Files\WinRAR\unrar.exe",
    r"C:\Program Files (x86)\WinRAR\unrar.exe",
    os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "WinRAR", "unrar.exe"),
    os.path.join(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"), "WinRAR", "unrar.exe"),
]:
    if os.path.exists(_unrar):
        rarfile.UNRAR_TOOL = _unrar
        print(f"[Main] Auto-configured rarfile UNRAR_TOOL: '{_unrar}'")
        break

from typing import List


core = None
try:
    import core
    from core import NotificationType, Notification, Environment, CORE_VERSION

    JAVA_FOUND = True
except Exception as e:
    NotificationType = Notification = Environment = CORE_VERSION = None
    JAVA_FOUND = False

    CORE_IMPORT_ERROR = f"{type(e).__name__}: {str(e)}"
    print(f"Error importing core: {CORE_IMPORT_ERROR}")
    traceback.print_exc()
from PySide6.QtCore import QSize, QTranslator, QLocale, QTimer, Signal, Qt
from PySide6.QtGui import QIcon, QFontDatabase, QFont, QClipboard
from PySide6.QtWidgets import QMainWindow, QApplication, QFrame, QVBoxLayout, QLabel

from ui.ui_handler.window import Window
from ui.ui_handler.header import HeaderFrame
from ui.ui_handler.loading import Loading
from ui.ui_handler.mods import Mods
from ui.ui_handler.progressdialog import ProgressDialog
from ui.ui_handler.buttonsdialog import ButtonsDialog
from ui.ui_handler.acceptdialog import AcceptDialog

from ui.utils.layout import ClearFrame, AddToFrame
from ui.utils.version import GetLatest, GITHUB, REPO, VERSION, GIT_VERSION, PRERELEASE, GAMEBANANA
from ui.utils.textformater import TextFormatter
from ui.utils.mainthread import QExecMainThread
from ui.utils.config import LoaderConfig

from ui.ui_handler.settings import SettingsFrame
from ui.ui_handler.gamebanana import GameBananaFrame
import ui.ui_sources.translate as translate

def get_dir_size(path='.'):
    total = 0
    try:
        with os.scandir(path) as it:
            for entry in it:
                if entry.is_file():
                    total += entry.stat().st_size
                elif entry.is_dir():
                    total += get_dir_size(entry.path)
    except:
        pass
    return total

def format_size(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TB"


SUPPORT_URL = "https://www.patreon.com/bhmodloader"

PROGRAM_NAME = "Brawlhalla Mod Loader"


def InitWindowSetText(text):
    if getattr(sys, "frozen", False):
        try:
            import pyi_splash
            pyi_splash.update_text(text)
        except:
            pass

def restart_app():
    # Kill background children before restarting
    for proc in multiprocessing.active_children():
        proc.kill()
    os.execl(sys.executable, sys.executable, *sys.argv)


def InitWindowClose():
    if getattr(sys, "frozen", False):
        try:
            import pyi_splash
            pyi_splash.update_text("application")
            pyi_splash.close()
        except:
            pass


def TerminateApp(exitId=0):
    for proc in multiprocessing.active_children():
        proc.kill()
    os.kill(multiprocessing.current_process().pid, exitId)
    sys.exit(exitId)


class ImportQueue:
    def __init__(self):
        self.urlQueue = []
        self.signalUrl = None
        self._readUrlQueue = False

        self.fileQueue = []
        self.signalFile = None
        self._readFileQueue = False

    def setUrlSignal(self, signalUrl):
        self.signalUrl = signalUrl

    def _emitUrl(self):
        while True:
            try:
                if self.signalUrl is None:
                    time.sleep(0.1)
                else:
                    self.signalUrl.emit()
                    break
            except:
                time.sleep(0.1)

    def addUrl(self, url):
        self.urlQueue.append(url)

        if not self._readUrlQueue:
            threading.Thread(target=self._emitUrl).start()

    def iterUrl(self):
        self._readUrlQueue = True

        while self.urlQueue:
            yield self.urlQueue.pop(0)

        self._readUrlQueue = False

    def setFileSignal(self, signalFile):
        self.signalFile = signalFile

    def _emitFile(self):
        while True:
            try:
                if self.signalFile is None:
                    time.sleep(0.1)
                else:
                    self.signalFile.emit()
                    break
            except:
                time.sleep(0.1)

    def addFile(self, file):
        self.fileQueue.append(file)

        if not self._readFileQueue:
            threading.Thread(target=self._emitFile).start()

    def iterFile(self):
        self._readFileQueue = True

        while self.fileQueue:
            yield self.fileQueue.pop(0)

        self._readFileQueue = False


class ModLoader(QMainWindow):
    queueUrlSignal = Signal(str)
    queueFileSignal = Signal(str)
    brawlhallaNotFoundSignal = Signal()
    importQueue = ImportQueue()

    _local_base = (
        os.path.dirname(sys.executable)
        if getattr(sys, "frozen", False)
        else os.path.dirname(os.path.abspath(sys.argv[0]))
    )
    _local_mods = os.path.join(_local_base, "Mods")

    config = LoaderConfig()
    if config.modsPath:
        modsPath = config.modsPath
    else:
        modsPath = _local_mods
        os.makedirs(modsPath, exist_ok=True)

    errors: List[Notification] = []

    app = None

    def __init__(self):
        super().__init__()
        self.ui = Window()
        self.ui.setupUi(self)

        # Enable drag & drop on the main window
        self.setAcceptDrops(True)

        self.config = LoaderConfig()

        QExecMainThread.init(self)

        InitWindowSetText("ui")

        self.setWindowTitle(PROGRAM_NAME)
        self.setWindowIcon(QIcon(':/icons/resources/icons/App.ico'))

        self.loading = Loading()
        self.header = HeaderFrame(githubMethod=lambda: webbrowser.open(f"{GITHUB}/{REPO}"),
                                  supportMethod=lambda: webbrowser.open(SUPPORT_URL),
                                  infoMethod=self.showInformation)
        self.header.ui.gamebananaButton.setText("GameBanana (Beta)")
        self.mods = Mods(installMethod=self.installMod,
                         uninstallMethod=self.uninstallMod,
                         reinstallMethod=self.reinstallMod,
                         deleteMethod=self.deleteMod,
                         reloadMethod=self.reloadMods,
                         openFolderMethod=self.openModsFolder,
                         uninstallAllMethod=self.uninstallAllMods,
                         toggleFavoriteMethod=self.toggleFavorite,
                         sortCallback=self.updateSortState,
                         savePresetMethod=self.savePreset,
                         deletePresetMethod=self.deletePreset,
                         applyPresetMethod=self.applyPreset,
                         editPresetMethod=self.renamePreset,
                         reloadPresetMethod=self.applyPreset,
                         modsPath=self.modsPath,
                         controllerGetter=lambda: getattr(self, 'controller', None),
                         bulkInstallMethod=self.bulkInstallMods,
                         bulkUninstallMethod=self.bulkUninstallMods)



        self.progressDialog = ProgressDialog(self)
        self.buttonsDialog = ButtonsDialog(self)
        self.acceptDialog = AcceptDialog(self)
        
        # Temporary WIP flag for GameBanana browser
        GAMEBANANA_WIP = False
        
        if GAMEBANANA_WIP:
            self.gamebanana = WIPFrame("GameBanana Browser")
        else:
            self.gamebanana = GameBananaFrame(modsPath=self.modsPath)
            self.gamebanana.downloadMod.connect(self.handleGameBananaDownload, Qt.QueuedConnection)

        bhPath = "Not found"
        cacheSize = "0 B"
        if core and hasattr(core, 'worker') and hasattr(core.worker, 'brawlhalla'):
            bhPath = core.worker.brawlhalla.BRAWLHALLA_PATH or "Not found"
        if core and hasattr(core, 'MODLOADER_CACHE_PATH'):
            cacheSize = format_size(get_dir_size(core.MODLOADER_CACHE_PATH))

        self.settings = SettingsFrame(
            saveCallback=self.syncSettingsWithCore,
            openCacheMethod=self.openCacheFolder,
            clearCacheMethod=self.clearCache,
            bhPath=bhPath,
            modsPath=self.modsPath,
            cacheSize=cacheSize
        )
        self.bulkOperationCount = 0
        self.currentSortField = "Name"
        self.currentSortReverse = False
        self.reloadPending = False

        self.setLoadingScreen()

        # self.resize(QSize(977, 550))
        self.setMinimumSize(QSize(910, 550))

        self.header.setModsButtonPressed(lambda: self.checkUnsavedSettings(self.setModsScreen))
        self.header.setGamebananaButtonPressed(lambda: self.checkUnsavedSettings(self.setGamebananaScreen))
        self.header.setSettingsButtonPressed(self.setSettingsScreen)

        threading.Thread(target=self.checkNewVersion).start()

        self.queueUrlSignal.connect(self.queueUrl)
        self.queueFileSignal.connect(self.queueFile)
        self.brawlhallaNotFoundSignal.connect(self.showBrawlhallaNotFoundDialog)

        self.importQueue.setUrlSignal(self.queueUrlSignal)
        self.importQueue.setFileSignal(self.queueFileSignal)

        self.setForeground()

        self.controller = None
        if JAVA_FOUND:
            threading.Thread(target=self.runController).start()

            # Get core events
            self.controllerGetterTimer = QTimer()
            self.controllerGetterTimer.timeout.connect(self.controllerHandler)
            self.controllerGetterTimer.start(10)
        else:
            err_str = str(CORE_IMPORT_ERROR).lower() if CORE_IMPORT_ERROR else ""
            is_java_error = not CORE_IMPORT_ERROR or any(k in err_str for k in ["java not found", "_jpype", "jpype", "jvmnotfoundexception", "jvm"])
            if not is_java_error:
                message = f"Error importing core:\n\n{CORE_IMPORT_ERROR}\n\nPlease check your installation."
            else:
                message = ("Java Not Found!\n\n"
                           "Java 64-bit is required to run this application.\n\n"
                           "<b>1. Download & Install (If not installed):</b>\n"
                           "Download and install the <u>Windows Offline (64-bit)</u> version from:\n"
                           "<url=\"https://www.java.com/en/download/windows_manual.jsp\">"
                           "https://www.java.com/en/download/windows_manual.jsp</url>\n\n"
                           "<b>2. If already installed:</b>\n"
                           "Set <b>JAVA_HOME</b> as the variable name, and for the path, enter your Java installation directory "
                           "(e.g. <i>C:\\Program Files\\Java\\jre1.8.0_401</i>). Click OK and restart Brawlhalla Mod Loader.")
            self.showError("Fatal Error:", TextFormatter.format(message, 11), terminate=True)

        InitWindowClose()
        self.__class__.app = self

    def runController(self):
        self.loading.setText("Loading ModLoader Core")

        self.controller = core.Controller()
        self.controller.setModsPath(self.modsPath)
        
        # Sync custom brawlhalla path to core
        if self.config.brawlhallaPath:
            core.worker.config.ModloaderCoreConfig.customBrawlhallaPath = self.config.brawlhallaPath
            core.worker.config.ModloaderCoreConfig.save()
            if hasattr(core, 'worker') and hasattr(core.worker, 'brawlhalla'):
                core.worker.brawlhalla.BRAWLHALLA_PATH = self.config.brawlhallaPath
            
        if self.controller and hasattr(self.controller, 'reloadMods'):
            self.controller.reloadMods()
        self.controller.getModsData()

        # Check if Brawlhalla path was found
        bh_path = getattr(core.worker.brawlhalla, 'BRAWLHALLA_PATH', None) if (hasattr(core, 'worker') and hasattr(core.worker, 'brawlhalla')) else None
        if not bh_path or not os.path.exists(bh_path) or not os.path.isfile(os.path.join(bh_path, "Brawlhalla.exe")):
            QTimer.singleShot(500, self.brawlhallaNotFoundSignal.emit)

    def controllerHandler(self):
        if self.controller is None:
            return

        # Process up to 100 messages per tick to avoid overwhelming the UI
        processed = 0
        while self.controller.ready_to_receive and processed < 100:
            try:
                data = self.controller.getData()
                if data is None:
                    break
                self._processControllerData(data)
                processed += 1
            except Exception:
                break

    def _processControllerData(self, data):
        cmd = data[0]

        if cmd == Environment.Notification:
            notification: core.notifications.Notification = data[1]
            ntype = notification.notificationType

            if ntype == NotificationType.LoadingMod:
                modPath = notification.args[0]
                self.loading.setText(f"Loading mod '{modPath or 'from cache'}'")

            elif ntype == NotificationType.ModElementsCount:
                modHash, count = notification.args
                self.progressDialog.setMaximum(count)

            # Check conflicts
            elif ntype == NotificationType.ModConflictSearchInSwf:
                modHash, swfName = notification.args
                self.progressDialog.setContent(f"Searching in: {swfName}")
                self.progressDialog.addValue()
            elif ntype == NotificationType.ModConflictNotFound:
                modHash, = notification.args
                self.progressDialog.setValue(0)
                self.controller.installMod(modHash)
            elif ntype == NotificationType.ModConflict:
                modHash, modConflictHashes = notification.args
                self.progressDialog.hide()

                new_mod_name = self.mods.mods[modHash].name if modHash in self.mods.mods else "New Mod"
                conflicting_names = [self.mods.mods[h].name if h in self.mods.mods else f"Installed Mod ({h[:6]})" for h in modConflictHashes]

                from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QRadioButton, QButtonGroup, QPushButton, QHBoxLayout
                from PySide6.QtCore import Qt

                diag = QDialog(self)
                diag.setWindowTitle("Mod Conflict & Priority Order")
                diag.setMinimumWidth(440)
                diag.setStyleSheet("""
                    QDialog { background-color: #141518; color: #FFFFFF; }
                    QLabel { color: #FFFFFF; font-size: 12px; }
                    QRadioButton { color: #FFFFFF; font-size: 12px; font-weight: bold; spacing: 8px; }
                    QRadioButton::indicator { width: 16px; height: 16px; }
                    QPushButton { background-color: #24638C; color: #FFFFFF; border-radius: 4px; padding: 6px 16px; font-weight: bold; }
                    QPushButton:hover { background-color: #347BA9; }
                """)

                layout = QVBoxLayout(diag)
                layout.setSpacing(12)

                lbl_title = QLabel("Conflict Detected!")
                lbl_title.setStyleSheet("color: #FFA500; font-size: 15px; font-weight: bold;")
                layout.addWidget(lbl_title)

                lbl_desc = QLabel(f"The mod <b>'{new_mod_name}'</b> conflicts with: <i>{', '.join(conflicting_names)}</i>.<br><br><b>Choose priority order for conflicting files:</b>")
                lbl_desc.setWordWrap(True)
                layout.addWidget(lbl_desc)

                bg = QButtonGroup(diag)
                rb1 = QRadioButton(f"High Priority: '{new_mod_name}' (Overwrite installed mods)")
                rb1.setChecked(True)
                bg.addButton(rb1, 1)
                layout.addWidget(rb1)

                rb2 = QRadioButton(f"High Priority: Currently installed mod(s) (Keep installed mods)")
                bg.addButton(rb2, 2)
                layout.addWidget(rb2)

                btn_lay = QHBoxLayout()
                btn_ok = QPushButton("Apply Selected Priority")
                btn_cancel = QPushButton("Cancel")
                btn_cancel.setStyleSheet("background-color: #2A2C32;")
                btn_lay.addStretch()
                btn_lay.addWidget(btn_ok)
                btn_lay.addWidget(btn_cancel)
                layout.addLayout(btn_lay)

                btn_ok.clicked.connect(diag.accept)
                btn_cancel.clicked.connect(diag.reject)

                if diag.exec() == QDialog.Accepted:
                    if bg.checkedId() == 1:
                        # High Priority: New Mod -> Overwrite installed conflicting mods
                        self.controller.installMod(modHash)
                    else:
                        # High Priority: Installed Mod -> Install new mod first, then re-apply installed conflicting mods on top
                        self.controller.installMod(modHash)
                        for ch in modConflictHashes:
                            self.controller.installMod(ch)


            # Installing
            elif ntype == NotificationType.InstallingModSwf:
                modHash, swfName = notification.args
                self.progressDialog.setContent(f"Open game file: {swfName}")
            elif ntype == NotificationType.InstallingModSwfSprite:
                modHash, sprite = notification.args
                self.progressDialog.setContent(f"Installing sprite: {sprite}")
                self.progressDialog.addValue()
            elif ntype == NotificationType.InstallingModSwfSound:
                modHash, sound = notification.args
                self.progressDialog.setContent(f"Installing sound: {sound}")
                self.progressDialog.addValue()
            elif ntype == NotificationType.InstallingModFile:
                modHash, fileName = notification.args
                self.progressDialog.setContent(f"Installing file: {fileName}")
                self.progressDialog.addValue()
            elif ntype == NotificationType.InstallingModFileCache:
                modHash, fileName = notification.args
                self.progressDialog.setContent(fileName)
                self.progressDialog.addValue()
            elif ntype == NotificationType.InstallingModFinished:
                modHash = notification.args[0]
                modClass = self.mods.mods[modHash]
                modClass.installed = True
                
                # Update specific mod button UI
                for btn in self.mods.modsButtons:
                    if btn.modClass.hash == modHash:
                        btn.updateData()
                        break
                
                # Update main view if it's the selected one
                if self.mods.selectedModButton and self.mods.selectedModButton.modClass.hash == modHash:
                    self.mods.updateData()
                
                if hasattr(self, 'bulkTotalCount') and self.bulkTotalCount > 0:
                    self.bulkCompletedCount += 1
                    self.progressDialog.setValue(self.bulkCompletedCount)
                    self.progressDialog.setContent(f"Applying preset mods ({self.bulkCompletedCount}/{self.bulkTotalCount})...")

                if self.bulkOperationCount > 0:
                    self.bulkOperationCount -= 1
                    
                if self.bulkOperationCount <= 0:
                    self.bulkTotalCount = 0
                    self.bulkCompletedCount = 0
                    self.progressDialog.hide()
                    if hasattr(self, 'currentPresetAppliedName') and self.currentPresetAppliedName:
                        pname = self.currentPresetAppliedName
                        self.currentPresetAppliedName = None
                        self.buttonsDialog.setTitle("Preset Synced")
                        self.buttonsDialog.setContent(TextFormatter.format(f"Mod preset <b>'{pname}'</b> has been loaded and synced successfully!", 11))
                        self.buttonsDialog.setButtons([("OK", self.buttonsDialog.hide)])
                        self.buttonsDialog.show()
                    
                if self.currentSortField == "Installed":
                    self.mods.applySort(self.currentSortField, self.currentSortReverse)
                    
                self.showErrorNotifications()

            # Uninstalling
            elif ntype == NotificationType.UninstallingModSwf:
                modHash, swfName = notification.args
                self.progressDialog.setContent(swfName)
            elif ntype == NotificationType.UninstallingModSwfSprite:
                modHash, sprite = notification.args
                self.progressDialog.setContent(sprite)
                self.progressDialog.addValue()
            elif ntype == NotificationType.UninstallingModSwfSound:
                modHash, sprite = notification.args
                self.progressDialog.setContent(sprite)
                self.progressDialog.addValue()
            elif ntype == NotificationType.UninstallingModFile:
                modHash, fileName = notification.args
                self.progressDialog.setContent(fileName)
                self.progressDialog.addValue()
            elif ntype == NotificationType.UninstallingModFinished:
                modHash = notification.args[0]
                modClass = self.mods.mods[modHash]
                modClass.installed = False
                
                # Update specific mod button UI
                for btn in self.mods.modsButtons:
                    if btn.modClass.hash == modHash:
                        btn.updateData()
                        break
                
                # Update main view if it's the selected one
                if self.mods.selectedModButton and self.mods.selectedModButton.modClass.hash == modHash:
                    self.mods.updateData()

                if hasattr(self, 'bulkTotalCount') and self.bulkTotalCount > 0:
                    self.bulkCompletedCount += 1
                    self.progressDialog.setValue(self.bulkCompletedCount)
                    self.progressDialog.setContent(f"Applying preset mods ({self.bulkCompletedCount}/{self.bulkTotalCount})...")

                if self.bulkOperationCount > 0:
                    self.bulkOperationCount -= 1
                    
                if self.bulkOperationCount <= 0:
                    self.bulkTotalCount = 0
                    self.bulkCompletedCount = 0
                    self.progressDialog.hide()
                    if hasattr(self, 'currentPresetAppliedName') and self.currentPresetAppliedName:
                        pname = self.currentPresetAppliedName
                        self.currentPresetAppliedName = None
                        self.buttonsDialog.setTitle("Preset Synced")
                        self.buttonsDialog.setContent(TextFormatter.format(f"Mod preset <b>'{pname}'</b> has been loaded and synced successfully!", 11))
                        self.buttonsDialog.setButtons([("OK", self.buttonsDialog.hide)])
                        self.buttonsDialog.show()
                    
                if self.currentSortField == "Installed":
                    self.mods.applySort(self.currentSortField, self.currentSortReverse)
                    
                self.showErrorNotifications()

            elif ntype in [NotificationType.CompileModSourcesSpriteHasNoSymbolclass,  # Compiler
                           NotificationType.CompileModSourcesSpriteEmpty,
                           NotificationType.CompileModSourcesSpriteNotFoundInFolder,
                           NotificationType.CompileModSourcesUnsupportedCategory,
                           NotificationType.CompileModSourcesUnknownFile,
                           NotificationType.CompileModSourcesSaveError,
                           NotificationType.CompileModSourcesDefectivePiece,
                           NotificationType.CompileModSourcesDuplicateSpriteId,
                           NotificationType.CompileModSourcesGeneralError,
                           NotificationType.LoadingModIsEmpty,  # Loader
                           NotificationType.InstallingModNotFoundFileElement,  # Installer
                           NotificationType.InstallingModNotFoundGameSwf,
                           NotificationType.InstallingModSwfScriptError,
                           NotificationType.InstallingModSwfSoundSymbolclassNotExist,
                           NotificationType.InstallingModSoundNotExist,
                           NotificationType.InstallingModSwfSpriteSymbolclassNotExist,
                           NotificationType.InstallingModSpriteNotExist,
                           NotificationType.UninstallingModSwfOriginalElementNotFound,  # Uninstaller
                           NotificationType.UninstallingModSwfElementNotFound]:
                self.errors.append(notification)
                if ntype in [NotificationType.CompileModSourcesDefectivePiece, NotificationType.CompileModSourcesDuplicateSpriteId, NotificationType.CompileModSourcesGeneralError]:
                    self.showErrorNotifications()

            elif ntype == NotificationType.FatalError:
                self.showError("Fatal Error:", notification.args[0])

        elif cmd == Environment.ReloadMods:
            FlowTracer.new_session("Environment.ReloadMods received from Core")
            FlowTracer.log("Environment.ReloadMods", f"Count mods: {len(self.mods.mods)}")
            self.mods.removeAllMods()

        elif cmd == Environment.GetModsData:
            FlowTracer.log("Environment.GetModsData", f"Received {len(data[1])} mods from Core")
            for modData in data[1]:
                self.mods.addMod(gameVersion=modData.get("gameVersion", ""),
                                 name=modData.get("name", ""),
                                 author=modData.get("author", ""),
                                 version=modData.get("version", ""),
                                 description=modData.get("description", ""),
                                 tags=modData.get("tags", []),
                                 previewsPaths=modData.get("previewsPaths", []),
                                 hash=modData.get("hash", ""),
                                 platform=modData.get("platform", ""),
                                 installed=modData.get("installed", False),
                                 currentVersion=modData.get("currentVersion", False),
                                 modFileExist=modData.get("modFileExist", False),
                                 date=modData.get("date", 0.0),
                                 favorite=modData.get("hash", "") in self.config.favorites,
                                 swfNames=modData.get("swfNames", []),
                                 fileNames=modData.get("fileNames", []),
                                 spriteNames=modData.get("spriteNames", []),
                                 modPath=modData.get("modPath", ""))

            FlowTracer.log("applySort_start", "At end of GetModsData")
            self.mods.applySort(self.currentSortField, self.currentSortReverse)
            FlowTracer.log("applySort_end", "Finished applySort in GetModsData")
            self.setModsScreen()
            self.showErrorNotifications()


        elif cmd == Environment.GetModConflict:
            searching, modHash = data[1]
            if searching:
                modClass = self.mods.mods[modHash]
                self.progressDialog.setTitle(f"Searching conflicts '{modClass.name}'...")
                self.progressDialog.setContent("Searching...")
                self.progressDialog.show()

        elif cmd == Environment.InstallMod:
            installing, modHash = data[1]
            if installing:
                modClass = self.mods.mods[modHash]
                self.progressDialog.setTitle(f"Installing mod '{modClass.name}'...")
                self.progressDialog.setContent("Loading mod...")
                self.progressDialog.show()

        elif cmd == Environment.UninstallMod:
            uninstalling, modHash = data[1]
            if uninstalling:
                modClass = self.mods.mods[modHash]
                self.progressDialog.setTitle(f"Uninstalling mod '{modClass.name}'...")
                self.progressDialog.setContent("")
                self.progressDialog.show()

        elif cmd == Environment.DeleteMod:
            pass

        elif cmd == Environment.SetModsPath:
            pass

        else:
            print(f"Controller <- {str(data)}\n", end="")

    def showErrorNotifications(self):
        if self.errors:
            import re
            errors = []
            errorsNotifications = self.errors.copy()
            self.errors.clear()

            for notif in errorsNotifications:
                ntype = notif.notificationType
                string = ""

                mod_hash = notif.args[0] if notif.args and isinstance(notif.args[0], str) else None
                mod_is_ex = False
                if mod_hash and hasattr(self, 'mods') and mod_hash in self.mods.mods:
                    mod_is_ex = bool(re.search(r'\bEX\b', self.mods.mods[mod_hash].name, re.IGNORECASE))

                if mod_is_ex and ntype in [
                    NotificationType.InstallingModNotFoundGameSwf,
                    NotificationType.InstallingModNotFoundFileElement,
                    NotificationType.InstallingModSwfSoundSymbolclassNotExist,
                    NotificationType.InstallingModSoundNotExist,
                    NotificationType.InstallingModSwfSpriteSymbolclassNotExist,
                    NotificationType.InstallingModSpriteNotExist
                ]:
                    continue

                # Loader
                if ntype == NotificationType.LoadingModIsEmpty:
                    string = f"Mod '{notif.args[1]}' is empty"

                # Installer
                elif ntype == NotificationType.InstallingModNotFoundFileElement:
                    string = f"Not found element '{notif.args[1]}' in bmod "

                elif ntype == NotificationType.InstallingModNotFoundGameSwf:
                    string = f"Not found game file '{notif.args[1]}'"

                elif ntype == NotificationType.InstallingModSwfScriptError:
                    string = f"Script '{notif.args[1]}' not installed"

                elif ntype == NotificationType.InstallingModSwfSoundSymbolclassNotExist:
                    string = f"Not found sound '{notif.args[1]}' in '{notif.args[2]}'"

                elif ntype == NotificationType.InstallingModSoundNotExist:
                    string = f"Not found sound '{notif.args[1]} ({notif.args[2]})' in '{notif.args[3]}'"

                elif ntype == NotificationType.InstallingModSwfSpriteSymbolclassNotExist:
                    string = f"Not found sprite '{notif.args[1]}' in '{notif.args[2]}'"

                elif ntype == NotificationType.InstallingModSpriteNotExist:
                    string = f"Not found sprite '{notif.args[1]} ({notif.args[2]})' in mod file"

                # Uninstaller
                elif ntype == NotificationType.UninstallingModSwfOriginalElementNotFound:
                    string = f"Not found orig element '{notif.args[1]}' in '{notif.args[2]}'"

                elif ntype == NotificationType.UninstallingModSwfElementNotFound:
                    string = f"Not found mod element '{notif.args[1]}' in '{notif.args[2]}'"

                elif ntype == NotificationType.CompileModSourcesDefectivePiece:
                    sprite = notif.args[1]
                    element_id = notif.args[2]
                    string = (f"There is a defective piece in the mod, please delete it and try again.\n\n"
                             f"The defective piece is: {sprite} (Element ID: {element_id})")

                elif ntype == NotificationType.CompileModSourcesDuplicateSpriteId:
                    sprite_id = notif.args[1]
                    sprite1 = notif.args[2]
                    sprite2 = notif.args[3]
                    string = (f"There is a conflict because two sprites share the same ID number.\n\n"
                              f"Duplicate ID: {sprite_id}\n"
                              f"Found in: '{sprite1}' and '{sprite2}'\n"
                              f"Please change the ID of one of them and try again.")

                elif ntype == NotificationType.CompileModSourcesGeneralError:
                    error_msg = notif.args[1]
                    # traceback_str = notif.args[2]
                    string = f"An error occurred during compilation: {error_msg}"

                if string:
                    errors.append(string)
                else:
                    errors.append(repr(notif))

            if errors:
                string = ""
                for error in errors:
                    string += f"{error}\n"

                self.showError("Errors:", string)

    @QExecMainThread
    def showError(self, title, content, action=None, terminate=False):
        self.buttonsDialog.setTitle(title)

        if self.acceptDialog.isShown():
            self.acceptDialog.hide()

        if self.buttonsDialog.isShown():
            self.buttonsDialog.hide()

        if self.progressDialog.isShown():
            self.progressDialog.hide()

        if action is None:
            action = self.buttonsDialog.hide

        if terminate:
            action = TerminateApp

        # If it's a long traceback, show a shorter summary and keep the full one for the button
        display_content = content
        if "Traceback (most recent call last):" in content:
            lines = content.strip().split("\n")
            # Extract the last few lines (the actual error)
            display_content = "An unexpected error occurred during the operation.\n\n" + "\n".join(lines[-2:])

        self.buttonsDialog.setContent(display_content)
        self.buttonsDialog.setButtons([("Copy Error", lambda: self.copyToClipboard(f"{title}\n\n{content}")),
                                       ("Ok", action)])
        self.buttonsDialog.show()

    def checkGameRunning(self):
        try:
            # Try multiple process names to be sure
            for proc_name in ["Brawlhalla.exe", "Brawlhalla64.exe"]:
                output = subprocess.check_output(f'tasklist /FI "IMAGENAME eq {proc_name}" /NH', 
                                                 shell=True, 
                                                 creationflags=subprocess.CREATE_NO_WINDOW).decode(errors='ignore').lower()
                if proc_name.lower() in output:
                    self.showError("Game is running!", 
                                   "Brawlhalla is currently running. Please close the game before installing or uninstalling mods.")
                    return True
        except Exception as e:
            print(f"[DEBUG] checkGameRunning error: {e}")
        return False

    def copyToClipboard(self, text):
        cb = QApplication.clipboard()
        cb.clear(mode=QClipboard.Mode.Clipboard)
        cb.setText(text, mode=QClipboard.Mode.Clipboard)

    def setLoadingScreen(self):
        ClearFrame(self.ui.mainFrame)
        AddToFrame(self.ui.mainFrame, self.loading)
        self.loading.setText("Loading mods sources...")

    def setModsScreen(self):
        self.header.ui.modsButton.setChecked(True)
        self.header.ui.gamebananaButton.setChecked(False)
        self.header.ui.settingsButton.setChecked(False)
        self.header.ui.modsLine.show()
        self.header.ui.gamebananaLine.hide()
        self.header.ui.settingsLine.hide()

        ClearFrame(self.ui.mainFrame)
        AddToFrame(self.ui.mainFrame, self.header)
        AddToFrame(self.ui.mainFrame, self.mods)
        if self.reloadPending:
            self.setLoadingScreen()
            # Refresh the list of installed mods in the browser
            if hasattr(self, 'gamebanana'):
                self.gamebanana.update_installed_mods(self.getInstalledModNames())
            self.reloadMods()
            self.reloadPending = False

    def setGamebananaScreen(self):
        self.header.ui.modsButton.setChecked(False)
        self.header.ui.gamebananaButton.setChecked(True)
        self.header.ui.settingsButton.setChecked(False)
        self.header.ui.modsLine.hide()
        self.header.ui.gamebananaLine.show()
        self.header.ui.settingsLine.hide()

        ClearFrame(self.ui.mainFrame)
        AddToFrame(self.ui.mainFrame, self.header)
        AddToFrame(self.ui.mainFrame, self.gamebanana)

    def setSettingsScreen(self):
        self.header.ui.modsButton.setChecked(False)
        self.header.ui.gamebananaButton.setChecked(False)
        self.header.ui.settingsButton.setChecked(True)
        self.header.ui.modsLine.hide()
        self.header.ui.gamebananaLine.hide()
        self.header.ui.settingsLine.show()

        ClearFrame(self.ui.mainFrame)
        AddToFrame(self.ui.mainFrame, self.header)
        AddToFrame(self.ui.mainFrame, self.settings)

    def checkUnsavedSettings(self, nextScreenMethod):
        if self.settings.hasUnsavedChanges:
            self.acceptDialog.setTitle("Unsaved Changes")
            self.acceptDialog.setContent("Save the settings before changing tab!")
            self.acceptDialog.ui.accept.setText("Save")
            self.acceptDialog.ui.cancel.setText("Discard")
            
            def saveAndContinue():
                self.settings.saveSettings()
                self.acceptDialog.hide()
                nextScreenMethod()
            
            def discardAndContinue():
                self.settings.hasUnsavedChanges = False
                self.acceptDialog.hide()
                nextScreenMethod()
                
            self.acceptDialog.setAccept(saveAndContinue)
            self.acceptDialog.setCancel(discardAndContinue)
            self.acceptDialog.show()
        else:
            nextScreenMethod()

    def syncSettingsWithCore(self):
        # Update paths if they changed
        if self.config.modsPath:
            self.modsPath = self.config.modsPath
        else:
            self.modsPath = self._local_mods
            os.makedirs(self.modsPath, exist_ok=True)

        if self.controller:
            self.controller.setModsPath(self.modsPath)
            
            if self.config.brawlhallaPath:
                core.worker.config.ModloaderCoreConfig.customBrawlhallaPath = self.config.brawlhallaPath
                core.worker.config.ModloaderCoreConfig.save()

    def openCacheFolder(self):
        os.startfile(core.MODLOADER_CACHE_PATH)

    def uninstallAllMods(self):
        if self.checkGameRunning():
            return
            
        installed_mods = [btn for btn in self.mods.modsButtons if btn.modClass.installed]
        if not installed_mods:
            return
            
        self.acceptDialog.setTitle("Uninstall All")
        self.acceptDialog.setContent(f"Are you sure you want to uninstall all {len(installed_mods)} installed mods?")
        self.acceptDialog.ui.accept.setText("Uninstall All")
        self.acceptDialog.ui.cancel.setText("Cancel")
        self.acceptDialog.setAccept(lambda: self._doUninstallAll(installed_mods))
        self.acceptDialog.show()

    def _doUninstallAll(self, mods_to_uninstall):
        self.acceptDialog.hide()
        self.bulkOperationCount = len(mods_to_uninstall)
        for modButton in mods_to_uninstall:
            self.uninstallMod(modButton)

    def bulkInstallMods(self, hashes: List[str]):
        if not hashes:
            return
        if hasattr(self, 'controller') and self.controller:
            self.bulkTotalCount = len(hashes)
            self.bulkCompletedCount = 0
            self.bulkOperationCount = len(hashes)
            self.progressDialog.setMaximum(len(hashes))
            self.progressDialog.setValue(0)
            self.progressDialog.setTitle(f"Installing {len(hashes)} mods...")
            self.progressDialog.setContent("Starting...")
            self.progressDialog.show()
            for h in hashes:
                self.controller.getModConflict(h)

    def bulkUninstallMods(self, hashes: List[str]):
        if not hashes:
            return
        if hasattr(self, 'controller') and self.controller:
            self.bulkTotalCount = len(hashes)
            self.bulkCompletedCount = 0
            self.bulkOperationCount = len(hashes)
            self.progressDialog.setMaximum(len(hashes))
            self.progressDialog.setValue(0)
            self.progressDialog.setTitle(f"Uninstalling {len(hashes)} mods...")
            self.progressDialog.setContent("Starting...")
            self.progressDialog.show()
            for h in hashes:
                self.controller.uninstallMod(h)


    def clearCache(self):
        self.acceptDialog.setTitle("Clear Cache")
        self.acceptDialog.setContent(
            "Clearing the cache may cause problems, especially if you already have mods installed.\n\n"
            "It is recommended to uninstall mods first before clearing the cache.\n\n"
            "The application will CLOSE after clearing the cache. You must reopen it manually.\n\n"
            "Are you sure you want to clear the cache?"
        )
        self.acceptDialog.ui.accept.setText("Clear")
        self.acceptDialog.ui.cancel.setText("Cancel")
        self.acceptDialog.setAccept(self._doClearCache)
        self.acceptDialog.setCancel(self.acceptDialog.hide)
        self.acceptDialog.show()

    def savePreset(self, name: str):
        if not name:
            return
        installed_hashes = [m.hash for m in self.mods.mods.values() if m.installed]
        presets = dict(self.config.presets)
        presets[name] = installed_hashes
        self.config.presets = presets
        self.mods.loadPresetsList()
        # Automatically select the newly saved preset in the combo box
        idx = self.mods.presetCombo.findText(name)
        if idx >= 0:
            self.mods.presetCombo.blockSignals(True)
            self.mods.presetCombo.setCurrentIndex(idx)
            self.mods.presetCombo.blockSignals(False)

        self.buttonsDialog.setTitle("Preset Saved")
        self.buttonsDialog.setContent(TextFormatter.format(f"Mod preset <b>'{name}'</b> has been saved successfully with current installed mods!", 11))
        self.buttonsDialog.setButtons([("OK", self.buttonsDialog.hide)])
        self.buttonsDialog.show()

    def renamePreset(self, old_name: str, new_name: str):
        if not old_name or not new_name or old_name == new_name:
            return
        presets = dict(self.config.presets)
        if old_name in presets:
            presets[new_name] = presets.pop(old_name)
            self.config.presets = presets
            self.mods.loadPresetsList()
            idx = self.mods.presetCombo.findText(new_name)
            if idx >= 0:
                self.mods.presetCombo.blockSignals(True)
                self.mods.presetCombo.setCurrentIndex(idx)
                self.mods.presetCombo.blockSignals(False)

    def deletePreset(self, name: str):
        presets = dict(self.config.presets)
        if name in presets:
            del presets[name]
            self.config.presets = presets
            self.mods.loadPresetsList()

    def applyPreset(self, name: str):
        if self.checkGameRunning():
            return
        presets = self.config.presets
        if name not in presets:
            return
        target_hashes = set(presets[name])

        initial_installed = set(modHash for modHash, mod in self.mods.mods.items() if mod.installed)

        missing_mods = []
        valid_preset_hashes = set()
        for modHash in target_hashes:
            if modHash in self.mods.mods:
                mod = self.mods.mods[modHash]
                if not mod.modFileExist:
                    missing_mods.append(mod.name)
                else:
                    valid_preset_hashes.add(modHash)
            else:
                missing_mods.append(f"Unknown Mod ({modHash[:8]}...)")

        if missing_mods:
            from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout

            diag = QDialog(self)
            diag.setWindowTitle("Missing Mod File Interruption")
            diag.setMinimumWidth(450)
            diag.setStyleSheet("""
                QDialog { background-color: #141518; color: #FFFFFF; }
                QLabel { color: #FFFFFF; font-size: 12px; }
                QPushButton { background-color: #24638C; color: #FFFFFF; border-radius: 4px; padding: 6px 16px; font-weight: bold; }
                QPushButton:hover { background-color: #347BA9; }
            """)

            layout = QVBoxLayout(diag)
            layout.setSpacing(12)

            lbl_title = QLabel("Missing Mod Files Detected!")
            lbl_title.setStyleSheet("color: #FFA500; font-size: 15px; font-weight: bold;")
            layout.addWidget(lbl_title)

            msg_text = "The following mod(s) in this preset were deleted or moved from your disk:<br><ul>"
            for mm in missing_mods:
                msg_text += f"<li><b>{mm}</b></li>"
            msg_text += "</ul><br><b>Choose an action:</b>"

            lbl_desc = QLabel(msg_text)
            lbl_desc.setWordWrap(True)
            layout.addWidget(lbl_desc)

            btn_lay = QHBoxLayout()
            btn_continue = QPushButton("Skip Missing & Continue")
            btn_cancel = QPushButton("Cancel & Rollback")
            btn_cancel.setStyleSheet("background-color: #5C2626;")
            btn_lay.addStretch()
            btn_lay.addWidget(btn_continue)
            btn_lay.addWidget(btn_cancel)
            layout.addLayout(btn_lay)

            btn_continue.clicked.connect(diag.accept)
            btn_cancel.clicked.connect(diag.reject)

            if diag.exec_() == QDialog.Accepted:
                self._doApplyPreset(name, valid_preset_hashes, initial_installed)
            else:
                print(f"[PRESET] Preset apply cancelled by user due to missing mods.")
                return
        else:
            self._doApplyPreset(name, target_hashes, initial_installed)

    def _doApplyPreset(self, name: str, target_hashes: set, initial_installed: set = None):
        mods_to_uninstall = [modHash for modHash, mod in self.mods.mods.items() if mod.installed and modHash not in target_hashes]
        mods_to_install = [modHash for modHash in target_hashes if modHash in self.mods.mods and not self.mods.mods[modHash].installed and self.mods.mods[modHash].modFileExist]

        total_ops = len(mods_to_uninstall) + len(mods_to_install)
        if total_ops == 0:
            self.buttonsDialog.setTitle("Preset Synced")
            self.buttonsDialog.setContent(TextFormatter.format(f"Mod preset <b>'{name}'</b> is already active and fully synced!", 11))
            self.buttonsDialog.setButtons([("OK", self.buttonsDialog.hide)])
            self.buttonsDialog.show()
            return

        self.currentPresetAppliedName = name
        self.bulkTotalCount = total_ops
        self.bulkCompletedCount = 0
        self.bulkOperationCount = total_ops

        self.progressDialog.setMaximum(total_ops)
        self.progressDialog.setValue(0)
        self.progressDialog.setTitle(f"Applying Preset '{name}'")
        self.progressDialog.setContent(f"Applying preset mods (0/{total_ops})...")
        self.progressDialog.show()

        for modHash in mods_to_uninstall:
            self.controller.uninstallMod(modHash)

        for modHash in mods_to_install:
            self.controller.installMod(modHash)

    def _doClearCache(self):
        import shutil
        try:
            # Delete everything inside MODLOADER_CACHE_PATH except core.*, config_*, files.json, and association files
            for filename in os.listdir(core.MODLOADER_CACHE_PATH):
                file_path = os.path.join(core.MODLOADER_CACHE_PATH, filename)
                try:
                    # Protection list
                    if any([
                        filename.startswith("core."),
                        filename.startswith("config_"),
                        filename == "files.json",
                        filename.endswith(".ico"),
                        filename.endswith(".png"),
                        filename.endswith(".reg")
                    ]):
                        continue
                        
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    print(f'Failed to delete {file_path}. Reason: {e}')
            
            # Recreate necessary folders
            os.makedirs(os.path.join(core.MODLOADER_CACHE_PATH, "OriginalFiles"), exist_ok=True)
            
            self.buttonsDialog.setTitle("Cache Cleared")
            self.buttonsDialog.setContent("The application cache has been cleared. The app will now close.")
            self.buttonsDialog.setButtons([("Ok", TerminateApp)])
            self.buttonsDialog.show()
        except Exception as e:
            self.showError("Error clearing cache", str(e))
        finally:
            self.acceptDialog.hide()

    def showInformation(self):
        self.buttonsDialog.setTitle("About")

        string = TextFormatter.table([["Product:", PROGRAM_NAME],
                                      ["Version:", VERSION],
                                      ["GitHub tag:", GIT_VERSION or "None"],
                                      ["Status:", 'Beta' if PRERELEASE else 'Release'],
                                      ["Core version:", CORE_VERSION],
                                      ["Homepage:", f"<url=\"{GITHUB}/{REPO}\">{GITHUB}/{REPO}</url>"],
                                      [None, f"<url=\"{GAMEBANANA}\">{GAMEBANANA}</url>"],
                                      ["Author:", "I_FabrizioG_I"],
                                      ["Maintainers:", "LordShadow505 & Bucccket"],
                                      ["Modhalla Discord:", f"<url=\"https://discord.gg/ctzYZxBHgY\">https://discord.gg/ctzYZxBHgY</url>"]], newLine=False)

        self.buttonsDialog.setContent(TextFormatter.format(string, 11))
        self.buttonsDialog.setButtons([("Ok", self.buttonsDialog.hide)])
        self.buttonsDialog.show()

    def showBrawlhallaNotFoundDialog(self):
        message = (
            "Brawlhalla Path Not Found!\n\n"
            "The location of <b>Brawlhalla.exe</b> could not be detected automatically.\n\n"
            "Please click <b>'Select Path'</b> to locate your <i>Brawlhalla.exe</i> or installation folder.\n\n"
            "<b>Note:</b>\n"
            "• You can also set or change the Brawlhalla path anytime in <b>Settings</b>.\n"
            "• If you cancel, the application will still load, but mods <u>cannot be installed</u> until 'Brawlhalla.exe' is selected."
        )
        self.acceptDialog.setTitle("Brawlhalla Path Not Found")
        self.acceptDialog.setContent(TextFormatter.format(message, 11))
        self.acceptDialog.ui.accept.setText("Select Path")
        self.acceptDialog.ui.cancel.setText("Cancel")
        self.acceptDialog.setAccept(self._browseBrawlhallaPath)
        self.acceptDialog.setCancel(self.acceptDialog.hide)
        self.acceptDialog.show()

    def _browseBrawlhallaPath(self):
        self.acceptDialog.hide()
        from PySide6.QtWidgets import QFileDialog

        initial_dir = self.config.brawlhallaPath if (self.config.brawlhallaPath and os.path.exists(self.config.brawlhallaPath)) else "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Brawlhalla"

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Brawlhalla.exe or Installation Folder",
            initial_dir,
            "Brawlhalla Executable (Brawlhalla.exe *.exe);;All Files (*)"
        )

        if not file_path:
            return

        folder = os.path.dirname(file_path) if os.path.isfile(file_path) else file_path

        if os.path.exists(folder) and (os.path.isfile(os.path.join(folder, "Brawlhalla.exe")) or "Brawlhalla.exe" in os.listdir(folder)):
            self.config.brawlhallaPath = folder
            self.config.save()
            if hasattr(core, 'worker') and hasattr(core.worker, 'config'):
                core.worker.config.ModloaderCoreConfig.customBrawlhallaPath = folder
                core.worker.config.ModloaderCoreConfig.save()
            if hasattr(core, 'worker') and hasattr(core.worker, 'brawlhalla'):
                core.worker.brawlhalla.BRAWLHALLA_PATH = folder
                
            if hasattr(self, 'controller') and self.controller and hasattr(self.controller, 'reloadMods'):
                self.controller.reloadMods()
        else:
            err_msg = (
                "Invalid Brawlhalla Path!\n\n"
                f"The selected directory:\n<b>{folder}</b>\n\n"
                "Does not contain <b>Brawlhalla.exe</b>. Please select the folder containing Brawlhalla.exe."
            )
            self.acceptDialog.setTitle("Invalid Path")
            self.acceptDialog.setContent(TextFormatter.format(err_msg, 11))
            self.acceptDialog.ui.accept.setText("Try Again")
            self.acceptDialog.ui.cancel.setText("Cancel")
            self.acceptDialog.setAccept(self.showBrawlhallaNotFoundDialog)
            self.acceptDialog.setCancel(self.acceptDialog.hide)
            self.acceptDialog.show()

    def installMod(self, modTarget=None):
        bh_path = getattr(core.worker.brawlhalla, 'BRAWLHALLA_PATH', None) if (hasattr(core, 'worker') and hasattr(core.worker, 'brawlhalla')) else None
        if not bh_path or not os.path.exists(bh_path) or not os.path.isfile(os.path.join(bh_path, "Brawlhalla.exe")):
            self.showBrawlhallaNotFoundDialog()
            return

        if self.checkGameRunning():
            return

        targetHash = None
        if isinstance(modTarget, str):
            targetHash = modTarget
        elif hasattr(modTarget, 'modClass'):
            targetHash = modTarget.modClass.hash
        elif hasattr(modTarget, 'hash'):
            targetHash = modTarget.hash
        elif self.mods.selectedModButton is not None:
            targetHash = self.mods.selectedModButton.modClass.hash

        if targetHash:
            if self.bulkOperationCount <= 0:
                self.bulkOperationCount = 1
            self.controller.getModConflict(targetHash)

    def toggleFavorite(self, modHash):
        favorites = self.config.favorites.copy()
        if modHash in favorites:
            favorites.remove(modHash)
        else:
            favorites.append(modHash)
        self.config.favorites = favorites
        
        # Trigger re-sort using CURRENT sort settings
        self.mods.applySort(self.currentSortField, self.currentSortReverse)

    def uninstallMod(self, modButton=None):
        if self.checkGameRunning():
            return

        modHash = None
        if isinstance(modButton, str):
            modHash = modButton
        elif hasattr(modButton, 'modClass'):
            modHash = modButton.modClass.hash
        elif hasattr(modButton, 'hash'):
            modHash = modButton.hash
        elif self.mods.selectedModButton is not None:
            modHash = self.mods.selectedModButton.modClass.hash

        if modHash:
            if self.bulkOperationCount <= 0:
                self.bulkOperationCount = 1
            self.controller.uninstallMod(modHash)

    def reinstallMod(self):
        if self.checkGameRunning():
            return
            
        if self.mods.selectedModButton is not None:
            modClass = self.mods.selectedModButton.modClass
            self.controller.uninstallMod(modClass.hash)
            self.controller.getModConflict(modClass.hash)

    def deleteMod(self):
        if self.mods.selectedModButton is not None:
            modClass = self.mods.selectedModButton.modClass

            self.buttonsDialog.deleteButtons()
            self.buttonsDialog.setTitle(f"Delete mod '{modClass.name}'")

            if modClass.installed:
                self.buttonsDialog.setContent("To delete mod, you need to uninstall it")
            else:
                self.buttonsDialog.setContent("")
                self.buttonsDialog.addButton("Delete", self._deleteMod)

            self.buttonsDialog.addButton("Cancel", self.buttonsDialog.hide)

            self.buttonsDialog.show()

    def getInstalledModNames(self):
        names = []
        try:
            # Current UI names
            for i in range(self.mods.ui.modsLayout.count()):
                item = self.mods.ui.modsLayout.itemAt(i)
                if item and item.widget():
                    w = item.widget()
                    if hasattr(w, 'modClass'):
                        names.append(w.modClass.name)
            
            # Plus files/folders in mods folder (for immediate feedback before reload)
            if os.path.exists(self.modsPath):
                for item in os.listdir(self.modsPath):
                    # Remove extensions for better matching with GB names
                    base = os.path.splitext(item)[0]
                    names.append(base)
                    names.append(item)
        except: pass
        return list(set(names))

    def reloadMods(self):
        self.setLoadingScreen()
        if self.controller:
            self.controller.reloadMods()
            self.controller.getModsData()

    def updateSortState(self, field, reverse):
        self.currentSortField = field
        self.currentSortReverse = reverse

    def openModsFolder(self):
        os.startfile(self.modsPath)

    def _deleteMod(self):
        modClass = self.mods.selectedModButton.modClass
        modClass.modFileExist = False
        self.controller.deleteMod(modClass.hash)
        self.reloadMods()
        self.buttonsDialog.hide()

    def resizeEvent(self, event):
        self.progressDialog.onResize()
        self.acceptDialog.onResize()
        self.buttonsDialog.onResize()
        super().resizeEvent(event)

    @QExecMainThread
    def newVersion(self, url: str, fileUrl: str, version: str, body: str):
        self.buttonsDialog.setTitle(f"New version available '{version}'")
        self.buttonsDialog.setContent(TextFormatter.format(body, 11))
        self.buttonsDialog.deleteButtons()
        self.buttonsDialog.addButton("GO TO SITE", lambda: webbrowser.open(url))
        self.buttonsDialog.addButton("UPDATE", lambda: [self.buttonsDialog.hide(),
                                                        self.updateApp(fileUrl, version)])
        self.buttonsDialog.addButton("CANCEL", self.buttonsDialog.hide)
        self.buttonsDialog.show()

    def handleUpdateApp(self, blocknum, blocksize, totalsize):
        readedData = blocknum * blocksize

        if totalsize > 0:
            downloadPercentage = int(readedData * 100 / totalsize)
            self.progressDialog.setValue(downloadPercentage)
            if hasattr(self, 'gamebanana'):
                self.gamebanana.set_download_progress(downloadPercentage, f"Downloading... {downloadPercentage}%")
            QApplication.processEvents()

    def updateApp(self, fileUrl: str, version: str):
        filePath = os.path.join(os.getcwd(), "temp.exe")
        fileName = os.path.split(fileUrl)[1]

        self.progressDialog.setMaximum(100)
        self.progressDialog.setTitle(f"Update ModLoader to '{version}'")
        self.progressDialog.setContent(f"Download '{fileName}'")
        self.progressDialog.show()
        urllib.request.urlretrieve(fileUrl, filePath, self.handleUpdateApp)
        self.progressDialog.hide()

        clientPath = os.environ.get("CLIENT_PATH")
        if not clientPath and core and hasattr(core, 'MODLOADER_CACHE_PATH'):
            possibleClient = os.path.join(core.MODLOADER_CACHE_PATH, "ModLoaderClient.exe")
            if os.path.exists(possibleClient):
                clientPath = possibleClient

        currentExe = os.path.abspath(sys.argv[0])
        if clientPath and os.path.exists(clientPath):
            subprocess.Popen([clientPath, "-update", currentExe, filePath])
        else:
            cmd = f'ping 127.0.0.1 -n 3 > NUL & move /y "{filePath}" "{currentExe}" & start "" "{currentExe}"'
            subprocess.Popen(cmd, shell=True)

        QApplication.exit(0)

    def checkNewVersion(self):
        latest = GetLatest()

        if latest is not None:
            newVersion, fileUrl, version, body = latest
            self.newVersion(newVersion, fileUrl, version, body)

    @QExecMainThread
    def setForeground(self):
        try:
            if sys.platform.startswith("win"):
                import win32gui, win32com.client

                shell = win32com.client.Dispatch("WScript.Shell")
                shell.SendKeys('%')
                win32gui.SetForegroundWindow(self.winId())
        except:
            pass

    _dlProgress = Signal(int, str)
    _dlDone = Signal(str)
    _dlError = Signal(str)

    def handleGameBananaDownload(self, url, filename):

        if url.startswith("bmod://"):
            self.urlImport(url, reload=False)
            self.reloadPending = True
            return

        self.progressDialog.setTitle(f"Downloading {filename}...")
        self.progressDialog.setContent("Connecting...")
        self.progressDialog.setValue(0)
        self.progressDialog.setMaximum(100)
        # Progress dialog omitted so downloads happen quietly in background bar

        # Connect signals once (guard against double-connect)
        try: self._dlProgress.disconnect()
        except: pass
        try: self._dlDone.disconnect()
        except: pass
        try: self._dlError.disconnect()
        except: pass

        def _on_p(p, s):
            self.progressDialog.setValue(p)
            self.progressDialog.setContent(s)
            if hasattr(self, 'gamebanana'):
                self.gamebanana.set_download_progress(p, s)
        self._dlProgress.connect(_on_p)
        self._dlDone.connect(lambda path: (
            self.progressDialog.hide(), 
            self.fileImport(path, reload=False), 
            setattr(self, "reloadPending", True),
            self.gamebanana.update_installed_mods(self.getInstalledModNames()),
            self.gamebanana.set_download_progress(100, "Done") if hasattr(self, 'gamebanana') else None
        ))
        self._dlError.connect(lambda msg: (
            self.progressDialog.hide(),
            self.showError("Download Error", msg),
            self.gamebanana.set_download_progress(100, "Error") if hasattr(self, 'gamebanana') else None
        ))

        def download():
            try:
                print(f"[GB DL] Starting download: {url}")
                response = requests.get(url, stream=True, headers={"User-Agent": "BModLoader/1.0"}, timeout=15)
                response.raise_for_status()
                total_size = int(response.headers.get('content-length', 0))
                
                # Check if it's a bmod:// URL or direct URL
                if url.startswith("bmod://"):
                    # For bmod:// we expect the existing pipeline to handle it
                    # But if we are here, it might be a direct link from a file row
                    pass
                
                temp_path = os.path.join(os.getenv("TEMP"), filename)
                downloaded = 0
                with open(temp_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                p = int((downloaded / total_size) * 100)
                                self._dlProgress.emit(p, f"Downloaded {format_size(downloaded)} / {format_size(total_size)}")
                print(f"[GB DL] Successfully downloaded to {temp_path}")
                self._dlDone.emit(temp_path)
            except Exception as e:
                print(f"[GB DL] Error occurred: {e}")
                # Fallback to manual download to Downloads folder
                try:
                    downloads_path = os.path.join(os.path.expanduser("~"), "Downloads", filename)
                    print(f"[GB DL] Fallback: Downloading to {downloads_path}")
                    response = requests.get(url, stream=True, headers={"User-Agent": "BModLoader/1.0"})
                    with open(downloads_path, "wb") as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk: f.write(chunk)
                    self._dlError.emit(f"Automatic import failed, but mod was saved to your Downloads folder: {filename}")
                    os.startfile(os.path.join(os.path.expanduser("~"), "Downloads"))
                except Exception as e2:
                    self._dlError.emit(f"Download failed: {str(e)}\n\nFallback error: {str(e2)}")

        threading.Thread(target=download, daemon=True).start()

    queueFileSignal = Signal()

    def queueFile(self):
        for file in self.importQueue.iterFile():
            self.fileImport(file)

    def fileImport(self, filePath: str, reload=True):
        """Import a .bmod file, a .zip containing .bmod files, or a mod folder."""
        self.setForeground()

        filePath = os.path.normpath(filePath)

        # ── If it's a folder, treat it as a mod source folder ──────────────────
        if os.path.isdir(filePath):
            dest = os.path.join(self.modsPath, os.path.basename(filePath))
            if os.path.abspath(filePath) == os.path.abspath(dest):
                return  # already inside mods folder
            import shutil
            if os.path.exists(dest):
                shutil.rmtree(dest)
            shutil.copytree(filePath, dest)
            if reload:
                self.reloadMods()
            return

        # ── Skip if already inside mods folder ────────────────────────────────
        if os.path.abspath(filePath).startswith(os.path.abspath(self.modsPath)):
            return

        fileName = os.path.basename(filePath)
        ext = os.path.splitext(fileName)[1].lower()

        # ── .bmod — copy directly ─────────────────────────────────────────────
        if ext == f".{core.MOD_FILE_FORMAT}":
            fileNameSplit = os.path.splitext(fileName)
            destName = fileName
            if os.path.exists(os.path.join(self.modsPath, destName)):
                i = 1
                while os.path.exists(os.path.join(self.modsPath, f"{fileNameSplit[0]} ({i}){fileNameSplit[1]}")):
                    i += 1
                destName = f"{fileNameSplit[0]} ({i}){fileNameSplit[1]}"
            with open(filePath, "rb") as src:
                with open(os.path.join(self.modsPath, destName), "wb") as dst:
                    dst.write(src.read())

        # ── .zip — extract .bmod files inside ────────────────────────────────
        elif ext == ".zip":
            bmod_found = False
            try:
                with zipfile.ZipFile(filePath) as z:
                    for name in z.namelist():
                        if name.endswith(f".{core.MOD_FILE_FORMAT}"):
                            bmod_found = True
                            target_fn = os.path.basename(name)
                            data = z.read(name)
                            dest_path = os.path.join(self.modsPath, target_fn)
                            if os.path.exists(dest_path):
                                fn, fe = os.path.splitext(target_fn)
                                i = 1
                                while os.path.exists(os.path.join(self.modsPath, f"{fn} ({i}){fe}")):
                                    i += 1
                                dest_path = os.path.join(self.modsPath, f"{fn} ({i}){fe}")
                            with open(dest_path, "wb") as out:
                                out.write(data)
            except Exception as e:
                self.showError("ZIP Error", f"Could not open ZIP file:\n{e}")
                return
            if not bmod_found:
                self.showError("No .bmod found", f"<font color='red'>This file is not compatible with the .bmod loader, it will not be downloaded</font>")
                return
        else:
            # Unsupported extension — silently skip
            return

        if reload:
            self.reloadMods()

    # ── Drag & Drop ──────────────────────────────────────────────────────────
    def dragEnterEvent(self, event):
        mime = event.mimeData()
        if mime.hasUrls():
            # Accept if at least one url is a supported type
            for url in mime.urls():
                path = url.toLocalFile()
                ext = os.path.splitext(path)[1].lower()
                if os.path.isdir(path) or ext in (f".{core.MOD_FILE_FORMAT}", ".zip"):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        paths = [url.toLocalFile() for url in event.mimeData().urls()]
        event.acceptProposedAction()

        # Import all at once, reload once at the end
        for i, path in enumerate(paths):
            self.fileImport(path, reload=(i == len(paths) - 1))

    queueUrlSignal = Signal()

    def handleGameBananaDownload(self, url, fname):
        print(f"[GameBanana] Received download request: URL='{url}', Filename='{fname}'")
        mid = None
        try:
            data_str = url.split(":", 1)[1].strip("/")
            parts = [p.strip() for p in data_str.split(",") if p.strip()]
            if len(parts) >= 2 and parts[1].isdigit():
                mid = int(parts[1])
        except: pass

        try:
            res = self.urlImport(url, reload=False)
            self.reloadPending = True
            print(f"[GameBanana] Download & import completed with status: {res}")
            if res is True:
                if mid and hasattr(self, 'gamebanana'):
                    self.gamebanana.mark_mod_downloaded(mid)
            elif res is False:
                if mid and hasattr(self, 'gamebanana'):
                    self.gamebanana.mark_mod_incompatible(mid)
        except Exception as e:
            print(f"[GameBanana ERROR] Download failed: {e}")
            import traceback
            traceback.print_exc()
            if mid and hasattr(self, 'gamebanana'):
                self.gamebanana.mark_mod_error(mid)
            self.showError("Download Failed", f"An error occurred while downloading:\n{e}")

    def queueUrl(self):
        for url in self.importQueue.iterUrl():
            self.urlImport(url)

    def urlImport(self, url, reload=True):
        print(f"[urlImport] Handling import for URL: '{url}' (reload={reload})")
        data_str = url.split(":", 1)[1].strip("/")
        parts = [p.strip() for p in data_str.split(",") if p.strip()]
        if len(parts) < 3:
            print(f"[urlImport ERROR] Invalid bmod URL format: '{url}'")
            return False
            
        modType, modID, fileID = parts[0], parts[1], parts[2]
        mid_val = int(modID) if modID.isdigit() else None

        webUrl = f"https://gamebanana.com/dl/{fileID}"
        archivePath = os.path.join(self.modsPath, f"{modType}_{modID}_{fileID}")
        print(f"[urlImport] Target download URL: {webUrl}")
        print(f"[urlImport] Target archive path: {archivePath}")

        def reporthook(count, blockSize, totalSize):
            if totalSize > 0:
                percent = int(count * blockSize * 100 / totalSize)
                percent = min(100, max(0, percent))
                self.progressDialog.setContent(f"Download: {percent}%")
                if hasattr(self, 'gamebanana'):
                    self.gamebanana.set_download_progress(percent, mid=mid_val)
                QApplication.processEvents()

        if reload:
            self.progressDialog.setTitle("Import mod from Gamebanana...")
            self.progressDialog.setContent("Download...")
            self.progressDialog.show()

        try:
            # Install User-Agent and unverified SSL opener to prevent GameBanana HTTP 403 Forbidden and SSL verification errors
            ssl_ctx = ssl._create_unverified_context()
            opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ssl_ctx))
            opener.addheaders = [('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')]
            urllib.request.install_opener(opener)

            urllib.request.urlretrieve(webUrl, archivePath, reporthook)

            file_size = os.path.getsize(archivePath) if os.path.exists(archivePath) else 0
            print(f"[urlImport] Download finished. Downloaded archive size: {file_size} bytes")

            with open(archivePath, "rb") as file:
                _signature = file.read(3)
            print(f"[urlImport] Archive header signature: {_signature}")

            bmod_found = False
            extracted_bmod_filename = None

            if _signature.startswith(b"7z"):
                print("[urlImport] Extracting 7z archive...")
                with py7zr.SevenZipFile(archivePath) as mod7z:
                    names = mod7z.getnames()
                    print(f"[urlImport] Files inside 7z: {names}")
                    for file in names:
                        if file.endswith(f".{core.MOD_FILE_FORMAT}"):
                            bmod_found = True
                            target_fn = os.path.basename(file)
                            extracted_bmod_filename = target_fn
                            print(f"[urlImport] Extracting .bmod file: '{file}' -> '{target_fn}'")

                            self.progressDialog.setContent(f"Extract: '{target_fn}'")
                            QApplication.processEvents()
                            # Extract and move to root of modsPath
                            mod7z.extract(self.modsPath, [file])
                            # If it was in a subfolder, move it
                            if os.path.dirname(file):
                                old_path = os.path.join(self.modsPath, file)
                                new_path = os.path.join(self.modsPath, target_fn)
                                if os.path.exists(old_path):
                                    if os.path.exists(new_path): os.remove(new_path)
                                    os.rename(old_path, new_path)

            elif _signature.startswith(b"Rar"):
                print("[urlImport] Extracting RAR archive...")
                rar_success = False
                try:
                    with rarfile.RarFile(archivePath) as modRar:
                        names = modRar.namelist()
                        print(f"[urlImport] Files inside RAR: {names}")
                        for file in names:
                            if file.endswith(f".{core.MOD_FILE_FORMAT}"):
                                bmod_found = True
                                target_fn = os.path.basename(file)
                                extracted_bmod_filename = target_fn
                                print(f"[urlImport] Extracting .bmod file: '{file}' -> '{target_fn}'")

                                self.progressDialog.setContent(f"Extract: '{target_fn}'")
                                QApplication.processEvents()
                                
                                modRar.extract(file, self.modsPath)
                                if os.path.dirname(file):
                                    old_path = os.path.join(self.modsPath, file)
                                    new_path = os.path.join(self.modsPath, target_fn)
                                    if os.path.exists(old_path):
                                        if os.path.exists(new_path): os.remove(new_path)
                                        os.rename(old_path, new_path)
                                rar_success = True
                except Exception as rar_err:
                    print(f"[urlImport ERROR] rarfile module extraction error: {rar_err}. Attempting WinRAR executable fallback...")
                    for winrar_exe in [r"C:\Program Files\WinRAR\WinRAR.exe", r"C:\Program Files (x86)\WinRAR\WinRAR.exe", r"C:\Program Files\WinRAR\unrar.exe", r"C:\Program Files (x86)\WinRAR\unrar.exe"]:
                        if os.path.exists(winrar_exe):
                            try:
                                subprocess.run([winrar_exe, "e", "-y", archivePath, f"*.{core.MOD_FILE_FORMAT}", self.modsPath], capture_output=True)
                                bmod_files = [f for f in os.listdir(self.modsPath) if f.endswith(f".{core.MOD_FILE_FORMAT}")]
                                if bmod_files:
                                    bmod_found = True
                                    extracted_bmod_filename = bmod_files[0]
                                    rar_success = True
                                    print(f"[urlImport] WinRAR fallback successfully extracted .bmod files!")
                                    break
                            except Exception as e:
                                print(f"[urlImport ERROR] WinRAR fallback error: {e}")
                    if not rar_success and not bmod_found:
                        raise Exception(f"Could not extract RAR file. Please ensure WinRAR is installed.\nDetail: {rar_err}")

            elif _signature.startswith(b"PK"):
                print("[urlImport] Extracting ZIP archive...")
                with zipfile.ZipFile(archivePath) as modZip:
                    names = modZip.namelist()
                    print(f"[urlImport] Files inside ZIP: {names}")
                    for file in names:
                        if file.endswith(f".{core.MOD_FILE_FORMAT}"):
                            bmod_found = True
                            target_fn = os.path.basename(file)
                            extracted_bmod_filename = target_fn
                            print(f"[urlImport] Extracting .bmod file: '{file}' -> '{target_fn}'")

                            self.progressDialog.setContent(f"Extract: '{target_fn}'")
                            QApplication.processEvents()
                            
                            # Extract and move
                            modZip.extract(file, self.modsPath)
                            if os.path.dirname(file):
                                old_path = os.path.join(self.modsPath, file)
                                new_path = os.path.join(self.modsPath, target_fn)
                                if os.path.exists(old_path):
                                    if os.path.exists(new_path): os.remove(new_path)
                                    os.rename(old_path, new_path)

            if not bmod_found:
                print("[urlImport WARNING] No .bmod file found in archive!")
                self.progressDialog.hide()
                if mid_val and hasattr(self, 'gamebanana'):
                    self.gamebanana.mark_mod_incompatible(mid_val)
                self.showError("Incompatible Mod Format", 
                    "This mod is not compatible with the Brawlhalla Mod Loader. Please check the GameBanana page for manual installation instructions.")
                return False

            if reload:
                self.reloadMods()
            else:
                if hasattr(self, 'gamebanana'):
                    self.gamebanana.update_installed_mods(self.getInstalledModNames())

            if mid_val and hasattr(self, 'gamebanana'):
                if extracted_bmod_filename:
                    self.gamebanana.track_installed_mod_file(extracted_bmod_filename, mid_val, fileID)
                else:
                    self.gamebanana.mark_mod_downloaded(mid_val)

            self.progressDialog.hide()
            print("[urlImport SUCCESS] Mod successfully downloaded and imported!")
            return True

        except rarfile.RarCannotExec:
            print("[urlImport ERROR] WinRAR unrar.exe not found")
            self.progressDialog.hide()
            if mid_val and hasattr(self, 'gamebanana'):
                self.gamebanana.mark_mod_error(mid_val)
            self.showError(
                "Requirement Missing: WinRAR / UnRAR Tool Required",
                "This mod is packaged inside a .RAR archive, but WinRAR ('unrar.exe') was not found on your system.\n\n"
                "How to fix this issue:\n"
                "1. Download and install WinRAR from https://www.win-rar.com/\n"
                "2. Ensure WinRAR is installed to default path: 'C:\\Program Files\\WinRAR\\'\n"
                "3. Restart Brawlhalla Mod Loader and try downloading again."
            )
            return False

        except Exception as e:
            print(f"[urlImport ERROR] Automatic import failed: {e}")
            import traceback
            traceback.print_exc()
            self.progressDialog.hide()

            if mid_val and hasattr(self, 'gamebanana'):
                self.gamebanana.mark_mod_error(mid_val)

            err_msg = str(e)
            if "unrar" in err_msg.lower() or "rar" in err_msg.lower() or "winrar" in err_msg.lower():
                self.showError(
                    "Requirement Missing: WinRAR / UnRAR Tool Required",
                    "This mod is packaged inside a .RAR archive, but WinRAR ('unrar.exe') was not found on your system.\n\n"
                    "How to fix this issue:\n"
                    "1. Download and install WinRAR from https://www.win-rar.com/\n"
                    "2. Ensure WinRAR is installed to default path: 'C:\\Program Files\\WinRAR\\'\n"
                    "3. Restart Brawlhalla Mod Loader and try downloading again."
                )
            else:
                self.showError(
                    "Mod Download & Import Failed",
                    f"An error occurred while downloading and extracting the mod:\n\n{err_msg}\n\n"
                    "Troubleshooting Steps:\n"
                    "1. Verify your internet connection.\n"
                    "2. If downloading a .RAR file, install WinRAR (https://www.win-rar.com/).\n"
                    "3. Check folder write permissions in your Mods directory."
                )

            return False

        finally:
            self.progressDialog.hide()
            if 'archivePath' in locals() and os.path.exists(archivePath):
                try:
                    os.remove(archivePath)
                except:
                    pass



class WIPFrame(QFrame):
    def __init__(self, title):
        super().__init__()
        self.setStyleSheet("background-color: #151518;")
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        
        label = QLabel(f"{title} is currently under construction")
        font = QFont("Roboto", 20)
        font.setBold(True)
        label.setFont(font)
        label.setStyleSheet("color: #7E57C2;")
        layout.addWidget(label)
        
        sublabel = QLabel("WIP")
        sublabel.setFont(QFont("Roboto", 14))
        sublabel.setStyleSheet("color: #aaaaaa;")
        sublabel.setAlignment(Qt.AlignCenter)
        layout.addWidget(sublabel)

    def update_installed_mods(self, mods):
        pass


# pyrcc5 -o ui/ui_sources/icons_rc.py ui/ui_sources/icons.qrc
# venv\Lib\site-packages\PySide6\lupdate.exe @ui/ui_sources/ui_files.txt -ts ui/ui_sources/translate/header/ru_RU.ts
# venv\Lib\site-packages\PySide6\lupdate.exe ui/ui_sources/header.ui -locations ui/ui_sources/translate/header
# venv\Lib\site-packages\PySide6\lrelease.exe E:\BrawlhallaModloaderApp_0.3\ui\ui_sources\translate\header\ru_RU.ts


def RunApp():
    app = QApplication(sys.argv)

    font_db = QFontDatabase
    font_db.addApplicationFont(":/fonts/resources/fonts/Exo 2/Exo2-SemiBold.ttf")
    font_db.addApplicationFont(":/fonts/resources/fonts/Roboto/Roboto-Black.ttf")
    font_db.addApplicationFont(":/fonts/resources/fonts/Roboto/Roboto-BlackItalic.ttf")
    font_db.addApplicationFont(":/fonts/resources/fonts/Roboto/Roboto-Bold.ttf")
    font_db.addApplicationFont(":/fonts/resources/fonts/Roboto/Roboto-BoldItalic.ttf")
    font_db.addApplicationFont(":/fonts/resources/fonts/Roboto/Roboto-Italic.ttf")
    font_db.addApplicationFont(":/fonts/resources/fonts/Roboto/Roboto-Medium.ttf")
    font_db.addApplicationFont(":/fonts/resources/fonts/Roboto/Roboto-MediumItalic.ttf")
    font_db.addApplicationFont(":/fonts/resources/fonts/Roboto/Roboto-Regular.ttf")

    """
    translator = QTranslator()
    lang = QLocale.system().name()
    supportedLangs = translate.GetLangs()
    if lang in supportedLangs:
        translator.load(supportedLangs[lang])
    app.installTranslator(translator)
    """

    window = ModLoader()
    window.show()

    exitId = app.exec()
    TerminateApp(exitId)


if __name__ == "__main__":
    RunApp()
