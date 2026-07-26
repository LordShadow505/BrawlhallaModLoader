from typing import List, Dict

from PySide6.QtWidgets import QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QFrame, QLabel
from PySide6.QtGui import QPixmap, QPaintEvent, QIcon, QCursor
from PySide6.QtCore import QSize, Qt, QTimer

from .modbutton import ModButton
from .modclass import ModClass

from ..ui_sources.ui_mods import Ui_Mods
from ..ui_sources.ui_mod_body import Ui_ModBody
from ..ui_sources.ui_mods_actions import Ui_ModsActions

from ..utils.buttons import AddButtonWidthToTexSize
from ..utils.layout import AddToFrame, ClearFrame
from ..utils.buttongroup import ButtonGroup


# TODO: Add gif or video in previews


class NavigateButton(ButtonGroup):
    def __init__(self, n, method):
        self.n = n

        self.previewNavigate = QPushButton()
        self.previewNavigate.setCursor(QCursor(Qt.PointingHandCursor))
        self.previewNavigate.setStyleSheet(u"background-color: #00000000;")
        icon = QIcon()
        icon.addFile(u":/icons/resources/icons/UnselectedCircle.png", QSize(), QIcon.Normal, QIcon.Off)
        icon.addFile(u":/icons/resources/icons/SelectedCircle.png", QSize(), QIcon.Active, QIcon.On)
        self.previewNavigate.setIcon(icon)
        self.previewNavigate.setIconSize(QSize(8, 8))
        self.previewNavigate.setCheckable(True)

        super().__init__("PreviewNavigate", self.previewNavigate, method=method)

        if self.n == 0:
            self.previewNavigate.setChecked(True)

    def pressed(self):
        if not self.button.isChecked():
            self.pressedMethod(self.n)

        for k in self.getSelfGroup():
            if k.button.isChecked():
                k.button.setChecked(False)

        return False

    def released(self):
        self.button.setChecked(True)

        return True

    def setActive(self):
        self.button.setChecked(True)

        for k in self.getSelfGroup():
            if k.button != self.button:
                k.button.setChecked(False)

    def remove(self):
        self.button.setParent(None)

    def addToFrame(self, frame):
        AddToFrame(frame, self.button)

    def hasParent(self):
        return bool(self.button.parent())


class Mods(QWidget):
    defaultPreview = ":/images/resources/images/DefaultPreview.png"
    cachePreviews: Dict[str, QPixmap] = {}
    selectedModButton: ModButton = None
    mods: Dict[str, ModClass] = {}
    modsButtons: List[ModButton] = []

    def __init__(self, installMethod, uninstallMethod, reinstallMethod, deleteMethod, reloadMethod, openFolderMethod, uninstallAllMethod, toggleFavoriteMethod, sortCallback):
        super().__init__()

        self.ui = Ui_Mods()
        self.ui.setupUi(self)
        self.toggleFavoriteMethod = toggleFavoriteMethod
        self.sortCallback = sortCallback

        self.setStyleSheet("""
            QToolTip {
                background-color: #151518;
                color: #ffffff;
                border: 1px solid #404146;
                padding: 4px;
            }
        """)

        self.preview = None
        self.previews: List[QPixmap] = []
        self.previewsNavigate: List[NavigateButton] = [NavigateButton(n, self.setPreviewNum) for n in range(6)]
        self.previewRatio = 1

        bodyWidget = QWidget()
        self.body = Ui_ModBody()
        self.body.setupUi(bodyWidget)
        self.ui.scrollBody.setWidget(bodyWidget)

        self.ui.modBody.installEventFilter(self)
        self.modDescriptionsAndActionsLayout = self.body.modDescriptionsAndActions.layout()

        self.body.leftPreview.clicked.connect(self.leftPreview)
        self.body.rightPreview.clicked.connect(self.rightPreview)

        # Warning Notice
        self.warningFrame = QFrame()
        self.warningFrame.setStyleSheet("background-color: #1D1E20; border-bottom: 1px solid #333333;")
        warningLayout = QHBoxLayout(self.warningFrame)
        warningLayout.setContentsMargins(10, 5, 10, 5)
        warningLayout.setSpacing(10)

        warningIconLabel = QLabel()
        warningIconLabel.setPixmap(QIcon(":/icons/resources/icons/Warning.png").pixmap(16, 16))
        warningLayout.addWidget(warningIconLabel)

        warningTextLabel = QLabel("Remember that any existing skin mod requires a PAID skin, check the REQUIREMENTS section in GameBanana to find out which skin it replaces.")
        warningTextLabel.setWordWrap(True)
        warningTextLabel.setStyleSheet("color: #FF5252; font-size: 10px; font-weight: bold; border: none;")
        warningLayout.addWidget(warningTextLabel, 1)

        self.ui.verticalLayout.insertWidget(0, self.warningFrame)

        modsListFrame = QFrame()
        layout = QVBoxLayout(modsListFrame)
        layout.setSpacing(0)
        layout.setContentsMargins(2, 5, 2, 5)
        self.modsList = QFrame()
        self.ui.modsList.setMaximumWidth(528)
        self.modsList.setMaximumWidth(528)
        layout2 = QVBoxLayout(self.modsList)
        layout2.setSpacing(1)
        layout2.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.modsList, 0, Qt.AlignTop)
        self.ui.scrollModsList.setWidget(modsListFrame)

        self.resizeEvent = self.onResize
        self.origScrollModsListResizeEvent = self.ui.scrollModsList.resizeEvent
        self.ui.scrollModsList.resizeEvent = self.onModsListResize

        actionsWidget = QWidget()
        self.modsActions = Ui_ModsActions()
        self.modsActions.setupUi(actionsWidget)

        AddButtonWidthToTexSize(self.modsActions.webPage, 40)
        AddButtonWidthToTexSize(self.modsActions.install, 40)
        AddButtonWidthToTexSize(self.modsActions.uninstall, 40)
        AddButtonWidthToTexSize(self.modsActions.reinstall, 40)
        AddButtonWidthToTexSize(self.modsActions.update, 40)
        AddButtonWidthToTexSize(self.modsActions.deleteMod, 40)

        self.modsActions.install.clicked.connect(installMethod)
        self.modsActions.uninstall.clicked.connect(uninstallMethod)
        self.modsActions.reinstall.clicked.connect(reinstallMethod)
        self.modsActions.deleteMod.clicked.connect(deleteMethod)
        self.modsActions.deleteMod.setIcon(QIcon(":/icons/resources/icons/Delete.png"))
        
        self.ui.reloadModsList.clicked.connect(reloadMethod)
        self.ui.openModsFolderButton.clicked.connect(openFolderMethod)
        
        # New Uninstall All Button
        self.ui.uninstallAllMods = QPushButton(self.ui.leftButtons)
        self.ui.uninstallAllMods.setMinimumSize(QSize(30, 30))
        self.ui.uninstallAllMods.setCursor(Qt.PointingHandCursor)
        self.ui.uninstallAllMods.setIcon(QIcon(":/icons/resources/icons/UninstallAllMods.png"))
        self.ui.uninstallAllMods.setToolTip("Uninstall all mods from game")
        self.ui.horizontalLayout_4.insertWidget(2, self.ui.uninstallAllMods)
        self.ui.uninstallAllMods.clicked.connect(uninstallAllMethod)
        
        self.ui.deleteAllMods.setIcon(QIcon(":/icons/resources/icons/Delete.png"))
        self.ui.deleteAllMods.setToolTip("Delete all mods from list")
        
        from ..utils.config import LoaderConfig
        
        # Bottom left buttons Tooltips
        self.ui.modsSortButton.setToolTip("Sort Mods")
        self.ui.openModsFolderButton.setToolTip("Open Mods Folder")
        
        # Sort Dropdown
        self.ui.modsSortButton.clicked.connect(self.showSortMenu)
        
        # Toggle Previews Button
        self.ui.updateAllMods.setToolTip("Toggle List Previews")
        self.ui.updateAllMods.clicked.connect(self.toggleListPreviews)
        self.updateListPreviewsIcon()

        self.ui.searchArea.textChanged.connect(self.searchEvent)

        AddToFrame(self.body.modActions, actionsWidget)

        self.nameSortReverse = False
        self.dateSortReverse = True

        self.setPreviewsPaths([self.defaultPreview])

    def loadPreview(self, pixmap: QPixmap):
        self.previewRatio = pixmap.width() / pixmap.height()
        self.body.modPreview.setPixmap(pixmap)
        self.onResize()

    def searchEvent(self, text):
        if not text:
            displayModButtons = self.modsButtons

        else:
            text = text.casefold()

            if len(text.split(" ")) == 1:
                text = f" {text}"

            displayModButtons = [
                modButton
                for modButton in self.modsButtons
                if any([
                    text in f" {modButton.modClass.name.lower()}",
                    text in f" {modButton.modClass.author.lower()}",
                    modButton.modClass.gameVersion.startswith(text.strip()),
                    any([tag.casefold().lower().startswith(text.strip()) for tag in modButton.modClass.tags])
                ])
            ]

        for modButton in self.modsButtons:
            modButton.remove()

        for modButton in displayModButtons:
            modButton.restore(self.modsList)

    def toggleListPreviews(self):
        from ..utils.config import LoaderConfig
        config = LoaderConfig()
        config.showListPreviews = not config.showListPreviews
        self.updateListPreviewsIcon()
        
        # Update all visible mod buttons to show/hide the preview
        for modButton in self.modsButtons:
            modButton.updateListPreview()
            modButton.onParentResize()

    def updateListPreviewsIcon(self):
        from ..utils.config import LoaderConfig
        if LoaderConfig().showListPreviews:
            self.ui.updateAllMods.setIcon(QIcon(":/icons/resources/icons/PreviewActive.png"))
        else:
            self.ui.updateAllMods.setIcon(QIcon(":/icons/resources/icons/Preview.png"))

    def onResize(self, *a):
        width = self.ui.scrollBody.width() - (7 if self.ui.scrollBody.verticalScrollBar().isVisible() else 0)
        imageHeight = self.ui.scrollBody.width() // self.previewRatio

        self.body.modPreview.setGeometry(0, 0, width, imageHeight)
        self.body.modPreviewInfo.setGeometry(0, 0, width, imageHeight)

        lMargin, tMargin, rMargin, bMargin = self.modDescriptionsAndActionsLayout.getContentsMargins()
        spacing = self.modDescriptionsAndActionsLayout.spacing()

        self.body.modPreviewFrame.setMinimumHeight(imageHeight)

        modDescriptionHeight = self.ui.modBody.height() - imageHeight - self.body.modTags.height() - \
                               self.body.modActions.height() - tMargin - bMargin - spacing * \
                               (self.modDescriptionsAndActionsLayout.count() - 1)

        modDescriptionDocumentHeight = self.body.modDescription.document().size().height()

        if modDescriptionDocumentHeight > modDescriptionHeight:
            self.body.modDescription.setMinimumHeight(modDescriptionDocumentHeight)
        else:
            self.body.modDescription.setMinimumHeight(modDescriptionHeight)

    def onModsListResize(self, event):
        for n in range(self.modsList.layout().count()):
            w = self.modsList.layout().takeAt(0).widget()
            w.onParentResize()
            self.modsList.layout().addWidget(w)

        self.origScrollModsListResizeEvent(event)

    def eventFilter(self, qobject, event):
        # if event.type() not in [QEvent.HoverMove, QEvent.PolishRequest, QEvent.Paint, QEvent.MouseMove]:
        #    print(event.type())

        if isinstance(event, QPaintEvent):
            self.onResize(event)

        return False

    def leftPreview(self):
        n = 0
        for preview in self.previews:
            if self.body.modPreview.pixmap().cacheKey() == preview.cacheKey():
                break
            else:
                n += 1

        if n == 0:
            self.setPreviewNum(len(self.previews) - 1)
        else:
            self.setPreviewNum(n - 1)

    def rightPreview(self):
        n = 0
        for preview in self.previews:
            if self.body.modPreview.pixmap().cacheKey() == preview.cacheKey():
                break
            else:
                n += 1

        if n == len(self.previews) - 1:
            self.setPreviewNum(0)
        else:
            self.setPreviewNum(n + 1)

    def cachePreview(self, path: str) -> QPixmap:
        if path not in self.cachePreviews:
            pixmap = QPixmap(path.replace("\\", "/"))
            self.cachePreviews[path] = pixmap
        else:
            pixmap = self.cachePreviews[path]

        return pixmap

    def setPreviewNum(self, n):
        if -1 < n < len(self.previews):
            self.previewsNavigate[n].setActive()
            self.loadPreview(self.previews[n])

    def setPreviewsPaths(self, paths: List[str]):
        self.previews.clear()

        for previewNavigate in self.previewsNavigate:
            if previewNavigate.hasParent():
                previewNavigate.remove()

        for n in range(len(paths)):
            self.previewsNavigate[n].addToFrame(self.body.previewsNavigateFrame)
            if n == 0:
                self.previewsNavigate[n].pressed()
                self.previewsNavigate[n].released()

        if not paths:
            paths = [self.defaultPreview]

        if len(paths) == 1:
            self.body.leftPreview.setMaximumWidth(0)
            self.body.rightPreview.setMaximumWidth(0)
        else:
            self.body.leftPreview.setMaximumWidth(30)
            self.body.rightPreview.setMaximumWidth(30)

        for n, path in enumerate(paths):
            pixmap = self.cachePreview(path)
            self.previews.append(pixmap)

        self.loadPreview(self.previews[0])

    def updateData(self):
        modClass = self.selectedModButton.modClass

        self.modsActions.webPage.setParent(None)
        self.modsActions.install.setParent(None)
        self.modsActions.uninstall.setParent(None)
        self.modsActions.reinstall.setParent(None)
        self.modsActions.update.setParent(None)
        self.modsActions.deleteMod.setParent(None)

        if modClass.installed:
            if modClass.modFileExist:
                AddToFrame(self.modsActions.mainFrame, self.modsActions.reinstall)
            AddToFrame(self.modsActions.mainFrame, self.modsActions.uninstall)
        elif modClass.modFileExist:
            AddToFrame(self.modsActions.mainFrame, self.modsActions.install)

        #if modClass.modFileExist:
        AddToFrame(self.modsActions.mainFrame, self.modsActions.deleteMod)

        import re
        is_ex = bool(re.search(r'\bEX\b', modClass.name, re.IGNORECASE))
        if is_ex:
            self.body.modName.setStyleSheet("color: #FFA500;")
        else:
            self.body.modName.setStyleSheet("color: #eeeeee;")

        self.setPreviewsPaths(modClass.previewsPaths)
        self.body.modName.setText(modClass.name)
        source_text = modClass.platform if modClass.platform is not None else ""
        self.body.modSource.setText("Source: " + source_text)
        self.body.modVersion.setText("Version: " + modClass.version)

        desc = modClass.description or ""
        if is_ex:
            ex_warning_html = (
                '<p style="color: #FFA500; font-weight: bold; background-color: #2D1E00; padding: 8px; border: 1px solid #FF8C00; border-radius: 4px;">'
                'WARNING: This Mod is an EX-type mod. The official modloader may not support all features of this mod, '
                'use the Unofficial Modloader to use it: '
                '<a href="https://gamebanana.com/tools/20722" style="color: #3498db; text-decoration: underline;">https://gamebanana.com/tools/20722</a>'
                '</p><br/>'
            )
            if "<body>" in desc:
                desc = desc.replace("<body>", "<body>" + ex_warning_html)
            else:
                desc = ex_warning_html + desc

        self.body.modDescription.setText(desc)
        self.body.modTags.setText("Tags: " + ", ".join(modClass.tags))

    def selectMod(self, modClass: ModClass):
        for modButton in self.modsButtons:
            if modButton.modClass == modClass:
                self.selectedModButton = modButton

        self.updateData()

    def addModButton(self, modClass: ModClass):
        modButton = ModButton(modClass=modClass,
                              method=self.selectMod,
                              favoriteMethod=self.toggleFavoriteMethod)

        self.modsButtons.append(modButton)
        AddToFrame(self.modsList, modButton)

        if not self.selectedModButton:
            modButton.select()

    def addMod(self,
               gameVersion: str,
               name: str,
               author: str,
               version: str,
               description: str,
               tags: List[str],
               previewsPaths: List[str],
               hash: str,
               platform: str,
               installed: bool,
               currentVersion: bool,
               modFileExist: bool,
               date: float = 0.0,
               favorite: bool = False):

        for path in previewsPaths:
            self.cachePreview(path)

        mod = ModClass(gameVersion,
                       name,
                       author,
                       version,
                       description,
                       tags,
                       previewsPaths,
                       hash,
                       platform,
                       installed,
                       currentVersion,
                       modFileExist,
                       date,
                       favorite)

        self.mods[hash] = mod
        self.addModButton(mod)
        
    def removeAllMods(self):
        ClearFrame(self.modsList)

        self.selectedModButton = None
        for modButton in self.modsButtons:
            modButton.cleanup()
        self.modsButtons.clear()

        # Clear global preview cache to free up RAM
        SetPreview.cachedPreviews.clear()

        for modClass in self.mods.values():
            del modClass
        self.mods.clear()

    def showSortMenu(self):
        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QAction
        
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #151518;
                color: #ffffff;
                border: 1px solid #404146;
            }
            QMenu::item:selected {
                background-color: #42A5F5;
                color: #ffffff;
            }
        """)
        
        az_action = QAction("A-Z", self)
        az_action.triggered.connect(lambda: self.applySort("Name", False))
        
        za_action = QAction("Z-A", self)
        za_action.triggered.connect(lambda: self.applySort("Name", True))
        
        newest_action = QAction("Newest to Oldest", self)
        newest_action.triggered.connect(lambda: self.applySort("Date", True))
        
        oldest_action = QAction("Oldest to Newest", self)
        oldest_action.triggered.connect(lambda: self.applySort("Date", False))
        
        installed_action = QAction("Installed First", self)
        installed_action.triggered.connect(lambda: self.applySort("Installed", False))
        
        author_action = QAction("Author", self)
        author_action.triggered.connect(lambda: self.applySort("Author", False))
        
        menu.addAction(az_action)
        menu.addAction(za_action)
        menu.addSeparator()
        menu.addAction(newest_action)
        menu.addAction(oldest_action)
        menu.addSeparator()
        menu.addAction(installed_action)
        menu.addAction(author_action)
        
        menu.exec(QCursor.pos())

    def applySort(self, field, reverse):
        if self.sortCallback:
            self.sortCallback(field, reverse)
            
        # Save scroll position
        scroll_bar = self.ui.scrollModsList.verticalScrollBar()
        scroll_pos = scroll_bar.value()

        # Split favorites and others
        favorites = [b for b in self.modsButtons if b.modClass.favorite]
        others = [b for b in self.modsButtons if not b.modClass.favorite]
        
        if field == "Name":
            favorites.sort(key=lambda x: x.modClass.name.lower(), reverse=reverse)
            others.sort(key=lambda x: x.modClass.name.lower(), reverse=reverse)
        elif field == "Date":
            favorites.sort(key=lambda x: float(x.modClass.date or 0), reverse=reverse)
            others.sort(key=lambda x: float(x.modClass.date or 0), reverse=reverse)
        elif field == "Installed":
            # Primary sort by installed status (True first), secondary by name (A-Z)
            favorites.sort(key=lambda x: (not x.modClass.installed, x.modClass.name.lower()))
            others.sort(key=lambda x: (not x.modClass.installed, x.modClass.name.lower()))
        elif field == "Author":
            favorites.sort(key=lambda x: (x.modClass.author.lower(), x.modClass.name.lower()), reverse=reverse)
            others.sort(key=lambda x: (x.modClass.author.lower(), x.modClass.name.lower()), reverse=reverse)

        # Merge them: favorites always first
        self.modsButtons = favorites + others

        # Re-order in the layout
        for modButton in self.modsButtons:
            self.modsList.layout().removeWidget(modButton)
            modButton.setParent(None)

        for modButton in self.modsButtons:
            AddToFrame(self.modsList, modButton)
        
        # Restore scroll position after layout updates
        QTimer.singleShot(0, lambda: scroll_bar.setValue(scroll_pos))

        # Keep selection visible if any
        if self.selectedModButton:
            self.selectedModButton.select()
