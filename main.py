import os
import sys
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

# (https://stackoverflow.com/questions/9144724/unknown-encoding-idna-in-python-requests)
import encodings.idna

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
        self.header.ui.gamebananaButton.setText("GameBanana")
        self.mods = Mods(installMethod=self.installMod,
                         uninstallMethod=self.uninstallMod,
                         reinstallMethod=self.reinstallMod,
                         deleteMethod=self.deleteMod,
                         reloadMethod=self.reloadMods,
                         openFolderMethod=self.openModsFolder,
                         uninstallAllMethod=self.uninstallAllMods,
                         toggleFavoriteMethod=self.toggleFavorite,
                         sortCallback=self.updateSortState)

        self.progressDialog = ProgressDialog(self)
        self.buttonsDialog = ButtonsDialog(self)
        self.acceptDialog = AcceptDialog(self)
        
        # Temporary WIP flag for GameBanana browser
        GAMEBANANA_WIP = True
        
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
                self.acceptDialog.setTitle("Conflict mods!")
                content = "Mods:"

                for modConflictHash in modConflictHashes:
                    if modConflictHash in self.mods.mods:
                        mod = self.mods.mods[modConflictHash]
                        content += f"\n- {mod.name}"

                    else:
                        content += f"\n- UNKNOWN MOD: {modConflictHash}"
                        print("ERROR: One of the installed mods was not found in the ModLoader!")

                self.acceptDialog.setContent(content)
                self.acceptDialog.setAccept(lambda: [self.acceptDialog.hide(), self.controller.installMod(modHash)])
                self.acceptDialog.setCancel(self.acceptDialog.hide)

                self.progressDialog.hide()
                self.acceptDialog.show()


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
                
                if self.bulkOperationCount > 0:
                    self.bulkOperationCount -= 1
                    
                if self.bulkOperationCount <= 0:
                    self.progressDialog.hide()
                    
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

                if self.bulkOperationCount > 0:
                    self.bulkOperationCount -= 1
                    
                if self.bulkOperationCount <= 0:
                    self.progressDialog.hide()
                    
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
            self.mods.removeAllMods()

        elif cmd == Environment.GetModsData:
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
                                 favorite=modData.get("hash", "") in self.config.favorites)

            self.mods.applySort(self.currentSortField, self.currentSortReverse)
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
            errors = []
            errorsNotifications = self.errors.copy()
            self.errors.clear()

            for notif in errorsNotifications:
                ntype = notif.notificationType
                string = ""

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

    def installMod(self):
        bh_path = getattr(core.worker.brawlhalla, 'BRAWLHALLA_PATH', None) if (hasattr(core, 'worker') and hasattr(core.worker, 'brawlhalla')) else None
        if not bh_path or not os.path.exists(bh_path) or not os.path.isfile(os.path.join(bh_path, "Brawlhalla.exe")):
            self.showBrawlhallaNotFoundDialog()
            return

        if self.checkGameRunning():
            return
            
        if self.mods.selectedModButton is not None:
            if self.bulkOperationCount <= 0:
                self.bulkOperationCount = 1
            modClass = self.mods.selectedModButton.modClass
            self.controller.getModConflict(modClass.hash)

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
            
        if modButton is None or isinstance(modButton, bool):
            modButton = self.mods.selectedModButton
            if self.bulkOperationCount <= 0:
                self.bulkOperationCount = 1
            
        if modButton is not None:
            modClass = modButton.modClass
            self.controller.uninstallMod(modClass.hash)

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
        self.progressDialog.show()

        # Connect signals once (guard against double-connect)
        try: self._dlProgress.disconnect()
        except: pass
        try: self._dlDone.disconnect()
        except: pass
        try: self._dlError.disconnect()
        except: pass

        self._dlProgress.connect(lambda p, s: (self.progressDialog.setValue(p), self.progressDialog.setContent(s)))
        self._dlDone.connect(lambda path: (
            self.progressDialog.hide(), 
            self.fileImport(path, reload=False), 
            setattr(self, "reloadPending", True),
            self.gamebanana.update_installed_mods(self.getInstalledModNames())
        ))
        self._dlError.connect(lambda msg: (self.progressDialog.hide(), self.showError("Download Error", msg)))

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
                self.showError("No .bmod found", f"The ZIP '{fileName}' does not contain any .bmod files.")
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

    def queueUrl(self):
        for url in self.importQueue.iterUrl():
            self.urlImport(url)

    def urlImport(self, url: str, reload=True):

        self.setForeground()

        data = url.split(":", 1)[1].strip("/")
        splitData = [p for p in data.split(",") if p.strip()]  # strip empty trailing parts

        if len(splitData) >= 3:
            tag, modId, dlId = splitData[0], splitData[1], splitData[2]
            zipUrl = f"https://gamebanana.com/dl/{dlId}"
        else:
            zipUrl = ""
            return

        archivePath = os.path.join(self.modsPath, "_mod.archive")

        self.progressDialog.setMaximum(100)
        self.progressDialog.setTitle("Download mod")
        self.progressDialog.setContent("")
        self.progressDialog.show()
        QApplication.processEvents()
        try:
            # GameBanana requires a User-Agent header, otherwise it returns HTTP 403 Forbidden.
            opener = urllib.request.build_opener()
            opener.addheaders = [('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')]
            urllib.request.install_opener(opener)
            
            urllib.request.urlretrieve(zipUrl, archivePath, self.handleUpdateApp)

            with open(archivePath, "rb") as file:
                _signature = file.read(3)


            bmod_found = False

            if _signature.startswith(b"7z"):
                with py7zr.SevenZipFile(archivePath) as mod7z:
                    names = mod7z.getnames()

                    for file in names:
                        if file.endswith(f".{core.MOD_FILE_FORMAT}"):
                            bmod_found = True
                            target_fn = os.path.basename(file)

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
                with rarfile.RarFile(archivePath) as modRar:
                    names = modRar.namelist()

                    for file in names:
                        if file.endswith(f".{core.MOD_FILE_FORMAT}"):
                            bmod_found = True
                            target_fn = os.path.basename(file)

                            self.progressDialog.setContent(f"Extract: '{target_fn}'")
                            QApplication.processEvents()
                            
                            # Extracting with rarfile can be tricky for flattening, 
                            # easiest is to extract then move
                            modRar.extract(file, self.modsPath)
                            if os.path.dirname(file):
                                old_path = os.path.join(self.modsPath, file)
                                new_path = os.path.join(self.modsPath, target_fn)
                                if os.path.exists(old_path):
                                    if os.path.exists(new_path): os.remove(new_path)
                                    os.rename(old_path, new_path)

            elif _signature.startswith(b"PK"):
                with zipfile.ZipFile(archivePath) as modZip:
                    names = modZip.namelist()

                    for file in names:
                        if file.endswith(f".{core.MOD_FILE_FORMAT}"):
                            bmod_found = True
                            target_fn = os.path.basename(file)

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

                self.showError("Incompatible Mod Format", 
                    "This mod does not contain a standard .bmod file or is packaged in a way that cannot be automatically installed.\n\n"
                    "Please download it manually from the website and follow the installation instructions provided by the author.")
                return False

            if reload:
                self.reloadMods()
            else:
                if hasattr(self, 'gamebanana'):
                    self.gamebanana.update_installed_mods(self.getInstalledModNames())
            # Mark as downloaded ONLY IF SUCCESSFUL
            try:
                parts = url.split(":", 1)[1].strip("/").split(",")
                if len(parts) >= 2:
                    mid = int(parts[1])
                    if hasattr(self, 'gamebanana'):
                        self.gamebanana.mark_mod_downloaded(mid)
            except: pass

            self.progressDialog.hide()
            return True

        except rarfile.RarCannotExec:
            self.showError("Unpack error:", "WinRar 'unrar.exe' not found. Please install WinRar or add its installation folder to your Windows PATH to support .rar mod files.")
            return False

        except Exception as e:
            # Fallback to manual download if automatic import fails

            try:
                downloads_path = os.path.join(os.path.expanduser("~"), "Downloads", f"mod_{dlId}.zip")
                urllib.request.urlretrieve(zipUrl, downloads_path)
                self.showError("Automatic Import Failed", 
                    f"The automatic installation failed, but we've downloaded the mod to your Downloads folder: mod_{dlId}.zip\n\nError: {str(e)}")
                os.startfile(os.path.join(os.path.expanduser("~"), "Downloads"))
            except:
                self.showError("Operation failed:", "".join(traceback.format_exception(*sys.exc_info())))

        finally:
            self.progressDialog.hide()
            if os.path.exists(archivePath):
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
