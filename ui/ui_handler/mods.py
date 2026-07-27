import os
import webbrowser
from typing import List, Dict

from PySide6.QtWidgets import QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QFrame, QLabel, QComboBox, QInputDialog, QMessageBox, QDialog
from PySide6.QtGui import QPixmap, QPaintEvent, QIcon, QCursor
from PySide6.QtCore import QSize, Qt, QTimer, Signal, QObject

from .modbutton import ModButton
from .modclass import ModClass

from ..ui_sources.ui_mods import Ui_Mods
from ..ui_sources.ui_mod_body import Ui_ModBody
from ..ui_sources.ui_mods_actions import Ui_ModsActions

from ..utils.buttons import AddButtonWidthToTexSize
from ..utils.layout import AddToFrame, ClearFrame
from ..utils.buttongroup import ButtonGroup


def get_tinted_svg_pixmap(svg_path: str, fill_color: str, size: int = 18) -> QPixmap:
    if os.path.exists(svg_path):
        try:
            with open(svg_path, 'r', encoding='utf-8') as f:
                content = f.read()
            import re
            content = re.sub(r'fill="[^"]*"', f'fill="{fill_color}"', content)
            
            from PySide6.QtSvg import QSvgRenderer
            from PySide6.QtGui import QPainter, QImage
            
            renderer = QSvgRenderer(content.encode('utf-8'))
            image = QImage(size, size, QImage.Format_ARGB32)
            image.fill(Qt.transparent)
            painter = QPainter(image)
            renderer.render(painter)
            painter.end()
            return QPixmap.fromImage(image)
        except Exception as e:
            print(f"[SVG TINT ERROR] {e}")
    return QIcon(svg_path).pixmap(size, size)


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





class TagPillWidget(QWidget):
    clicked = Signal(str)

    def __init__(self, tag_name: str, bg_color: str, parent=None):
        super().__init__(parent)
        self.tag_name = tag_name
        from PySide6.QtGui import QColor, QFont, QFontMetrics
        self.bg_color = QColor(bg_color)
        self.setCursor(Qt.PointingHandCursor)
        
        fm = QFontMetrics(QFont("Segoe UI", 8, QFont.Bold))
        w = fm.horizontalAdvance(tag_name) + 16
        self.setFixedSize(max(w, 36), 18)

    def paintEvent(self, event):
        from PySide6.QtGui import QPainter, QPainterPath, QColor, QFont
        from PySide6.QtCore import QRectF
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, self.width(), self.height()), 9, 9)
        
        p.fillPath(path, self.bg_color)
        
        p.setPen(QColor("#FFFFFF"))
        p.setFont(QFont("Segoe UI", 8, QFont.Bold))
        p.drawText(self.rect(), Qt.AlignCenter, self.tag_name)
        p.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.tag_name)
        super().mousePressEvent(event)


class Mods(QWidget):
    defaultPreview = ":/images/resources/images/DefaultPreview.png"
    cachePreviews: Dict[str, QPixmap] = {}
    selectedModButton: ModButton = None
    mods: Dict[str, ModClass] = {}
    modsButtons: List[ModButton] = []
    wikiPreviewSignal = Signal(QPixmap, str)

    def __init__(self, installMethod, uninstallMethod, reinstallMethod, deleteMethod, reloadMethod, openFolderMethod, uninstallAllMethod, toggleFavoriteMethod, sortCallback, savePresetMethod=None, deletePresetMethod=None, applyPresetMethod=None, editPresetMethod=None, reloadPresetMethod=None):
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

        self.body.modTags.setOpenExternalLinks(False)
        self.body.modTags.linkActivated.connect(self.onTagLinkClicked)

        self.body.modDescription.setOpenExternalLinks(True)
        self.body.modDescription.highlighted.connect(self.onReplacementHovered)
        self.body.modDescription.viewport().installEventFilter(self)

        # Native PySide6 Single Unified Wiki Image Preview Card Container
        self.wikiPreviewCard = QFrame(None, Qt.ToolTip | Qt.FramelessWindowHint)
        self.wikiPreviewCard.setStyleSheet("""
            QFrame {
                background-color: #15161A;
                border: 1px solid #33343A;
                border-radius: 8px;
            }
        """)
        cardLayout = QVBoxLayout(self.wikiPreviewCard)
        cardLayout.setContentsMargins(8, 8, 8, 8)
        cardLayout.setSpacing(6)

        self.wikiPreviewTitle = QLabel()
        self.wikiPreviewTitle.setStyleSheet("color: #FFFFFF; font-size: 11px; font-weight: bold; background: transparent; border: none;")
        self.wikiPreviewTitle.setAlignment(Qt.AlignCenter)
        cardLayout.addWidget(self.wikiPreviewTitle)

        self.wikiPreviewImageLabel = QLabel()
        self.wikiPreviewImageLabel.setStyleSheet("background: transparent; border: none;")
        self.wikiPreviewImageLabel.setAlignment(Qt.AlignCenter)
        cardLayout.addWidget(self.wikiPreviewImageLabel)

        self.wikiPreviewCard.hide()
        self.wikiPreviewSignal.connect(self.showWikiPreviewCard)

        icons_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ui_sources", "resources", "icons"))
        mod_warning_icon_path = os.path.join(icons_dir, "ModWarning.svg")

        self.ui.modsList.setMaximumWidth(16777215)
        self.ui.splitter.setStretchFactor(0, 1)
        self.ui.splitter.setStretchFactor(1, 1)
        self.ui.splitter.setSizes([425, 425])

        # Skin Warning Notice (Coral #FF7043)
        self.warningFrame = QFrame()
        self.warningFrame.setStyleSheet("background-color: #1A1B1E; border-radius: 6px; border: 1px solid #2B2C30; margin: 4px 0px;")
        warningLayout = QHBoxLayout(self.warningFrame)
        warningLayout.setContentsMargins(10, 6, 10, 6)
        warningLayout.setSpacing(10)

        warningIconLabel = QLabel()
        warningIconLabel.setPixmap(get_tinted_svg_pixmap(mod_warning_icon_path, "#FF7043", 18))
        warningIconLabel.setStyleSheet("background: transparent; border: none; padding: 0px;")
        warningLayout.addWidget(warningIconLabel)

        warningTextLabel = QLabel("Remember that any existing skin mod requires a PAID skin, check the REQUIREMENTS section in GameBanana to find out which skin it replaces.")
        warningTextLabel.setWordWrap(True)
        warningTextLabel.setStyleSheet("color: #FF7043; font-size: 10px; font-weight: bold; border: none; background: transparent;")
        warningLayout.addWidget(warningTextLabel, 1)

        self.modDescriptionsAndActionsLayout.insertWidget(2, self.warningFrame)

        # EX Mod Warning Notice (Gold/Amber #FFA500)
        self.exWarningFrame = QFrame()
        self.exWarningFrame.setStyleSheet("background-color: #1A1B1E; border-radius: 6px; border: 1px solid #2B2C30; margin: 4px 0px;")
        exWarningLayout = QHBoxLayout(self.exWarningFrame)
        exWarningLayout.setContentsMargins(10, 6, 10, 6)
        exWarningLayout.setSpacing(10)

        exWarningIconLabel = QLabel()
        exWarningIconLabel.setPixmap(get_tinted_svg_pixmap(mod_warning_icon_path, "#FFA500", 18))
        exWarningIconLabel.setStyleSheet("background: transparent; border: none; padding: 0px;")
        exWarningLayout.addWidget(exWarningIconLabel)

        exWarningTextLabel = QLabel(
            "WARNING: This Mod is an EX-type mod. The official modloader may not support all features of this mod, "
            "use the Unofficial Modloader to use it: "
            "<a href=\"https://gamebanana.com/tools/20722\" style=\"color: #3498db; text-decoration: underline;\">https://gamebanana.com/tools/20722</a>"
        )
        exWarningTextLabel.setWordWrap(True)
        exWarningTextLabel.setOpenExternalLinks(True)
        exWarningTextLabel.setStyleSheet("color: #FFA500; font-size: 10px; font-weight: bold; border: none; background: transparent;")
        exWarningLayout.addWidget(exWarningTextLabel, 1)

        self.modDescriptionsAndActionsLayout.insertWidget(3, self.exWarningFrame)
        self.exWarningFrame.hide()

        modsListFrame = QFrame()
        layout = QVBoxLayout(modsListFrame)
        layout.setSpacing(0)
        layout.setContentsMargins(2, 5, 2, 5)
        self.modsList = QFrame()
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

        self.savePresetMethod = savePresetMethod
        self.deletePresetMethod = deletePresetMethod
        self.applyPresetMethod = applyPresetMethod
        self.editPresetMethod = editPresetMethod
        self.reloadPresetMethod = reloadPresetMethod

        # Resolve icon paths
        save_icon_path = os.path.join(icons_dir, "Save.svg")
        edit_icon_path = os.path.join(icons_dir, "Edit.svg")
        reload_icon_path = os.path.join(icons_dir, "Reload.svg")
        delete_icon_path = os.path.join(icons_dir, "Delete.svg")
        launch_icon_path = os.path.join(icons_dir, "Launch.svg")

        # Dedicated Presets & Launch toolbar
        self.presetsBarFrame = QFrame(self.ui.modsList)
        self.presetsBarFrame.setMinimumSize(QSize(0, 36))
        self.presetsBarFrame.setMaximumSize(QSize(16777215, 36))
        self.presetsBarFrame.setStyleSheet("background-color: #111113; border-bottom: 1px solid #1E1F24;")
        self.presetsBarLayout = QHBoxLayout(self.presetsBarFrame)
        self.presetsBarLayout.setContentsMargins(4, 3, 4, 3)
        self.presetsBarLayout.setSpacing(4)

        # Presets Combo Box (Compact width capped at 130px)
        self.presetCombo = QComboBox(self.presetsBarFrame)
        self.presetCombo.setMinimumHeight(28)
        self.presetCombo.setMaximumWidth(130)
        self.presetCombo.setCursor(Qt.PointingHandCursor)
        self.presetCombo.setStyleSheet("""
            QComboBox {
                background-color: #1A1B1F;
                color: #FFFFFF;
                border: 1px solid #33343A;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 11px;
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background-color: #151518;
                color: #FFFFFF;
                selection-background-color: #24638C;
            }
        """)
        self.presetCombo.setToolTip("Select or apply a mod preset profile")
        self.presetCombo.currentIndexChanged.connect(self.onPresetComboChanged)
        self.presetsBarLayout.addWidget(self.presetCombo, 0)

        # Save Preset Button (Save.svg)
        self.savePresetBtn = QPushButton(self.presetsBarFrame)
        self.savePresetBtn.setFixedSize(QSize(28, 28))
        self.savePresetBtn.setCursor(Qt.PointingHandCursor)
        if os.path.exists(save_icon_path):
            self.savePresetBtn.setIcon(QIcon(save_icon_path))
        else:
            self.savePresetBtn.setIcon(QIcon(":/icons/resources/icons/Save.png"))
        self.savePresetBtn.setIconSize(QSize(16, 16))
        self.savePresetBtn.setToolTip("Save Current Installed Mods as Preset")
        self.savePresetBtn.setStyleSheet("QPushButton { background-color: #1A1B1F; border: 1px solid #33343A; border-radius: 8px; } QPushButton:hover { background-color: #2A2C32; }")
        self.savePresetBtn.clicked.connect(self.onSavePresetClicked)
        self.presetsBarLayout.addWidget(self.savePresetBtn)

        # Edit/Rename Preset Button (Edit.svg)
        self.editPresetBtn = QPushButton(self.presetsBarFrame)
        self.editPresetBtn.setFixedSize(QSize(28, 28))
        self.editPresetBtn.setCursor(Qt.PointingHandCursor)
        if os.path.exists(edit_icon_path):
            self.editPresetBtn.setIcon(QIcon(edit_icon_path))
        self.editPresetBtn.setIconSize(QSize(16, 16))
        self.editPresetBtn.setToolTip("Rename Selected Preset Profile")
        self.editPresetBtn.setStyleSheet("QPushButton { background-color: #1A1B1F; border: 1px solid #33343A; border-radius: 8px; } QPushButton:hover { background-color: #2A2C32; }")
        self.editPresetBtn.clicked.connect(self.onEditPresetClicked)
        self.presetsBarLayout.addWidget(self.editPresetBtn)

        # Reload/Sync Preset Button (Reload.svg)
        self.reloadPresetBtn = QPushButton(self.presetsBarFrame)
        self.reloadPresetBtn.setFixedSize(QSize(28, 28))
        self.reloadPresetBtn.setCursor(Qt.PointingHandCursor)
        if os.path.exists(reload_icon_path):
            self.reloadPresetBtn.setIcon(QIcon(reload_icon_path))
        self.reloadPresetBtn.setIconSize(QSize(16, 16))
        self.reloadPresetBtn.setToolTip("Re-apply / Sync Selected Preset")
        self.reloadPresetBtn.setStyleSheet("QPushButton { background-color: #1A1B1F; border: 1px solid #33343A; border-radius: 8px; } QPushButton:hover { background-color: #2A2C32; }")
        self.reloadPresetBtn.clicked.connect(self.onReloadPresetClicked)
        self.presetsBarLayout.addWidget(self.reloadPresetBtn)

        # Delete Preset Button (Delete.svg)
        self.deletePresetBtn = QPushButton(self.presetsBarFrame)
        self.deletePresetBtn.setFixedSize(QSize(28, 28))
        self.deletePresetBtn.setCursor(Qt.PointingHandCursor)
        if os.path.exists(delete_icon_path):
            self.deletePresetBtn.setIcon(QIcon(delete_icon_path))
        else:
            self.deletePresetBtn.setIcon(QIcon(":/icons/resources/icons/Delete.png"))
        self.deletePresetBtn.setIconSize(QSize(16, 16))
        self.deletePresetBtn.setToolTip("Delete Selected Preset Profile")
        self.deletePresetBtn.setStyleSheet("QPushButton { background-color: #1A1B1F; border: 1px solid #33343A; border-radius: 8px; } QPushButton:hover { background-color: #3A1B1B; }")
        self.deletePresetBtn.clicked.connect(self.onDeletePresetClicked)
        self.presetsBarLayout.addWidget(self.deletePresetBtn)

        # Launch Brawlhalla Button (Launch.svg)
        self.launchBrawlhallaBtn = QPushButton("Launch Brawlhalla!", self.presetsBarFrame)
        self.launchBrawlhallaBtn.setMinimumHeight(28)
        self.launchBrawlhallaBtn.setCursor(Qt.PointingHandCursor)
        if os.path.exists(launch_icon_path):
            self.launchBrawlhallaBtn.setIcon(QIcon(launch_icon_path))
        self.launchBrawlhallaBtn.setIconSize(QSize(16, 16))
        self.launchBrawlhallaBtn.setToolTip("Launch Brawlhalla")
        self.launchBrawlhallaBtn.setStyleSheet("""
            QPushButton {
                background-color: #2ECC71;
                color: #FFFFFF;
                font-weight: bold;
                font-size: 11px;
                border-radius: 8px;
                padding: 4px 8px;
                border: none;
            }
            QPushButton:hover { background-color: #27AE60; }
            QPushButton:pressed { background-color: #1E8449; }
        """)
        self.launchBrawlhallaBtn.clicked.connect(lambda: webbrowser.open("steam://rungameid/291550"))
        self.presetsBarLayout.addWidget(self.launchBrawlhallaBtn)

        # Presets at Top (index 0), Search Bar Below Presets (index 1)
        self.ui.verticalLayout.insertWidget(0, self.presetsBarFrame)
        self.ui.verticalLayout.insertWidget(1, self.ui.searchFrame)

        self.loadPresetsList()

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

    def loadPresetsList(self):
        from ..utils.config import LoaderConfig
        config = LoaderConfig()
        if hasattr(self, 'presetCombo'):
            self.presetCombo.blockSignals(True)
            self.presetCombo.clear()
            self.presetCombo.addItem("+ Add New Preset")
            for name in config.presets.keys():
                self.presetCombo.addItem(name)

            last_preset = config.lastSelectedPreset
            if last_preset and last_preset in config.presets:
                idx = self.presetCombo.findText(last_preset)
                if idx > 0:
                    self.presetCombo.setCurrentIndex(idx)
            else:
                self.presetCombo.setCurrentIndex(0)
            self.presetCombo.blockSignals(False)

    def onPresetComboChanged(self, index):
        from ..utils.config import LoaderConfig
        config = LoaderConfig()
        if index == 0:
            self.promptNewPreset()
        elif index > 0:
            preset_name = self.presetCombo.itemText(index)
            config.lastSelectedPreset = preset_name
            if hasattr(self, 'applyPresetMethod') and self.applyPresetMethod:
                self.applyPresetMethod(preset_name)

    def promptNewPreset(self):
        dialog = QInputDialog(self)
        dialog.setWindowTitle("Create New Mod Preset")
        dialog.setLabelText("Enter a name for the new mod preset:")
        dialog.setStyleSheet("""
            QInputDialog { background-color: #141518; color: #FFFFFF; }
            QLabel { color: #FFFFFF; font-size: 12px; font-weight: bold; }
            QLineEdit { background-color: #1F2024; color: #FFFFFF; border: 1px solid #24638C; border-radius: 4px; padding: 6px; font-size: 12px; }
            QPushButton { background-color: #24638C; color: #FFFFFF; border-radius: 4px; padding: 6px 14px; font-weight: bold; }
            QPushButton:hover { background-color: #347BA9; }
        """)
        ok = dialog.exec()
        name = dialog.textValue().strip()
        if ok == QDialog.Accepted and name:
            from ..utils.config import LoaderConfig
            config = LoaderConfig()
            if name in config.presets:
                msgBox = QMessageBox(self)
                msgBox.setWindowTitle("Overwrite Preset")
                msgBox.setText(f"Preset '{name}' already exists. Do you want to overwrite it?")
                msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                msgBox.setStyleSheet("""
                    QMessageBox { background-color: #141518; color: #FFFFFF; }
                    QLabel { color: #FFFFFF; font-size: 12px; }
                    QPushButton { background-color: #24638C; color: #FFFFFF; border-radius: 4px; padding: 5px 12px; }
                """)
                reply = msgBox.exec()
                if reply != QMessageBox.Yes:
                    return
            if hasattr(self, 'savePresetMethod') and self.savePresetMethod:
                self.savePresetMethod(name)

    def onSavePresetClicked(self):
        current_idx = self.presetCombo.currentIndex()
        if current_idx > 0:
            preset_name = self.presetCombo.currentText()
            if hasattr(self, 'savePresetMethod') and self.savePresetMethod:
                self.savePresetMethod(preset_name)
        else:
            self.promptNewPreset()

    def onEditPresetClicked(self):
        current = self.presetCombo.currentText()
        if self.presetCombo.currentIndex() > 0 and current:
            dialog = QInputDialog(self)
            dialog.setWindowTitle("Rename Preset")
            dialog.setLabelText(f"Enter new name for preset '{current}':")
            dialog.setTextValue(current)
            dialog.setStyleSheet("""
                QInputDialog { background-color: #141518; color: #FFFFFF; }
                QLabel { color: #FFFFFF; font-size: 12px; font-weight: bold; }
                QLineEdit { background-color: #1F2024; color: #FFFFFF; border: 1px solid #24638C; border-radius: 4px; padding: 6px; font-size: 12px; }
                QPushButton { background-color: #24638C; color: #FFFFFF; border-radius: 4px; padding: 6px 14px; font-weight: bold; }
                QPushButton:hover { background-color: #347BA9; }
            """)
            ok = dialog.exec()
            new_name = dialog.textValue().strip()
            if ok == QDialog.Accepted and new_name and new_name != current:
                if hasattr(self, 'editPresetMethod') and self.editPresetMethod:
                    self.editPresetMethod(current, new_name)

    def onReloadPresetClicked(self):
        current = self.presetCombo.currentText()
        if self.presetCombo.currentIndex() > 0 and current:
            if hasattr(self, 'reloadPresetMethod') and self.reloadPresetMethod:
                self.reloadPresetMethod(current)

    def onDeletePresetClicked(self):
        current = self.presetCombo.currentText()
        if self.presetCombo.currentIndex() > 0 and current:
            msgBox = QMessageBox(self)
            msgBox.setWindowTitle("Delete Preset")
            msgBox.setText(f"Are you sure you want to delete preset '{current}'?")
            msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msgBox.setStyleSheet("""
                QMessageBox { background-color: #141518; color: #FFFFFF; }
                QLabel { color: #FFFFFF; font-size: 12px; }
                QPushButton { background-color: #24638C; color: #FFFFFF; border-radius: 4px; padding: 5px 12px; }
            """)
            reply = msgBox.exec()
            if reply == QMessageBox.Yes and hasattr(self, 'deletePresetMethod') and self.deletePresetMethod:
                self.deletePresetMethod(current)

        self.setPreviewsPaths([self.defaultPreview])

    def loadPreview(self, pixmap: QPixmap):
        self.previewRatio = pixmap.width() / pixmap.height()
        self.body.modPreview.setPixmap(pixmap)
        self.onResize()

    def onReplacementHovered(self, url):
        url_str = url.toString() if hasattr(url, 'toString') else str(url or "")
        if url_str and "brawlhalla.wiki.gg/wiki/" in url_str:
            slug = url_str.split("brawlhalla.wiki.gg/wiki/")[-1].split("#")[0]
            clean_name = slug.replace("_", " ")

            import threading
            threading.Thread(target=self._fetch_and_show_wiki_preview, args=(slug, clean_name), daemon=True).start()
        else:
            self.wikiPreviewCard.hide()

    def _fetch_and_show_wiki_preview(self, slug: str, clean_name: str):
        import requests
        from PySide6.QtGui import QImage, QPixmap

        cache_dir = os.path.join(os.environ.get("APPDATA", ""), "BModLoader", "wiki_cache")
        os.makedirs(cache_dir, exist_ok=True)
        cache_file = os.path.join(cache_dir, f"{slug}.png")

        dataData = None
        if os.path.exists(cache_file) and os.path.getsize(cache_file) > 100:
            try:
                with open(cache_file, "rb") as f:
                    dataData = f.read()
            except: pass

        if not dataData:
            thumb_url = f"https://brawlhalla.wiki.gg/images/thumb/{slug}.png/150px-{slug}.png"
            full_url = f"https://brawlhalla.wiki.gg/images/{slug}.png"
            for url in [thumb_url, full_url]:
                try:
                    r = requests.get(url, timeout=2)
                    if r.status_code == 200 and len(r.content) > 100:
                        dataData = r.content
                        with open(cache_file, "wb") as f:
                            f.write(dataData)
                        break
                except: pass

        if dataData:
            img = QImage()
            if img.loadFromData(dataData):
                pixmap = QPixmap.fromImage(img).scaled(230, 230, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.wikiPreviewSignal.emit(pixmap, clean_name)

    def showWikiPreviewCard(self, pixmap: QPixmap, clean_name: str):
        from PySide6.QtCore import QPoint
        from PySide6.QtGui import QCursor
        self.wikiPreviewTitle.setText(clean_name)
        self.wikiPreviewImageLabel.setPixmap(pixmap)
        self.wikiPreviewCard.adjustSize()
        card_h = self.wikiPreviewCard.height()
        pos = QCursor.pos() + QPoint(12, -card_h - 6)
        self.wikiPreviewCard.move(pos)
        self.wikiPreviewCard.show()
        self.wikiPreviewCard.raise_()

    def eventFilter(self, watched, event):
        if hasattr(self, 'body') and hasattr(self.body, 'modDescription') and watched == self.body.modDescription.viewport():
            if event.type() in (QEvent.Leave, QEvent.FocusOut):
                if hasattr(self, 'wikiPreviewCard'):
                    self.wikiPreviewCard.hide()
        return super().eventFilter(watched, event)

    def onTagButtonClicked(self, tag_name: str):
        self.ui.searchArea.setText(tag_name)
        self.searchEvent(tag_name)

    def onTagLinkClicked(self, link: str):
        if link.startswith("tag:"):
            tag_name = link[4:]
            self.onTagButtonClicked(tag_name)

    def searchEvent(self, text):
        if not text:
            displayModButtons = self.modsButtons

        else:
            text = text.casefold().strip()

            from ..utils.tags_helper import auto_detect_tags
            displayModButtons = []
            for modButton in self.modsButtons:
                replacements = self.getModReplacements(modButton.modClass)
                auto_tags = auto_detect_tags(modButton.modClass, replacements)
                modButton.modClass.tags = auto_tags
                
                name_match = text in modButton.modClass.name.lower()
                author_match = text in modButton.modClass.author.lower()
                version_match = modButton.modClass.gameVersion.lower().startswith(text)
                tag_match = any(text in t.lower() for t in auto_tags)
                rep_match = any(text in r.lower() for r in replacements)

                if name_match or author_match or version_match or tag_match or rep_match:
                    displayModButtons.append(modButton)

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

    def getModReplacements(self, modClass: ModClass) -> List[str]:
        from ..utils.config import LoaderConfig
        from ..utils.lang_reader import get_global_lang_reader, get_cached_replacements, set_cached_replacements

        # Hash-based cache: compute once per mod, reuse on every select click
        cached = get_cached_replacements(modClass.hash)
        if cached is not None:
            return cached

        config = LoaderConfig()
        bh_path = config.brawlhallaPath
        if not bh_path or not os.path.exists(os.path.join(bh_path, "languages")):
            possible_path = "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Brawlhalla"
            if os.path.exists(os.path.join(possible_path, "languages")):
                bh_path = possible_path

        lang_reader = None
        if bh_path and os.path.exists(os.path.join(bh_path, "languages")):
            lang_reader = get_global_lang_reader(os.path.join(bh_path, "languages"))

        # Sprite part_type prefix -> weapon type display name
        # Keys are the exact first segment after stripping "a_" prefix from symbolclass names
        WEAPON_PREFIXES = {
            'WeaponHammer': 'Hammer',
            'WeaponHammerShort': 'Hammer',
            'WeaponRocketLance': 'Rocket Lance',
            'WeaponRocketLanceShort': 'Rocket Lance',
            'WeaponSword': 'Sword',
            'WeaponSwordShort': 'Sword',
            'WeaponSpear': 'Spear',
            'WeaponSpearShort': 'Spear',
            'WeaponPistol': 'Blasters',
            'WeaponPistolShort': 'Blasters',
            'WeaponKatar': 'Katars',
            'WeaponKatarShort': 'Katars',
            'WeaponAxe': 'Axe',
            'WeaponAxeShort': 'Axe',
            'WeaponBow': 'Bow',
            'WeaponBowShort': 'Bow',
            'WeaponGloves': 'Gauntlets',
            'WeaponGlovesShort': 'Gauntlets',
            'WeaponFists': 'Gauntlets',
            'WeaponFistsShort': 'Gauntlets',
            'WeaponScythe': 'Scythe',
            'WeaponScytheShort': 'Scythe',
            'WeaponCannon': 'Cannon',
            'WeaponCannonShort': 'Cannon',
            'WeaponOrb': 'Orb',
            'WeaponOrbShort': 'Orb',
            'WeaponChakram': 'Orb',
            'WeaponGreatsword': 'Greatsword',
            'WeaponGreatswordShort': 'Greatsword',
            'WeaponGreat': 'Greatsword',
            'WeaponBoots': 'Battle Boots',
            'WeaponBootsShort': 'Battle Boots',
        }

        replacements = []
        seen = set()

        sprites_to_process = modClass.spriteNames if hasattr(modClass, 'spriteNames') and modClass.spriteNames else []

        if not sprites_to_process:
            for swf in modClass.swfNames:
                base = os.path.basename(swf)
                if any(base.lower().startswith(p) for p in ["bones", "sfx", "ui"]):
                    continue
                clean = base.replace(".swf", "").replace(".SWF", "").replace("Gfx_", "").replace("gfx_", "")
                if clean:
                    sprites_to_process.append(f"a_Torso_{clean}")

        for sprite in sprites_to_process:
            clean = sprite
            if clean.startswith("a_"):
                clean = clean[2:]
            
            parts = clean.split("_")
            if len(parts) < 2:
                continue

            part_type = parts[0]
            code = "_".join(parts[1:])

            if not code or code.isdigit() or len(code) < 2:
                continue

            weapon_type = None
            for w_prefix, w_name in WEAPON_PREFIXES.items():
                if part_type == w_prefix or part_type.startswith(w_prefix):
                    weapon_type = w_name
                    break

            item = None
            if lang_reader:
                if weapon_type:
                    item = lang_reader.resolve_weapon(code, weapon_type)
                else:
                    item = lang_reader.resolve_costume(code)

            if item and item not in seen:
                seen.add(item)
                replacements.append(item)

        set_cached_replacements(modClass.hash, replacements)
        return replacements

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

        AddToFrame(self.modsActions.mainFrame, self.modsActions.deleteMod)

        import re
        is_ex = bool(re.search(r'\bEX\b', modClass.name, re.IGNORECASE))
        if is_ex:
            self.body.modName.setStyleSheet("color: #FFA500;")
            if hasattr(self, 'exWarningFrame'):
                self.exWarningFrame.show()
        else:
            self.body.modName.setStyleSheet("color: #eeeeee;")
            if hasattr(self, 'exWarningFrame'):
                self.exWarningFrame.hide()

        self.setPreviewsPaths(modClass.previewsPaths)
        self.body.modName.setText(modClass.name)
        source_text = modClass.platform if modClass.platform is not None else ""
        self.body.modSource.setText("Source: " + source_text)
        self.body.modVersion.setText("Version: " + modClass.version)

        desc = modClass.description or ""
        replacements = self.getModReplacements(modClass)

        if replacements:
            import urllib.parse
            total_count = len(replacements)
            display_items = replacements[:15]
            
            replaces_html = "<br/><div style='margin-top: 12px; border-top: 1px solid #33333A; padding-top: 10px;'>"
            replaces_html += "<b style='color: #42A5F5; font-size: 12px;'>This mod replaces:</b><ul style='margin-top: 4px; margin-bottom: 4px; padding-left: 20px; color: #FFFFFF; font-size: 11px;'>"
            for item in display_items:
                clean_name = item.split('(')[0].strip()
                slug = clean_name.replace(' ', '_').replace("'", "%27")
                wiki_url = f"https://brawlhalla.wiki.gg/wiki/{slug}"
                replaces_html += f"<li style='margin-bottom: 3px;'><a href='{wiki_url}' style='color: #42A5F5; text-decoration: underline;'>{item}</a></li>"
            replaces_html += "</ul>"

            if total_count > 15:
                extra = total_count - 15
                replaces_html += f"<p style='color: #9E9E9E; font-size: 11px; font-style: italic; margin-left: 5px;'>And {extra} More...</p>"
            
            replaces_html += "</div>"
            desc += replaces_html

        self.body.modDescription.setText(desc)

        from ..utils.tags_helper import auto_detect_tags
        auto_tags = auto_detect_tags(modClass, replacements)
        modClass.tags = auto_tags
        self.updateTagPills(auto_tags)

    def updateTagPills(self, tags: List[str]):
        from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel
        from ..utils.tags_helper import get_category_color, normalize_tag

        if not hasattr(self, 'tagsContainerFrame'):
            self.tagsContainerFrame = QFrame()
            self.tagsContainerFrame.setStyleSheet("background: transparent; border: none; margin: 4px 0px;")
            self.tagsContainerLayout = QVBoxLayout(self.tagsContainerFrame)
            self.tagsContainerLayout.setContentsMargins(0, 0, 0, 0)
            self.tagsContainerLayout.setSpacing(6)
            self.modDescriptionsAndActionsLayout.insertWidget(1, self.tagsContainerFrame)
            self.body.modTags.hide()

        while self.tagsContainerLayout.count():
            item = self.tagsContainerLayout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        if not tags:
            return

        seen_norm = set()
        clean_tags = []
        for t in tags:
            nt = normalize_tag(t)
            if nt.lower() not in seen_norm:
                clean_tags.append(nt)
                seen_norm.add(nt.lower())

        display_tags = clean_tags[:10]

        row_frame = None
        row_layout = None

        for i, tag in enumerate(display_tags):
            if i % 4 == 0:
                if row_layout:
                    row_layout.addStretch()
                row_frame = QFrame()
                row_frame.setStyleSheet("background: transparent; border: none;")
                row_layout = QHBoxLayout(row_frame)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.setSpacing(6)
                self.tagsContainerLayout.addWidget(row_frame)

            bg_color = get_category_color(tag)
            btn = TagPillWidget(tag, bg_color)
            btn.clicked.connect(self.onTagButtonClicked)
            row_layout.addWidget(btn)

        if row_layout:
            row_layout.addStretch()

        if len(clean_tags) > 10:
            extra = len(clean_tags) - 10
            lbl = QLabel(f"and {extra} more...")
            lbl.setStyleSheet("color: #888888; font-size: 11px; font-style: italic; background: transparent; border: none;")
            if row_layout:
                row_layout.addWidget(lbl)

        self.tagsContainerLayout.addStretch()

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
               favorite: bool = False,
               swfNames: List[str] = None,
               fileNames: List[str] = None,
               spriteNames: List[str] = None):

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
                       favorite,
                       swfNames,
                       fileNames,
                       spriteNames)

        from ..utils.tags_helper import auto_detect_tags
        replacements = self.getModReplacements(mod)
        mod.tags = auto_detect_tags(mod, replacements)

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
