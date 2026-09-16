import os
import shutil
import webbrowser
from typing import List, Dict, Tuple

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
    wikiPreviewSignal = Signal(QPixmap, str, str)

    def __init__(self, installMethod, uninstallMethod, reinstallMethod, deleteMethod, reloadMethod, openFolderMethod, uninstallAllMethod, toggleFavoriteMethod, sortCallback, savePresetMethod=None, deletePresetMethod=None, applyPresetMethod=None, editPresetMethod=None, reloadPresetMethod=None, modsPath: str = "", controllerGetter=None, bulkInstallMethod=None, bulkUninstallMethod=None, fixMethod=None):
        super().__init__()

        self.modsPath = modsPath
        self.controllerGetter = controllerGetter
        self.reloadMethod = reloadMethod
        self.fixMethod = fixMethod
        self.bulkInstallMethod = bulkInstallMethod
        self.bulkUninstallMethod = bulkUninstallMethod
        self.modGroupsWidgets: Dict[str, QWidget] = {}
        from ..utils.config import LoaderConfig
        _cfg = LoaderConfig()
        self.currentSortField = _cfg.sortField
        self.currentSortReverse = _cfg.sortReverse


        self.active_hover_slug = None
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
        SCROLLBAR_STYLE = """
            QScrollBar:vertical {
                border: none;
                background: #2B2C32;
                width: 7px;
                margin: 0 0 0 0;
                border-radius: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: #616161;
                min-height: 30px;
                border-radius: 7px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #A1A1A1;
            }
            QScrollBar::handle:vertical:pressed {
                background-color: #717171;
            }
            QScrollBar::sub-line:vertical {
                border: none;
                background: none;
                height: 0px;
            }
            QScrollBar::add-line:vertical {
                border: none;
                background: none;
                height: 0px;
            }
            QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical {
                background: none;
                border: none;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
                border: none;
            }
        """

        bodyWidget = QWidget()
        bodyWidget.setObjectName("ModBody")
        bodyWidget.setStyleSheet("background-color: #303136; border: none;")
        self.body = Ui_ModBody()
        self.body.setupUi(bodyWidget)
        
        self.ui.scrollBody.setStyleSheet(f"""
            QScrollArea {{
                background-color: #303136;
                border: none;
            }}
            {SCROLLBAR_STYLE}
        """)
        self.ui.scrollBody.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.ui.scrollBody.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.ui.scrollBody.verticalScrollBar().setStyleSheet(SCROLLBAR_STYLE)
        self.ui.scrollBody.setWidget(bodyWidget)
        
        self.body.modDescription.verticalScrollBar().setStyleSheet(SCROLLBAR_STYLE)
        self.ui.scrollModsList.verticalScrollBar().setStyleSheet(SCROLLBAR_STYLE)
        self.ui.modBody.setStyleSheet("QFrame#modBody { background-color: #303136; border: none; }")

        self.ui.modBody.installEventFilter(self)
        self.modDescriptionsAndActionsLayout = self.body.modDescriptionsAndActions.layout()

        self.body.leftPreview.clicked.connect(self.leftPreview)
        self.body.rightPreview.clicked.connect(self.rightPreview)

        self.body.modTags.setOpenExternalLinks(False)
        self.body.modTags.linkActivated.connect(self.onTagLinkClicked)

        self.body.modDescription.setOpenExternalLinks(True)
        self.body.modDescription.highlighted.connect(self.onReplacementHovered)
        self.body.modDescription.anchorClicked.connect(self.hideWikiPreviewCard)
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

        # Pinned Selection Banner Frame (Fixed between Search Bar and Scroll Area)
        self.selectionBannerFrame = QFrame(self.ui.modsList)
        self.selectionBannerFrame.setObjectName("selectionBannerFrame")
        self.selectionBannerFrame.setFixedHeight(42)
        self.selectionBannerFrame.setStyleSheet("""
            QFrame#selectionBannerFrame {
                background-color: #191A1E;
                border: 1px solid #2B2C30;
                border-radius: 6px;
                margin: 4px 6px;
            }
        """)
        bannerLayout = QHBoxLayout(self.selectionBannerFrame)
        bannerLayout.setContentsMargins(12, 4, 12, 4)
        bannerLayout.setSpacing(10)

        self.selectionLabel = QLabel("Select mods to move")
        self.selectionLabel.setStyleSheet("color: #FFFFFF; font-size: 11px; font-weight: bold; border: none; background: transparent;")
        bannerLayout.addWidget(self.selectionLabel, 1)

        self.confirmMoveBtn = QPushButton("Move to...")
        self.confirmMoveBtn.setObjectName("confirmMoveBtn")
        self.confirmMoveBtn.setCursor(Qt.PointingHandCursor)
        self.confirmMoveBtn.setStyleSheet("""
            QPushButton#confirmMoveBtn {
                background-color: #43C15F !important;
                color: #FFFFFF !important;
                font-weight: bold;
                font-size: 11px;
                border-radius: 6px;
                padding: 6px 16px;
                border: none;
            }
            QPushButton#confirmMoveBtn:hover {
                background-color: #4BD469 !important;
            }
        """)
        self.confirmMoveBtn.clicked.connect(self.onMoveToClicked)
        bannerLayout.addWidget(self.confirmMoveBtn)


        self.cancelMoveBtn = QPushButton("Cancel")
        self.cancelMoveBtn.setObjectName("cancelMoveBtn")
        self.cancelMoveBtn.setCursor(Qt.PointingHandCursor)
        self.cancelMoveBtn.setStyleSheet("""
            QPushButton#cancelMoveBtn {
                background-color: #23242A !important;
                color: #CCCCCC !important;
                font-weight: bold;
                font-size: 11px;
                border-radius: 6px;
                padding: 6px 12px;
                border: 1px solid #3A3C4A;
            }
            QPushButton#cancelMoveBtn:hover {
                background-color: #2D2E38 !important;
                color: #FFFFFF !important;
            }
        """)
        self.cancelMoveBtn.clicked.connect(self.exitSelectionMode)
        bannerLayout.addWidget(self.cancelMoveBtn)

        self.ui.verticalLayout.insertWidget(1, self.selectionBannerFrame)
        self.selectionBannerFrame.hide()


        self.pending_target_group_id = None
        self.pending_target_group_name = None

        modsListFrame = QFrame()
        layout = QVBoxLayout(modsListFrame)
        layout.setSpacing(2)
        layout.setContentsMargins(2, 5, 2, 5)

        self.modsList = QFrame()
        layout2 = QVBoxLayout(self.modsList)
        layout2.setSpacing(1)
        layout2.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.modsList, 0, Qt.AlignTop)

        self.ui.scrollModsList.setWidget(modsListFrame)

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

        # Hand Mod Warning Notice (Gold/Amber #FFA500)
        self.handWarningFrame = QFrame()
        self.handWarningFrame.setStyleSheet("background-color: #1A1B1E; border-radius: 6px; border: 1px solid #2B2C30; margin: 4px 0px;")
        handWarningLayout = QHBoxLayout(self.handWarningFrame)
        handWarningLayout.setContentsMargins(10, 6, 10, 6)
        handWarningLayout.setSpacing(10)

        handWarningIconLabel = QLabel()
        handWarningIconLabel.setPixmap(get_tinted_svg_pixmap(mod_warning_icon_path, "#FFA500", 18))
        handWarningIconLabel.setStyleSheet("background: transparent; border: none; padding: 0px;")
        handWarningLayout.addWidget(handWarningIconLabel)

        handWarningTextLabel = QLabel(
            "WARNING: Hand mods are experimental and may stop working in the future or contain bugs/glitches. If something doesn't work, reinstall the mod or verify game files via Steam."
        )
        handWarningTextLabel.setWordWrap(True)
        handWarningTextLabel.setStyleSheet("color: #FFA500; font-size: 10px; font-weight: bold; border: none; background: transparent;")
        handWarningLayout.addWidget(handWarningTextLabel, 1)

        self.modDescriptionsAndActionsLayout.insertWidget(4, self.handWarningFrame)
        self.handWarningFrame.hide()

        # Color Mod Warning Notice (Gold/Amber #FFA500)
        self.colorWarningFrame = QFrame()
        self.colorWarningFrame.setStyleSheet("background-color: #1A1B1E; border-radius: 6px; border: 1px solid #2B2C30; margin: 4px 0px;")
        colorWarningLayout = QHBoxLayout(self.colorWarningFrame)
        colorWarningLayout.setContentsMargins(10, 6, 10, 6)
        colorWarningLayout.setSpacing(10)

        colorWarningIconLabel = QLabel()
        colorWarningIconLabel.setPixmap(get_tinted_svg_pixmap(mod_warning_icon_path, "#FFA500", 18))
        colorWarningIconLabel.setStyleSheet("background: transparent; border: none; padding: 0px;")
        colorWarningLayout.addWidget(colorWarningIconLabel)

        colorWarningTextLabel = QLabel(
            "WARNING: Color mods are experimental and may stop working in the future. If something doesn't work, reinstall the mod or verify game files via Steam."
        )
        colorWarningTextLabel.setWordWrap(True)
        colorWarningTextLabel.setStyleSheet("color: #FFA500; font-size: 10px; font-weight: bold; border: none; background: transparent;")
        colorWarningLayout.addWidget(colorWarningTextLabel, 1)

        self.modDescriptionsAndActionsLayout.insertWidget(5, self.colorWarningFrame)
        self.colorWarningFrame.hide()

        # ── SECURITY SECTION (English) ────────────────────────────────────────
        self.securitySectionFrame = QFrame()
        self.securitySectionFrame.setStyleSheet("background-color: #16171a; border-radius: 6px; border: 1px solid #27272a; margin: 4px 0px;")
        secOuterLayout = QVBoxLayout(self.securitySectionFrame)
        secOuterLayout.setContentsMargins(10, 8, 10, 8)
        secOuterLayout.setSpacing(6)

        secHeaderLayout = QHBoxLayout()
        secHeaderLayout.setContentsMargins(0, 0, 0, 0)
        secHeaderLayout.setSpacing(6)
        secHeaderIcon = QLabel()
        secHeaderIcon.setPixmap(get_tinted_svg_pixmap(mod_warning_icon_path, "#a1a1aa", 14))
        secHeaderIcon.setStyleSheet("background: transparent; border: none; padding: 0px;")
        secHeaderLayout.addWidget(secHeaderIcon)
        secHeaderTitle = QLabel("SECURITY")
        secHeaderTitle.setStyleSheet("color: #a1a1aa; font-size: 11px; font-weight: bold; border: none; background: transparent; letter-spacing: 0.5px;")
        secHeaderLayout.addWidget(secHeaderTitle)
        secHeaderLayout.addStretch()
        secOuterLayout.addLayout(secHeaderLayout)

        # Badges container
        self.secBadgesFrame = QFrame()
        self.secBadgesFrame.setStyleSheet("background: transparent; border: none;")
        self.secBadgesLayout = QHBoxLayout(self.secBadgesFrame)
        self.secBadgesLayout.setContentsMargins(0, 0, 0, 0)
        self.secBadgesLayout.setSpacing(8)
        self.secBadgesLayout.setAlignment(Qt.AlignLeft)
        secOuterLayout.addWidget(self.secBadgesFrame)

        # Status text
        self.secStatusDescLabel = QLabel()
        self.secStatusDescLabel.setWordWrap(True)
        self.secStatusDescLabel.setStyleSheet("color: #94a3b8; font-size: 10px; border: none; background: transparent;")
        secOuterLayout.addWidget(self.secStatusDescLabel)

        # Expandable threat details toggle button
        self.secDetailsToggleBtn = QPushButton("Show Details ▼")
        self.secDetailsToggleBtn.setCursor(Qt.PointingHandCursor)
        self.secDetailsToggleBtn.setStyleSheet("""
            QPushButton {
                color: #f87171;
                font-size: 10px;
                font-weight: bold;
                background: transparent;
                border: none;
                text-align: left;
                padding: 2px 0px;
            }
            QPushButton:hover {
                color: #ef4444;
                text-decoration: underline;
            }
        """)
        self.secDetailsToggleBtn.clicked.connect(self._toggleSecurityDetails)
        self.secDetailsToggleBtn.hide()
        secOuterLayout.addWidget(self.secDetailsToggleBtn)

        # Threat details container
        self.secDetailsContainer = QFrame()
        self.secDetailsContainer.setStyleSheet("background-color: #1e1113; border: 1px solid #7f1d1d; border-radius: 4px;")
        self.secDetailsLayout = QVBoxLayout(self.secDetailsContainer)
        self.secDetailsLayout.setContentsMargins(8, 6, 8, 6)
        self.secDetailsLayout.setSpacing(4)
        self.secDetailsContainer.hide()
        secOuterLayout.addWidget(self.secDetailsContainer)

        # Add Security Section below mod description
        self.modDescriptionsAndActionsLayout.addWidget(self.securitySectionFrame)

        # Replaces Info Card Frame (Electric Blue #526eff)
        self.replacesFrame = QFrame()
        self.replacesFrame.setStyleSheet("background-color: #1A1B1E; border-radius: 6px; border: 1px solid #2B2C30; margin: 4px 0px;")
        replacesOuterLayout = QVBoxLayout(self.replacesFrame)
        replacesOuterLayout.setContentsMargins(10, 8, 10, 8)
        replacesOuterLayout.setSpacing(6)

        replacesHeaderFrame = QFrame()
        replacesHeaderFrame.setStyleSheet("background: transparent; border: none;")
        replacesHeaderLayout = QHBoxLayout(replacesHeaderFrame)
        replacesHeaderLayout.setContentsMargins(0, 0, 0, 0)
        replacesHeaderLayout.setSpacing(8)

        replacesIconLabel = QLabel()
        replacesIconLabel.setPixmap(get_tinted_svg_pixmap(mod_warning_icon_path, "#526eff", 16))
        replacesIconLabel.setStyleSheet("background: transparent; border: none; padding: 0px;")
        replacesHeaderLayout.addWidget(replacesIconLabel)

        replacesTitleLabel = QLabel("This Mod Replaces:")
        replacesTitleLabel.setStyleSheet("color: #526eff; font-size: 11px; font-weight: bold; border: none; background: transparent;")
        replacesHeaderLayout.addWidget(replacesTitleLabel, 1)

        replacesOuterLayout.addWidget(replacesHeaderFrame)

        from PySide6.QtWidgets import QTextBrowser
        from PySide6.QtGui import QTextOption
        self.replacesListLabel = QTextBrowser()
        self.replacesListLabel.setOpenExternalLinks(True)
        self.replacesListLabel.setLineWrapMode(QTextBrowser.NoWrap)
        self.replacesListLabel.setWordWrapMode(QTextOption.NoWrap)
        self.replacesListLabel.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.replacesListLabel.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.replacesListLabel.setStyleSheet("background: transparent; border: none; color: #FFFFFF; font-size: 11px;")
        self.replacesListLabel.highlighted.connect(self.onReplacementHovered)
        self.replacesListLabel.anchorClicked.connect(self.hideWikiPreviewCard)
        self.replacesListLabel.viewport().installEventFilter(self)
        replacesOuterLayout.addWidget(self.replacesListLabel)

        self.modDescriptionsAndActionsLayout.insertWidget(6, self.replacesFrame)
        self.replacesFrame.hide()

        modsListFrame = QFrame()
        layout = QVBoxLayout(modsListFrame)
        layout.setSpacing(2)
        layout.setContentsMargins(2, 5, 2, 5)

        self.pending_target_group_id = None
        self.pending_target_group_name = None

        self.modsList = QFrame()
        layout2 = QVBoxLayout(self.modsList)
        layout2.setSpacing(1)
        layout2.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.modsList, 0, Qt.AlignTop)

        self.ui.scrollModsList.setWidget(modsListFrame)
        self.ui.scrollModsList.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

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
        AddButtonWidthToTexSize(self.modsActions.fixMod, 40)

        icons_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ui_sources", "resources", "icons"))
        fix_icon_svg_path = os.path.join(icons_dir, "FixIcon.svg")
        fix_icon_png_path = os.path.join(icons_dir, "FixIcon.png")
        if os.path.exists(fix_icon_svg_path):
            self.modsActions.fixMod.setIcon(QIcon(fix_icon_svg_path))
        elif os.path.exists(fix_icon_png_path):
            self.modsActions.fixMod.setIcon(QIcon(fix_icon_png_path))
        else:
            self.modsActions.fixMod.setIcon(QIcon(":/icons/resources/icons/FixIcon.png"))
        self.modsActions.fixMod.setIconSize(QSize(22, 22))
        self.modsActions.fixMod.setText("Fix")
        self.modsActions.fixMod.setStyleSheet("""
            QPushButton {
                background-color: #3396CD;
                border-radius: 14px;
                color: #eeeeee;
                font: 500 11pt "Roboto Medium";
            }
            QPushButton:hover {
                background-color: #3ba7e3;
            }
            QPushButton:pressed {
                background-color: #2b7fae;
            }
        """)

        self.modsActions.install.clicked.connect(installMethod)
        self.modsActions.uninstall.clicked.connect(uninstallMethod)
        self.modsActions.reinstall.clicked.connect(reinstallMethod)
        self.modsActions.deleteMod.clicked.connect(deleteMethod)
        self.modsActions.deleteMod.setIcon(QIcon(":/icons/resources/icons/Delete.png"))
        if fixMethod:
            self.modsActions.fixMod.clicked.connect(fixMethod)
        
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
        
        # New Group Button (NewGroup.svg icon only)
        new_group_icon_path = os.path.join(icons_dir, "NewGroup.svg")
        move_group_icon_path = os.path.join(icons_dir, "MoveToGroup.svg")

        self.ui.newGroupBtn = QPushButton(self.ui.leftButtons)
        self.ui.newGroupBtn.setMinimumSize(QSize(30, 30))
        self.ui.newGroupBtn.setCursor(Qt.PointingHandCursor)
        if os.path.exists(new_group_icon_path):
            self.ui.newGroupBtn.setIcon(QIcon(new_group_icon_path))
        else:
            self.ui.newGroupBtn.setIcon(QIcon(":/icons/resources/icons/NewGroup.svg"))
        self.ui.newGroupBtn.setIconSize(QSize(18, 18))
        self.ui.newGroupBtn.setToolTip("Create New Mod Group")
        self.ui.newGroupBtn.setEnabled(True)
        self.ui.horizontalLayout_4.insertWidget(3, self.ui.newGroupBtn)
        self.ui.newGroupBtn.clicked.connect(self.promptNewGroup)

        # Move Selected Mods Button (MoveToGroup.svg icon only)
        self.ui.moveGroupBtn = QPushButton(self.ui.leftButtons)
        self.ui.moveGroupBtn.setMinimumSize(QSize(30, 30))
        self.ui.moveGroupBtn.setCursor(Qt.PointingHandCursor)
        if os.path.exists(move_group_icon_path):
            self.ui.moveGroupBtn.setIcon(QIcon(move_group_icon_path))
        else:
            self.ui.moveGroupBtn.setIcon(QIcon(":/icons/resources/icons/MoveToGroup.svg"))
        self.ui.moveGroupBtn.setIconSize(QSize(18, 18))
        self.ui.moveGroupBtn.setToolTip("Move Selected Mods to Group...")
        self.ui.moveGroupBtn.setEnabled(True)
        self.ui.horizontalLayout_4.insertWidget(4, self.ui.moveGroupBtn)
        self.ui.moveGroupBtn.clicked.connect(self.promptMoveSelectedModsToGroup)

        self.ui.deleteAllMods.setIcon(QIcon(":/icons/resources/icons/Delete.png"))
        self.ui.deleteAllMods.setToolTip("Delete all mods from list")

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
        self.presetsBarFrame.setStyleSheet("background-color: #1D1E20; border-bottom: 1px solid #2B2C30;")
        self.presetsBarLayout = QHBoxLayout(self.presetsBarFrame)
        self.presetsBarLayout.setContentsMargins(6, 4, 6, 4)
        self.presetsBarLayout.setSpacing(5)

        # Presets Combo Box (Compact width capped at 130px)
        self.presetCombo = QComboBox(self.presetsBarFrame)
        self.presetCombo.setMinimumHeight(28)
        self.presetCombo.setMaximumWidth(130)
        self.presetCombo.setCursor(Qt.PointingHandCursor)
        self.presetCombo.setStyleSheet("""
            QComboBox {
                background-color: #2B2C32;
                color: #FFFFFF;
                border: 1px solid #3E4048;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 11px;
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background-color: #1D1E20;
                color: #FFFFFF;
                selection-background-color: #24638C;
            }
        """)
        self.presetCombo.setToolTip("Select or apply a mod preset profile")
        self.presetCombo.currentIndexChanged.connect(self.onPresetComboChanged)
        self.presetsBarLayout.addWidget(self.presetCombo, 0)

        # Preset tool buttons with 4px border-radius
        btn_style = "QPushButton { background-color: #2B2C32; border: 1px solid #3E4048; border-radius: 4px; } QPushButton:hover { background-color: #3B3D44; } QPushButton:pressed { background-color: #24638C; }"

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
        self.savePresetBtn.setStyleSheet(btn_style)
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
        self.editPresetBtn.setStyleSheet(btn_style)
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
        self.reloadPresetBtn.setStyleSheet(btn_style)
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
        self.deletePresetBtn.setStyleSheet("QPushButton { background-color: #2B2C32; border: 1px solid #3E4048; border-radius: 4px; } QPushButton:hover { background-color: #552222; }")
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
                border-radius: 14px;
                padding: 4px 12px;
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

        from ..utils.config import LoaderConfig
        cfg = LoaderConfig()
        self.currentSortField = cfg.sortField
        self.currentSortReverse = cfg.sortReverse
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

    def hideWikiPreviewCard(self, *args):
        self.active_hover_slug = None
        if hasattr(self, 'wikiPreviewCard'):
            self.wikiPreviewCard.hide()

    def onReplacementHovered(self, url):
        url_str = url.toString() if hasattr(url, 'toString') else str(url or "")
        if url_str and "brawlhalla.wiki.gg/wiki/" in url_str:
            slug = url_str.split("brawlhalla.wiki.gg/wiki/")[-1].split("#")[0]
            clean_name = slug.replace("_", " ")
            self.active_hover_slug = slug

            import threading
            threading.Thread(target=self._fetch_and_show_wiki_preview, args=(slug, clean_name), daemon=True).start()
        else:
            self.hideWikiPreviewCard()

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
                self.wikiPreviewSignal.emit(pixmap, clean_name, slug)

    def showWikiPreviewCard(self, pixmap: QPixmap, clean_name: str, slug: str):
        if getattr(self, 'active_hover_slug', None) != slug:
            return
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
        if hasattr(self, 'body') and (
            (hasattr(self.body, 'modDescription') and watched == self.body.modDescription.viewport()) or
            (hasattr(self, 'replacesListLabel') and watched == self.replacesListLabel.viewport())
        ):
            if event.type() in (QEvent.Leave, QEvent.FocusOut, QEvent.MouseButtonPress):
                self.hideWikiPreviewCard()
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
            for gw in self.modGroupsWidgets.values():
                gw.show()
                gw.setCollapsed(gw.collapsed)
                for btn in gw.mod_buttons:
                    btn.show()

            for btn in self.modsButtons:
                btn.show()
            return

        text = text.casefold().strip()
        from ..utils.tags_helper import auto_detect_tags

        matching_hashes = set()
        for modClass in self.mods.values():
            replacements = self.getModReplacements(modClass)
            auto_tags = auto_detect_tags(modClass, replacements)
            modClass.tags = auto_tags
            
            name_match = text in modClass.name.lower()
            author_match = text in modClass.author.lower()
            version_match = modClass.gameVersion.lower().startswith(text)
            tag_match = any(text in t.lower() for t in auto_tags)
            rep_match = any(text in r.lower() for r in replacements)

            if name_match or author_match or version_match or tag_match or rep_match:
                matching_hashes.add(modClass.hash)

        # Update visibility of group widgets and their mod buttons
        for gid, gw in self.modGroupsWidgets.items():
            has_matching = any(b.modClass.hash in matching_hashes for b in gw.mod_buttons)
            if has_matching:
                gw.show()
                gw.contentFrame.show()
                for btn in gw.mod_buttons:
                    if btn.modClass.hash in matching_hashes:
                        btn.show()
                    else:
                        btn.hide()
            else:
                gw.hide()

        # Update visibility of loose and favorite mod buttons in modsList
        group_btn_set = set()
        for gw in self.modGroupsWidgets.values():
            group_btn_set.update(gw.mod_buttons)

        for btn in self.modsButtons:
            if btn not in group_btn_set:
                if btn.modClass.hash in matching_hashes:
                    btn.show()
                else:
                    btn.hide()


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
        layout = self.modsList.layout()
        if layout:
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if item:
                    w = item.widget()
                    if w and hasattr(w, 'onParentResize'):
                        w.onParentResize()

        if hasattr(self, 'origScrollModsListResizeEvent') and self.origScrollModsListResizeEvent:
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
        from ..utils.tags_helper import detect_special_mod_types

        # Check for Special Mod Types (Hand Mod & Color Mod) replacements
        is_hand_spec, is_color_spec, hand_targets_spec, color_targets_spec = detect_special_mod_types(modClass)

        # Hash-based cache: compute once per mod, reuse on every select click
        cached = get_cached_replacements(modClass.hash)
        if cached is not None and len(cached) > 0:
            replacements = list(cached)
            if is_color_spec and color_targets_spec:
                for ct in color_targets_spec:
                    item = f"Replaces: {ct} (Color Scheme)"
                    if item not in replacements:
                        replacements.append(item)
            if is_hand_spec and hand_targets_spec:
                for ht in hand_targets_spec:
                    item = f"{ht} (Hand Mod)"
                    if item not in replacements:
                        replacements.append(item)
            return replacements

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

        from ..utils.lang_reader import format_avatar_name
        swf_names = getattr(modClass, 'swfNames', []) or []
        file_names = getattr(modClass, 'fileNames', []) or []
        sprite_names = getattr(modClass, 'spriteNames', []) or []

        all_names = swf_names + file_names + sprite_names
        for name in all_names:
            n_low = name.lower()
            if any(p in n_low for p in ['ui_avatars', 'sprites_avatars', 'avatar', 'cppscaler', 'flag1a', 'flag1b', 'flag1blong']):
                formatted = format_avatar_name(name, lang_reader)
                if formatted and formatted.lower() not in ['avatar', 'default', 'none']:
                    item = f"{formatted} (Avatar)"
                    if item not in seen:
                        seen.add(item)
                        replacements.append(item)

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
            s_low = sprite.lower()
            if any(p in s_low for p in ['ui_avatars', 'sprites_avatars', 'avatar', 'cppscaler', 'flag1a', 'flag1b', 'flag1blong', 'a_flag']):
                continue

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

        # Check for Special Mod Types (Hand Mod & Color Mod) replacements
        from ..utils.tags_helper import detect_special_mod_types
        is_hand_spec, is_color_spec, hand_targets_spec, color_targets_spec = detect_special_mod_types(modClass)

        if is_color_spec and color_targets_spec:
            for ct in color_targets_spec:
                item = f"Replaces: {ct} (Color Scheme)"
                if item not in seen:
                    seen.add(item)
                    replacements.append(item)

        if is_hand_spec and hand_targets_spec:
            for ht in hand_targets_spec:
                item = f"{ht} (Hand Mod)"
                if item not in seen:
                    seen.add(item)
                    replacements.append(item)

        set_cached_replacements(modClass.hash, replacements)
        return replacements

    def _toggleSecurityDetails(self):
        if hasattr(self, 'secDetailsContainer') and hasattr(self, 'secDetailsToggleBtn'):
            is_vis = self.secDetailsContainer.isVisible()
            self.secDetailsContainer.setVisible(not is_vis)
            self.secDetailsToggleBtn.setText("Hide Details ▲" if not is_vis else "Show Details ▼")

    def updateData(self):
        self.modsActions.webPage.setParent(None)
        self.modsActions.install.setParent(None)
        self.modsActions.uninstall.setParent(None)
        self.modsActions.reinstall.setParent(None)
        self.modsActions.update.setParent(None)
        self.modsActions.deleteMod.setParent(None)
        self.modsActions.fixMod.setParent(None)

        if not self.selectedModButton or not self.modsButtons:
            self.body.modName.setText("Brawlhalla Mod Loader")
            self.body.modName.setStyleSheet("color: #eeeeee;")
            self.body.modSource.setText("Source: ")
            self.body.modVersion.setText("Version: ")
            self.body.modDescription.setText("")
            self.setPreviewsPaths([self.defaultPreview])
            if hasattr(self, 'warningFrame'):
                self.warningFrame.hide()
            if hasattr(self, 'replacesFrame'):
                self.replacesFrame.hide()
            if hasattr(self, 'exWarningFrame'):
                self.exWarningFrame.hide()
            if hasattr(self, 'handWarningFrame'):
                self.handWarningFrame.hide()
            if hasattr(self, 'colorWarningFrame'):
                self.colorWarningFrame.hide()
            self.updateTagPills([])
            return

        modClass = self.selectedModButton.modClass


        if modClass.installed:
            if modClass.modFileExist:
                AddToFrame(self.modsActions.mainFrame, self.modsActions.reinstall)
            AddToFrame(self.modsActions.mainFrame, self.modsActions.uninstall)
        elif modClass.modFileExist:
            AddToFrame(self.modsActions.mainFrame, self.modsActions.install)

        AddToFrame(self.modsActions.mainFrame, self.modsActions.deleteMod)

        # Show Fix button for Color or Hand mods
        from ..utils.tags_helper import detect_special_mod_types
        is_hand_spec, is_color_spec, _, _ = detect_special_mod_types(modClass)
        if (is_hand_spec or is_color_spec) and modClass.modFileExist:
            AddToFrame(self.modsActions.mainFrame, self.modsActions.fixMod)

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

        # Hand Mod & Color Mod Warning Toggles
        from ..utils.tags_helper import detect_special_mod_types, check_ui_mainmenu_security
        is_hand_mod, is_color_mod, _, _ = detect_special_mod_types(modClass)
        sec_info = check_ui_mainmenu_security(modClass)

        if hasattr(self, 'handWarningFrame'):
            if is_hand_mod:
                self.handWarningFrame.show()
            else:
                self.handWarningFrame.hide()
        if hasattr(self, 'colorWarningFrame'):
            if is_color_mod:
                self.colorWarningFrame.show()
            else:
                self.colorWarningFrame.hide()

        # Update Security Audit Section Badges
        if hasattr(self, 'secBadgesLayout') and hasattr(self, 'secStatusDescLabel'):
            while self.secBadgesLayout.count():
                item = self.secBadgesLayout.takeAt(0)
                w = item.widget()
                if w:
                    w.deleteLater()

            has_ui = sec_info.get("has_ui_mainmenu", False)
            is_bmt = sec_info.get("is_certified", False) or getattr(modClass, "bmtCertified", False)
            is_creator = getattr(modClass, "creatorCertified", False) or getattr(modClass, "author", "") == "Brawlhalla ModCreator"
            threats = sec_info.get("threats", [])
            is_suspicious = (sec_info.get("status") == "SUSPICIOUS") or bool(threats)

            def _add_badge(label, dot_col, bg_col, bdr_col):
                b_frame = QFrame()
                b_frame.setFixedHeight(32)
                b_frame.setStyleSheet(f"background-color: {bg_col}; border-radius: 5px; border: 1px solid {bdr_col};")
                b_lay = QHBoxLayout(b_frame)
                b_lay.setContentsMargins(10, 0, 10, 0)
                b_lay.setSpacing(6)
                d_lbl = QLabel("●")
                d_lbl.setStyleSheet(f"color: {dot_col}; font-size: 9px; border: none; background: transparent;")
                b_lay.addWidget(d_lbl)
                t_lbl = QLabel(label)
                t_lbl.setStyleSheet("color: #FFFFFF; font-size: 11px; font-weight: bold; border: none; background: transparent;")
                b_lay.addWidget(t_lbl)
                self.secBadgesLayout.addWidget(b_frame)

            if is_suspicious:
                _add_badge("Security Warning", "#ef4444", "#2c1215", "#ef4444")
                self.secStatusDescLabel.setText(f"CRITICAL WARNING: {len(threats)} suspicious executable script(s) or pattern(s) detected.")
                self.secStatusDescLabel.setStyleSheet("color: #ef4444; font-size: 10px; font-weight: bold; border: none; background: transparent;")

                if hasattr(self, 'secDetailsLayout'):
                    while self.secDetailsLayout.count():
                        it = self.secDetailsLayout.takeAt(0)
                        w = it.widget()
                        if w:
                            w.deleteLater()

                    for t in threats:
                        t_snip = t.get("snippet", "Suspicious Code")
                        t_file = t.get("file", "UI_MainMenu.swf")
                        t_desc = t.get("description", "Potential external process execution or unauthorized network activity.")
                        t_lbl = QLabel(f"<span style='color: #ef4444; font-size: 10px;'>●</span> <b style='color: #fca5a5;'>{t_file}</b>: <code style='color: #fef08a; background: #2b1114; padding: 1px 4px; border-radius: 3px;'>{t_snip}</code><br><span style='color: #cbd5e1; font-size: 9px; padding-left: 8px;'>{t_desc}</span>")
                        t_lbl.setWordWrap(True)
                        t_lbl.setStyleSheet("color: #fca5a5; font-size: 10px; border: none; background: transparent; margin-bottom: 2px;")
                        self.secDetailsLayout.addWidget(t_lbl)

                if hasattr(self, 'secDetailsToggleBtn'):
                    self.secDetailsToggleBtn.setText("Show Details ▼")
                    self.secDetailsToggleBtn.show()
                if hasattr(self, 'secDetailsContainer'):
                    self.secDetailsContainer.hide()
            else:
                if hasattr(self, 'secDetailsToggleBtn'):
                    self.secDetailsToggleBtn.hide()
                if hasattr(self, 'secDetailsContainer'):
                    self.secDetailsContainer.hide()

                _add_badge("Mod Creator Certified", "#c084fc", "#221338", "#a855f7")

                if is_bmt:
                    _add_badge("BMT Certified", "#07c9d7", "#0c2429", "#07c9d7")
                    self.secStatusDescLabel.setText("Official verified clean mod created with Brawlhalla Modding Toolkit.")
                    self.secStatusDescLabel.setStyleSheet("color: #07c9d7; font-size: 10px; border: none; background: transparent;")
                elif has_ui:
                    _add_badge("Custom UI", "#94a3b8", "#1e293b", "#475569")
                    self.secStatusDescLabel.setText("Clean files without BMT certification.")
                    self.secStatusDescLabel.setStyleSheet("color: #94a3b8; font-size: 10px; border: none; background: transparent;")
                else:
                    _add_badge("Verified Safe Assets", "#34d399", "#06281e", "#10b981")
                    self.secStatusDescLabel.setText("Standard game asset mod. Zero executable code risk.")
                    self.secStatusDescLabel.setStyleSheet("color: #34d399; font-size: 10px; border: none; background: transparent;")

        self.setPreviewsPaths(modClass.previewsPaths)
        self.body.modName.setText(modClass.name)
        source_text = modClass.platform if modClass.platform is not None else ""
        self.body.modSource.setText("Source: " + source_text)
        self.body.modVersion.setText("Version: " + modClass.version)

        desc = modClass.description or ""
        self.body.modDescription.setText(desc)

        replacements = self.getModReplacements(modClass)

        if replacements:
            import urllib.parse
            replaces_html = "<ul style='margin-top: 2px; margin-bottom: 2px; padding-left: 18px; color: #FFFFFF; font-size: 11px; list-style-type: disc; white-space: nowrap;'>"
            for item in replacements:
                clean_name = item.split('(')[0].replace('Replaces:', '').strip()
                slug = clean_name.replace(' ', '_').replace("'", "%27")
                wiki_url = f"https://brawlhalla.wiki.gg/wiki/{slug}"
                replaces_html += f"<li style='margin-bottom: 3px; color: #FFFFFF; white-space: nowrap;'><a href='{wiki_url}' style='color: #FFFFFF; text-decoration: none; white-space: nowrap;'>{item}</a></li>"
            replaces_html += "</ul>"

            self.replacesListLabel.setHtml(replaces_html)
            self.replacesListLabel.document().adjustSize()
            doc_h = int(self.replacesListLabel.document().size().height())
            self.replacesListLabel.setFixedHeight(doc_h + 12)
            self.replacesFrame.show()
        else:
            self.replacesListLabel.setHtml("")
            self.replacesFrame.hide()

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

    def promptNewGroup(self):
        from PySide6.QtWidgets import QInputDialog
        dialog = QInputDialog(self)
        dialog.setWindowTitle("Create New Mod Group")
        dialog.setLabelText("Enter a name for the new virtual mod group:")
        dialog.setStyleSheet("""
            QInputDialog { background-color: #141518; color: #FFFFFF; }
            QLabel { color: #FFFFFF; font-size: 12px; font-weight: bold; }
            QLineEdit { background-color: #1F2024; color: #FFFFFF; border: 1px solid #24638C; border-radius: 4px; padding: 6px; font-size: 12px; }
            QPushButton { background-color: #24638C; color: #FFFFFF; border-radius: 4px; padding: 6px 14px; font-weight: bold; }
            QPushButton:hover { background-color: #347BA9; }
        """)
    def promptNewGroup(self):
        import random
        from PySide6.QtWidgets import QDialog
        from ..utils.tags_helper import CATEGORY_PALETTE
        from .modgroupsettingsdialog import ModGroupSettingsDialog

        default_color = random.choice(CATEGORY_PALETTE)
        dlg = ModGroupSettingsDialog(
            group_name="",
            group_color=default_color,
            mod_count=0,
            icon="Folder.png",
            is_create=True,
            parent=self
        )

        if dlg.exec() == QDialog.Accepted:
            name = dlg.new_name.strip()
            if not name:
                return
            color_hex = dlg.new_color
            selected_icon = dlg.new_icon

            group_id = name.lower().replace(" ", "_")
            from ..utils.config import LoaderConfig
            config = LoaderConfig()
            groups_dict = config.modGroups or {}

            if group_id not in groups_dict:
                groups_dict[group_id] = {
                    "name": name,
                    "color": color_hex,
                    "collapsed": True,
                    "icon": selected_icon
                }
                config.modGroups = groups_dict

            self.get_or_create_group_widget(group_id, name, color_hex, selected_icon)
            self.applySort(self.currentSortField, self.currentSortReverse)


    def _select_icon(self, fname, dialog, buttons):
        dialog.selected_icon = fname
        for btn in buttons:
            if btn.toolTip() == fname:
                btn.setStyleSheet("border: 2px solid #24638C; background: #1A1B1F; border-radius: 4px;")
            else:
                btn.setStyleSheet("border: 1px solid transparent; background: transparent; border-radius: 4px;")

    def install_all_in_group(self, group_id: str):
        gw = self.modGroupsWidgets.get(group_id)
        if not gw:
            return
        hashes = [btn.modClass.hash for btn in gw.mod_buttons 
                  if not btn.modClass.installed and btn.modClass.modFileExist]
        if not hashes:
            return
        if self.bulkInstallMethod:
            self.bulkInstallMethod(hashes)
        else:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Error", "No se puede instalar: el núcleo del ModLoader no está disponible.")

    def uninstall_all_in_group(self, group_id: str):
        gw = self.modGroupsWidgets.get(group_id)
        if not gw:
            return
        hashes = [btn.modClass.hash for btn in gw.mod_buttons if btn.modClass.installed]
        if not hashes:
            return
        if self.bulkUninstallMethod:
            self.bulkUninstallMethod(hashes)
        else:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Error", "No se puede desinstalar: el núcleo del ModLoader no está disponible.")

    def get_or_create_group_widget(self, group_id: str, group_name: str, group_color: str = "", group_icon: str = ""):
        if group_id in self.modGroupsWidgets:
            gw = self.modGroupsWidgets[group_id]
            if group_icon:
                gw.setIcon(group_icon)
            return gw

        from ..utils.config import LoaderConfig
        config = LoaderConfig()
        groups_dict = config.modGroups or {}

        if group_id in groups_dict:
            info = groups_dict[group_id]
            group_name = info.get("name", group_name)
            group_color = info.get("color", group_color)
            collapsed = info.get("collapsed", True)
            group_icon = info.get("icon", group_icon or "Folder.png")
        else:
            from ..utils.tags_helper import CATEGORY_PALETTE
            group_color = group_color or CATEGORY_PALETTE[len(groups_dict) % len(CATEGORY_PALETTE)]
            group_icon = group_icon or "Folder.png"
            collapsed = True
            groups_dict[group_id] = {
                "name": group_name,
                "color": group_color,
                "collapsed": collapsed,
                "icon": group_icon
            }
            config.modGroups = groups_dict


        from .modgroupwidget import ModGroupWidget
        gw = ModGroupWidget(group_id, group_name, group_color, collapsed, icon=group_icon, parent=self.modsList)
        gw.collapseToggled.connect(self.onGroupCollapseToggled)
        gw.settingsRequested.connect(self.onGroupSettingsRequested)
        gw.installAllRequested.connect(lambda: self.install_all_in_group(group_id))
        gw.uninstallAllRequested.connect(lambda: self.uninstall_all_in_group(group_id))

        self.modGroupsWidgets[group_id] = gw
        return gw


    def onGroupCollapseToggled(self, group_id: str, collapsed: bool):
        from ..utils.config import LoaderConfig
        config = LoaderConfig()
        groups_dict = config.modGroups or {}
        if group_id in groups_dict:
            groups_dict[group_id]["collapsed"] = collapsed
            config.modGroups = groups_dict

    def onGroupSettingsRequested(self, group_id: str):
        from ..utils.config import LoaderConfig
        config = LoaderConfig()
        groups_dict = config.modGroups or {}
        if group_id not in groups_dict:
            return

        info = groups_dict[group_id]
        gw = self.modGroupsWidgets.get(group_id)
        mod_count = gw.count() if gw else 0

        from .modgroupsettingsdialog import ModGroupSettingsDialog
        dlg = ModGroupSettingsDialog(info["name"], info["color"], mod_count, icon=info.get("icon", "Folder.png"), parent=self)
        if dlg.exec() == QDialog.Accepted:
            if dlg.delete_requested:
                self.deleteGroup(group_id)
            else:
                new_name = dlg.new_name
                new_color = dlg.new_color
                new_icon = getattr(dlg, 'new_icon', info.get("icon", "Folder.png"))

                info["name"] = new_name
                info["color"] = new_color
                info["icon"] = new_icon
                groups_dict[group_id] = info
                config.modGroups = groups_dict

                if gw:
                    gw.updateGroupData(new_name, new_color, new_icon)


    def deleteGroup(self, group_id: str):
        from ..utils.config import LoaderConfig
        config = LoaderConfig()
        groups_dict = config.modGroups or {}
        assignments = config.modGroupAssignments or {}

        if group_id not in groups_dict:
            return

        group_mod_hashes = [h for h, gid in assignments.items() if gid == group_id]

        for h in group_mod_hashes:
            assignments.pop(h, None)
        config.modGroupAssignments = assignments

        groups_dict.pop(group_id, None)
        config.modGroups = groups_dict

        gw = self.modGroupsWidgets.pop(group_id, None)
        if gw:
            gw.clearModButtons()
            gw.setParent(None)
            gw.deleteLater()

        self.rebuildVirtualGroups()

    def promptMoveSelectedModsToGroup(self):
        self.enterSelectionMode()

    def enterSelectionMode(self):
        self.selectionLabel.setText("Select mods to move")
        self.selectionBannerFrame.show()

        for btn in self.modsButtons:
            btn.showCheckBox(True)

    def exitSelectionMode(self):
        self.selectionBannerFrame.hide()

        for btn in self.modsButtons:
            btn.showCheckBox(False)

    def onMoveToClicked(self):
        checked_buttons = [b for b in self.modsButtons if b.isChecked()]
        if not checked_buttons:
            msgBox = QMessageBox(self)
            msgBox.setWindowTitle("Move Mods")
            msgBox.setText("No mods selected. Please check the checkbox on at least one mod.")
            msgBox.setStyleSheet("""
                QMessageBox { background-color: #141518; color: #FFFFFF; }
                QLabel { color: #FFFFFF; font-size: 12px; }
                QPushButton { background-color: #43C15F; color: #FFFFFF; border-radius: 4px; padding: 5px 14px; }
            """)
            msgBox.exec()
            return

        from ..utils.config import LoaderConfig
        config = LoaderConfig()
        groups_dict = config.modGroups or {}

        available_groups = []
        for gid, gdata in groups_dict.items():
            available_groups.append((gid, gdata.get("name", gid), gdata.get("color", "#24638C")))

        from .movetogroupdialog import MoveToGroupDialog
        dlg = MoveToGroupDialog(available_groups, current_group_id="", parent=self)
        if dlg.exec() == QDialog.Accepted and dlg.selected_group_id is not None:
            target_gid = dlg.selected_group_id
            assignments = config.modGroupAssignments or {}

            for btn in checked_buttons:
                h = btn.modClass.hash
                if target_gid == "":
                    assignments.pop(h, None)
                else:
                    assignments[h] = target_gid

            config.modGroupAssignments = assignments
            self.exitSelectionMode()
            self.rebuildVirtualGroups()

    def rebuildVirtualGroups(self):
        from ..utils.config import LoaderConfig
        config = LoaderConfig()
        groups_dict = config.modGroups or {}
        assignments = config.modGroupAssignments or {}

        for modButton in self.modsButtons:
            h = modButton.modClass.hash
            gid = assignments.get(h, "")
            if gid and gid in groups_dict:
                gdata = groups_dict[gid]
                gcolor = gdata.get("color", "")
                modButton.setGroup(gid, gcolor)
                modButton.modClass.groupId = gid
            else:
                modButton.setGroup("", "")
                modButton.modClass.groupId = ""

        self.applySort(getattr(self, 'currentSortField', 'Name'), getattr(self, 'currentSortReverse', False))

    def selectMod(self, modClass: ModClass):
        self.hideWikiPreviewCard()
        for modButton in self.modsButtons:
            if modButton.modClass == modClass:
                self.selectedModButton = modButton

        self.updateData()

    def addModButton(self, modClass: ModClass):
        modButton = ModButton(modClass=modClass,
                              method=self.selectMod,
                              favoriteMethod=self.toggleFavoriteMethod)

        self.modsButtons.append(modButton)

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
               spriteNames: List[str] = None,
               modPath: str = "",
               swfs: dict = None):

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
                       spriteNames,
                       modPath=modPath,
                       swfs=swfs)

        from ..utils.tags_helper import auto_detect_tags
        replacements = self.getModReplacements(mod)
        mod.tags = auto_detect_tags(mod, replacements)

        self.mods[hash] = mod
        self.addModButton(mod)
        
    def removeAllMods(self):
        for gw in list(self.modGroupsWidgets.values()):
            gw.clearModButtons()
            gw.setParent(None)
            gw.deleteLater()
        self.modGroupsWidgets.clear()

        ClearFrame(self.modsList)

        self.selectedModButton = None
        for modButton in self.modsButtons:
            modButton.cleanup()
        self.modsButtons.clear()

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

    def sortMods(self, field, reverse):
        self.applySort(field, reverse)

    def applySort(self, field="Name", reverse=False):
        try:
            from main import FlowTracer
            FlowTracer.log("applySort", f"field={field}, reverse={reverse}, total_mods={len(self.mods)}")
        except Exception: pass
        self.currentSortField = field
        self.currentSortReverse = reverse

        # Save sort state to persistent config
        from ..utils.config import LoaderConfig
        config = LoaderConfig()
        config.sortField = field
        config.sortReverse = reverse

        if self.sortCallback:
            self.sortCallback(field, reverse)

        scroll_bar = self.ui.scrollModsList.verticalScrollBar()
        scroll_pos = scroll_bar.value()

        # Phase 1: Read configuration model from disk/cache
        groups_dict = config.modGroups or {}
        raw_assignments = config.modGroupAssignments or {}

        # Sanitize assignments pointing to missing/deleted groups
        valid_group_ids = set(groups_dict.keys())
        assignments = {h: gid for h, gid in raw_assignments.items() if gid in valid_group_ids}

        # Phase 2: Sort underlying ModClass objects
        mod_list = list(self.mods.values())

        sort_key = None
        if field == "Name":
            sort_key = lambda x: x.name.lower()
        elif field == "Date":
            sort_key = lambda x: float(x.date or 0)
        elif field == "Installed":
            sort_key = lambda x: (not x.installed, x.name.lower())
        elif field == "Author":
            sort_key = lambda x: (x.author.lower(), x.name.lower())

        if sort_key:
            mod_list.sort(key=sort_key, reverse=reverse)

        favorites_mods = [m for m in mod_list if m.favorite]
        ungrouped_mods = [m for m in mod_list if not m.favorite and not assignments.get(m.hash, "")]

        # Phase 3: Build UI in a single atomic pass
        self.modsList.setUpdatesEnabled(False)
        self.blockSignals(True)
        try:
            def safe_remove_from_layout(w):
                p = w.parent()
                if p and p.layout():
                    p.layout().removeWidget(w)

            # Purge existing ModButton widgets
            for btn in list(self.modsButtons):
                safe_remove_from_layout(btn)
                btn.cleanup()
            self.modsButtons.clear()

            # Purge orphaned ModGroupWidgets no longer in config
            for gid in list(self.modGroupsWidgets.keys()):
                if gid not in valid_group_ids:
                    gw = self.modGroupsWidgets.pop(gid)
                    gw.clearModButtons()
                    gw.setParent(None)
                    gw.deleteLater()

            # Ensure all saved groups have a ModGroupWidget instance
            for gid, ginfo in groups_dict.items():
                gname = ginfo.get("name", gid)
                gcolor = ginfo.get("color", "")
                gicon = ginfo.get("icon", "Folder.png")
                self.get_or_create_group_widget(gid, gname, gcolor, gicon)

            # Clear content buttons from group widgets layout
            for gw in self.modGroupsWidgets.values():
                gw.clearModButtons()

            new_mods_buttons = []

            def create_button(modClass, group_id="", group_color=""):
                btn = ModButton(modClass=modClass,
                                method=self.selectMod,
                                favoriteMethod=self.toggleFavoriteMethod)
                if group_id and group_id in groups_dict:
                    gcolor = group_color or groups_dict[group_id].get("color", "")
                    btn.setGroup(group_id, gcolor)
                    btn.modClass.groupId = group_id
                else:
                    btn.setGroup("", "")
                    btn.modClass.groupId = ""
                new_mods_buttons.append(btn)
                return btn

            # 1. Favorites at top of modsList (pinned at start)
            for m in favorites_mods:
                gid = assignments.get(m.hash, "")
                gcolor = groups_dict.get(gid, {}).get("color", "") if gid else ""
                btn = create_button(m, group_id=gid, group_color=gcolor)
                btn.setParent(self.modsList)
                self.modsList.layout().addWidget(btn)

            # 2. Ungrouped non-favorite mods (loose mods)
            for m in ungrouped_mods:
                btn = create_button(m)
                btn.setParent(self.modsList)
                self.modsList.layout().addWidget(btn)

            # 3. Group widgets (each with its assigned mods, including favorite mods!)
            for gid, gw in sorted(self.modGroupsWidgets.items(), key=lambda t: t[1].group_name.lower()):
                safe_remove_from_layout(gw)
                gw.setParent(self.modsList)
                self.modsList.layout().addWidget(gw)
                gw.show()

                group_mods = [m for m in mod_list if assignments.get(m.hash, "") == gid]
                for m in group_mods:
                    btn = create_button(m, group_id=gid, group_color=gw.group_color)
                    gw.addModButton(btn)

            self.modsButtons = new_mods_buttons

            # 4. If no mods are loaded at all, show English Welcome Notice
            if not hasattr(self, 'emptyWelcomeWidget'):
                from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel
                from PySide6.QtGui import QFont

                self.emptyWelcomeWidget = QFrame()
                self.emptyWelcomeWidget.setStyleSheet("""
                    QFrame {
                        background-color: #1A1B1E;
                        border: 1px solid #2B2C30;
                        border-radius: 8px;
                        margin: 10px;
                    }
                    QLabel {
                        background: transparent;
                        border: none;
                    }
                """)
                wel_layout = QVBoxLayout(self.emptyWelcomeWidget)
                wel_layout.setContentsMargins(18, 18, 18, 18)
                wel_layout.setSpacing(12)

                # Title
                wel_title = QLabel("Welcome to Brawlhalla Mod Loader!")
                wel_title.setFont(QFont("Segoe UI", 13, QFont.Bold))
                wel_title.setStyleSheet("color: #FFFFFF;")
                wel_layout.addWidget(wel_title)

                # Body
                wel_body = QLabel(
                    'It looks like there are no mods here yet. Why not look for some on '
                    '<a href="https://gamebanana.com/games/5704" style="color: #4DB6AC; text-decoration: underline;">GameBanana</a> or in the '
                    '<a href="GameBanana_tab" style="color: #4DB6AC; text-decoration: underline;">GameBanana tab</a>?'
                )
                wel_body.setFont(QFont("Segoe UI", 10))
                wel_body.setStyleSheet("color: #D0D0D0;")
                wel_body.setWordWrap(True)
                wel_body.setOpenExternalLinks(False)

                def on_welcome_link_clicked(url):
                    if url == "GameBanana_tab":
                        try:
                            if hasattr(self, 'main') and hasattr(self.main, 'setGameBananaScreen'):
                                self.main.setGameBananaScreen()
                            elif hasattr(self, 'main') and hasattr(self.main, 'header') and hasattr(self.main.header, 'headerGameBananaButton'):
                                self.main.header.headerGameBananaButton.button.click()
                        except Exception as e:
                            print(f"Error opening GameBanana tab: {e}")
                    else:
                        import webbrowser
                        webbrowser.open(url)

                wel_body.linkActivated.connect(on_welcome_link_clicked)
                wel_layout.addWidget(wel_body)

                # Security / External Site Danger Warning
                wel_security = QLabel(
                    'If you find mods on another site or webpage, '
                    '<span style="color: #FF5050; font-weight: bold;">BEWARE</span>! You MAY be in danger. '
                    'The only safe places to download mods are '
                    '<a href="https://gamebanana.com/games/5704" style="color: #4DB6AC; text-decoration: underline;">GameBanana</a> or the '
                    '<a href="https://discord.gg/ctzYZxBHgY" style="color: #4DB6AC; text-decoration: underline;">Modhalla Discord</a>.'
                )
                wel_security.setFont(QFont("Segoe UI", 10))
                wel_security.setStyleSheet("color: #FFFFFF;")
                wel_security.setWordWrap(True)
                wel_security.setOpenExternalLinks(False)
                wel_security.linkActivated.connect(on_welcome_link_clicked)
                wel_layout.addWidget(wel_security)

                # Skin Paid Warning (in red)
                wel_warning = QLabel("Remember that any existing skin mod requires a PAID skin, check the REQUIREMENTS section in GameBanana to find out which skin it replaces.")
                wel_warning.setFont(QFont("Segoe UI", 9, QFont.Bold))
                wel_warning.setStyleSheet("color: #FF5050;")
                wel_warning.setWordWrap(True)
                wel_layout.addWidget(wel_warning)

                # Footer
                wel_footer = QLabel("Happy Modding!")
                wel_footer.setFont(QFont("Segoe UI", 10, QFont.Bold))
                wel_footer.setStyleSheet("color: #FFFFFF;")
                wel_layout.addWidget(wel_footer)

            safe_remove_from_layout(self.emptyWelcomeWidget)
            if not self.modsButtons:
                self.emptyWelcomeWidget.setParent(self.modsList)
                self.modsList.layout().addWidget(self.emptyWelcomeWidget)
                self.emptyWelcomeWidget.show()
                self.selectedModButton = None
                self.updateData()
            else:
                self.emptyWelcomeWidget.hide()


            try:
                from main import FlowTracer
                FlowTracer.log("applySort_step7", "Completed layout assembly")
            except Exception: pass

        finally:
            self.blockSignals(False)

            self.modsList.setUpdatesEnabled(True)
            self.modsList.update()

        QTimer.singleShot(0, lambda: scroll_bar.setValue(scroll_pos))

        if self.selectedModButton:
            self.selectedModButton.select()




