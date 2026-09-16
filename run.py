import os
import sys

# Detect frozen/compiled binary: supports both PyInstaller (sys.frozen) and Nuitka (__compiled__)
_is_nuitka = False
try:
    _is_nuitka = bool(__compiled__)  # noqa - defined by Nuitka at compile time
except NameError:
    pass

_IS_FROZEN = getattr(sys, 'frozen', False) or _is_nuitka

if _IS_FROZEN:
    # PyInstaller extracts to sys._MEIPASS; Nuitka onefile extracts next to __file__
    if hasattr(sys, '_MEIPASS'):
        _base_dir = sys._MEIPASS
    else:
        _base_dir = os.path.dirname(os.path.abspath(__file__))
    os.environ['PATH'] = _base_dir + os.pathsep + os.path.join(_base_dir, 'PySide6') + os.pathsep + os.path.join(_base_dir, 'shiboken6') + os.pathsep + os.environ.get('PATH', '')
    if hasattr(os, 'add_dll_directory'):
        try:
            os.add_dll_directory(_base_dir)
        except Exception:
            pass
        for _sub in ['PySide6', 'shiboken6']:
            _sub_dir = os.path.join(_base_dir, _sub)
            if os.path.isdir(_sub_dir):
                try:
                    os.add_dll_directory(_sub_dir)
                except Exception:
                    pass
    # Keep the normal Windows DLL search path so JPype can load jvm.dll from
    # the user's installed JDK/JRE in one-file mode.

class NullWriter:
    def write(self, s): pass
    def flush(self): pass

if sys.stdout is None:
    sys.stdout = NullWriter()
if sys.stderr is None:
    sys.stderr = NullWriter()


import json
import socket
import hashlib
import traceback
import threading
import multiprocessing

ERROR = None

try:
    import core
except Exception as e:
    # Java not found error
    core = None

    # If other error
    err_str = str(e).lower()
    if not any(k in err_str for k in ["java not found", "_jpype", "jpype", "jvmnotfoundexception", "jvm"]):
        ERROR = sys.exc_info()

from client import Arguments, Commands, CONFIG_FILE, CONFIG, SOCKET_PORT, MODLOADER_CLIENT

from ui.utils.systemdialog import Error

FROZEN = _IS_FROZEN

MOD_FILE_FORMAT = core.MOD_FILE_FORMAT if core is not None else ""
FILE_DESCRIPTION = "Brawlhalla Mod"
FILE_ICON = "file_icon.ico"

if core is not None:
    os.environ["CLIENT_PATH"] = os.path.join(core.MODLOADER_CACHE_PATH, MODLOADER_CLIENT)
    os.environ["FILE_ICON"] = os.path.join(core.MODLOADER_CACHE_PATH, FILE_ICON)


def _bootstrap(self, parent_sentinel=None):
    import itertools
    from multiprocessing.process import _ParentProcess
    from multiprocessing import util, context
    global _current_process, _parent_process, _process_counter, _children

    try:
        if self._start_method is not None:
            context._force_start_method(self._start_method)
        _process_counter = itertools.count(1)
        _children = set()
        util._close_stdin()
        old_process = multiprocessing.current_process()
        _current_process = self
        _parent_process = _ParentProcess(
            self._parent_name, self._parent_pid, parent_sentinel)
        if threading._HAVE_THREAD_NATIVE_ID:
            threading.main_thread()._set_native_id()
        try:
            util._finalizer_registry.clear()
            util._run_after_forkers()
        finally:
            # delay finalization of the old process object until after
            # _run_after_forkers() is executed
            del old_process
        util.info('child process calling self.run()')
        try:
            self.run()
            exitcode = 0
        finally:
            util._exit_function()
    except SystemExit as e:
        if not e.args:
            exitcode = 1
        elif isinstance(e.args[0], int):
            exitcode = e.args[0]
        else:
            sys.stderr.write(str(e.args[0]) + '\n')
            exitcode = 1
    except:
        exitcode = 1
        sys.excepthook(*sys.exc_info())
    finally:
        threading._shutdown()
        util.info('process exiting with exitcode %d' % exitcode)
        util._flush_std_streams()

    return exitcode


multiprocessing.Process._bootstrap = _bootstrap


def handle_exception(exc_type, exc_value, exc_traceback):
    try:
        import pyi_splash
        pyi_splash.close()
    except:
        pass

    errorText = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))

    from main import ModLoader, PROGRAM_NAME, TerminateApp
    if ModLoader.app is not None:
        ModLoader.app.showError("Fatal Error:", errorText, terminate=True)
    else:
        Error(PROGRAM_NAME, errorText)
        TerminateApp()


sys.excepthook = handle_exception
threading.excepthook = lambda hook: handle_exception(hook.exc_type, hook.exc_value, hook.exc_traceback)

if ERROR is not None:
    sys.excepthook(*ERROR)


def GetLocalPath(subpath=""):
    candidates = [
        getattr(sys, '_MEIPASS', ''),
        os.path.dirname(os.path.abspath(__file__)),
        os.path.dirname(sys.executable),
        os.path.abspath("."),
    ]
    for c in candidates:
        if c:
            p = os.path.join(c, subpath) if subpath else c
            if os.path.exists(p):
                return p
    return os.path.join(os.path.abspath("."), subpath) if subpath else os.path.abspath(".")


def InstallClient():
    if core is None:
        return
    try:
        configPath = os.path.join(core.MODLOADER_CACHE_PATH, CONFIG_FILE)
        if os.path.exists(configPath):
            with open(configPath, "r") as file:
                config = json.loads(file.read())
        else:
            config = CONFIG

        clientPath = os.path.join(core.MODLOADER_CACHE_PATH, MODLOADER_CLIENT)

        candidates = [
            os.path.join(GetLocalPath(), MODLOADER_CLIENT),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), MODLOADER_CLIENT),
            os.path.join(os.path.dirname(sys.executable), MODLOADER_CLIENT),
            os.path.join(os.path.abspath("."), "dist", MODLOADER_CLIENT),
            os.path.join(os.path.abspath("."), MODLOADER_CLIENT),
        ]
        origClientPath = None
        for c in candidates:
            if os.path.exists(c):
                origClientPath = c
                break

        if origClientPath:
            with open(origClientPath, "rb") as file:
                originalClientContent = file.read()
                clientHash = hashlib.sha256(originalClientContent).hexdigest()

            if config.get("clientHash") != clientHash or not os.path.exists(clientPath):
                with open(clientPath, "wb") as file:
                    file.write(originalClientContent)

            config["clientHash"] = clientHash
            if FROZEN and sys.argv[0] != config.get("modLoaderPath"):
                config["modLoaderPath"] = sys.argv[0]
            with open(configPath, "w") as file:
                file.write(json.dumps(config))

        iconCandidates = [
            os.path.join(GetLocalPath(), FILE_ICON),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), FILE_ICON),
            os.path.join(os.path.dirname(sys.executable), FILE_ICON),
            os.path.join(os.path.abspath("."), FILE_ICON),
        ]
        iconPath = os.path.join(core.MODLOADER_CACHE_PATH, FILE_ICON)
        if not os.path.exists(iconPath):
            for ic in iconCandidates:
                if os.path.exists(ic):
                    with open(iconPath, "wb") as out_ico:
                        with open(ic, "rb") as in_ico:
                            out_ico.write(in_ico.read())
                    break
    except Exception:
        pass


def RunAsAdmin():
    try:
        import win32com.shell.shell

        if sys.argv[0].endswith(".exe"):
            argv = sys.argv[1:]
        else:
            argv = sys.argv

        params = ' '.join([*argv, Arguments.AS_ADMIN])
        win32com.shell.shell.ShellExecuteEx(lpVerb='runas', lpFile=sys.executable, lpParameters=params)
        sys.exit(0)
    except Exception:
        pass


# File association
def CheckFileRegistry():
    if core is None:
        return True
    import winreg
    try:
        _format = f"file{MOD_FILE_FORMAT}"
        fileformat = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, f".{MOD_FILE_FORMAT}")
        shell_open_command = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, f"{_format}\\shell\\open\\command")
        expected_cmd = f"{os.path.join(core.MODLOADER_CACHE_PATH, MODLOADER_CLIENT)} {Arguments.FILE} \"%1\""
        if (
                winreg.QueryValueEx(fileformat, None)[0] != _format
                or
                winreg.QueryValueEx(shell_open_command, None)[0] != expected_cmd
        ):
            winreg.CloseKey(shell_open_command)
            winreg.CloseKey(fileformat)
            return False

        winreg.CloseKey(shell_open_command)
        winreg.CloseKey(fileformat)
        return True
    except Exception:
        return False


def InstallFileRegistry():
    if core is None:
        return
    import winreg
    try:
        _format = f"file{MOD_FILE_FORMAT}"
        fileformat = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, f".{MOD_FILE_FORMAT}")
        winreg.SetValueEx(fileformat, None, 0, winreg.REG_SZ, _format)

        winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, _format)

        main = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, _format, 0, winreg.KEY_WRITE)
        winreg.SetValueEx(main, None, 0, winreg.REG_SZ, FILE_DESCRIPTION)

        default_icon = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, f"{_format}\\DefaultIcon")
        icon_env = os.environ.get("FILE_ICON", os.path.join(core.MODLOADER_CACHE_PATH, FILE_ICON))
        winreg.SetValueEx(default_icon, None, 0, winreg.REG_EXPAND_SZ, f'"{icon_env}",0')

        shell = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, f"{_format}\\shell")
        shell_open = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, f"{_format}\\shell\\open")
        shell_open_command = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, f"{_format}\\shell\\open\\command")
        winreg.SetValueEx(shell_open_command, None, 0, winreg.REG_SZ,
                          f"{os.path.join(core.MODLOADER_CACHE_PATH, MODLOADER_CLIENT)} {Arguments.FILE} \"%1\"")

        winreg.CloseKey(fileformat)
        winreg.CloseKey(main)
        winreg.CloseKey(default_icon)
        winreg.CloseKey(shell)
        winreg.CloseKey(shell_open)
        winreg.CloseKey(shell_open_command)
    except Exception:
        pass


# Url association
def CheckUrlRegistry():
    if core is None:
        return True
    import winreg
    try:
        shell_open_command = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, f"{MOD_FILE_FORMAT}\\shell\\open\\command")
        expected_cmd = f"{os.path.join(core.MODLOADER_CACHE_PATH, MODLOADER_CLIENT)} {Arguments.URL} \"%1\""
        if winreg.QueryValueEx(shell_open_command, None)[0] != expected_cmd:
            winreg.CloseKey(shell_open_command)
            return False

        winreg.CloseKey(shell_open_command)
        return True
    except Exception:
        return False


def InstallUrlRegistry():
    if core is None:
        return
    import winreg
    try:
        winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, MOD_FILE_FORMAT)

        main = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, MOD_FILE_FORMAT, 0, winreg.KEY_WRITE)
        winreg.SetValueEx(main, None, 0, winreg.REG_SZ, f"URL:{MOD_FILE_FORMAT} Protocol")
        winreg.SetValueEx(main, "URL Protocol", 0, winreg.REG_SZ, "")

        default_icon = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, f"{MOD_FILE_FORMAT}\\DefaultIcon")
        icon_env = os.environ.get("FILE_ICON", os.path.join(core.MODLOADER_CACHE_PATH, FILE_ICON))
        winreg.SetValueEx(default_icon, None, 0, winreg.REG_SZ, f'"{icon_env}",0')

        shell = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, f"{MOD_FILE_FORMAT}\\shell")
        shell_open = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, f"{MOD_FILE_FORMAT}\\shell\\open")
        shell_open_command = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, f"{MOD_FILE_FORMAT}\\shell\\open\\command")
        winreg.SetValueEx(shell_open_command, None, 0, winreg.REG_SZ,
                          f"{os.path.join(core.MODLOADER_CACHE_PATH, MODLOADER_CLIENT)} {Arguments.URL} \"%1\"")

        winreg.CloseKey(main)
        winreg.CloseKey(default_icon)
        winreg.CloseKey(shell)
        winreg.CloseKey(shell_open)
        winreg.CloseKey(shell_open_command)
    except Exception:
        pass


# Server for ModloaderClient.exe
def MLServer(mlserver: socket.socket, app_cls):
    def handle(_mlclient: socket.socket, _app_cls):
        try:
            data = _mlclient.recv(3)
            if not data:
                return
            command = data[:1]
            size = int.from_bytes(data[1:], "big")
            if command == Commands.NONE:
                pass
            elif command == Commands.JUST_OPEN:
                if hasattr(_app_cls, 'app') and _app_cls.app:
                    _app_cls.app.setForeground()
            elif command == Commands.OPEN_FILE:
                file = _mlclient.recv(size).decode("UTF-8")
                if file.endswith(MOD_FILE_FORMAT) and hasattr(_app_cls, 'app') and _app_cls.app:
                    _app_cls.app.importQueue.addFile(file)
            elif command == Commands.OPEN_URL:
                url = _mlclient.recv(size).decode("UTF-8")
                if hasattr(_app_cls, 'app') and _app_cls.app:
                    _app_cls.app.importQueue.addUrl(url)
            _mlclient.send(b"\x01")
            _mlclient.close()
        except Exception:
            pass

    while True:
        try:
            mlclient, _ = mlserver.accept()
            threading.Thread(target=handle, args=(mlclient, app_cls), daemon=True).start()
        except OSError:
            break


def close_nuitka_splash():
    """Ensure Nuitka onefile bootloader splash is completely closed/hidden."""
    # 1. Official Nuitka onefile splash dismissal using NUITKA_ONEFILE_PARENT environment variable
    try:
        if "NUITKA_ONEFILE_PARENT" in os.environ:
            import tempfile
            splash_filename = os.path.join(
                tempfile.gettempdir(),
                "onefile_%d_splash_feedback.tmp" % int(os.environ["NUITKA_ONEFILE_PARENT"]),
            )
            if os.path.exists(splash_filename):
                try:
                    os.unlink(splash_filename)
                except Exception:
                    pass
    except Exception:
        pass

    # 2. Native module fallback if available
    try:
        import onefile_splash
        onefile_splash.close()
    except Exception:
        pass

    # 3. Clean any remaining splash feedback tmp files in temp directory
    try:
        import tempfile, glob
        temp_dir = tempfile.gettempdir()
        for f in glob.glob(os.path.join(temp_dir, "onefile_*_splash_feedback.tmp")):
            try:
                os.unlink(f)
            except Exception:
                pass
    except Exception:
        pass

    # 4. Find and close any lingering Windows splash window with class "Splash"
    try:
        import win32gui, win32con
        def enum_cb(hwnd, _):
            if win32gui.GetClassName(hwnd) == "Splash":
                win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        win32gui.EnumWindows(enum_cb, None)
    except Exception:
        pass


if __name__ == "__main__" and "--multiprocessing-fork" not in sys.argv:
    os.chdir(os.path.split(sys.argv[0])[0])

    # Show Dynamic Splash Screen IMMEDIATELY (< 50ms)
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFontDatabase, QPixmap
    from main import BmodsSplash, set_global_splash, InitWindowSetText, RunApp

    app = QApplication.instance() or QApplication(sys.argv)

    font_family = "Arial"
    bespoke_candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "ui_sources", "resources", "fonts", "Bespoke", "Bespoke.ttf"),
        os.path.join(os.path.dirname(sys.executable), "ui", "ui_sources", "resources", "fonts", "Bespoke", "Bespoke.ttf"),
        os.path.join(os.path.abspath("."), "ui", "ui_sources", "resources", "fonts", "Bespoke", "Bespoke.ttf"),
    ]
    for b_path in bespoke_candidates:
        if os.path.exists(b_path):
            f_id = QFontDatabase.addApplicationFont(b_path)
            if f_id != -1:
                fams = QFontDatabase.applicationFontFamilies(f_id)
                if fams:
                    font_family = fams[0]
                    break

    splash_candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "splash.png"),
        os.path.join(os.path.dirname(sys.executable), "splash.png"),
        os.path.join(os.path.abspath("."), "splash.png"),
    ]
    for s_path in splash_candidates:
        if os.path.exists(s_path):
            pixmap = QPixmap(s_path)
            if not pixmap.isNull():
                splash = BmodsSplash(pixmap, font_family)
                splash.show()
                set_global_splash(splash)
                InitWindowSetText("Initializing Mod Loader...", delay_ms=100)
                app.processEvents()
                # Ensure dynamic splash is visibly rendered before dismissing Nuitka pre-splash
                import time
                time.sleep(0.05)
                close_nuitka_splash()
                break
    else:
        close_nuitka_splash()

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(Arguments.AS_ADMIN, dest='asadmin', action='store_const', const=True, default=False)
    args, _ = parser.parse_known_args()

    if sys.platform.startswith("win") and core is not None:
        InitWindowSetText("Verifying system associations...")
        try:
            InstallClient()
            fileRegistered = CheckFileRegistry()
            urlRegistered = CheckUrlRegistry()

            if not fileRegistered or not urlRegistered:
                if args.asadmin:
                    if not fileRegistered:
                        InstallFileRegistry()
                    if not urlRegistered:
                        InstallUrlRegistry()
                else:
                    try:
                        if not fileRegistered:
                            InstallFileRegistry()
                        if not urlRegistered:
                            InstallUrlRegistry()
                    except Exception:
                        pass
        except Exception:
            pass

    InitWindowSetText("Connecting client...")
    try:
        mlclient = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        mlclient.settimeout(0.1)
        mlclient.connect(("127.0.0.1", SOCKET_PORT))
        dataSize = 0
        mlclient.send(Commands.JUST_OPEN + dataSize.to_bytes(2, byteorder='big'))
        mlclient.close()
        sys.exit(0)
    except (ConnectionRefusedError, TimeoutError, socket.timeout, OSError):
        pass

    try:
        mlserver = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        mlserver.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        mlserver.bind(('', SOCKET_PORT))
        mlserver.listen(5)
        from main import ModLoader

        threading.Thread(target=MLServer, args=(mlserver, ModLoader), daemon=True).start()
    except Exception:
        pass

    InitWindowSetText("Loading components...")
    RunApp()

elif "--multiprocessing-fork" in sys.argv:
    from core import Controller

    Controller()
