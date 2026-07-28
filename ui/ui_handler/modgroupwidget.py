import os
import re
from typing import List
from PySide6.QtWidgets import QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QToolButton
from PySide6.QtGui import QIcon, QPixmap, QPainter, QPainterPath, QColor, QFont, QCursor
from PySide6.QtCore import Qt, Signal, QSize, QRectF

def load_tinted_svg(svg_path: str, fill_color: str, size: int = 16) -> QPixmap:
    if os.path.exists(svg_path):
        try:
            with open(svg_path, 'r', encoding='utf-8') as f:
                content = f.read()
            content = re.sub(r'fill="[^"]*"', f'fill="{fill_color}"', content)
            from PySide6.QtSvg import QSvgRenderer
            from PySide6.QtGui import QImage
            renderer = QSvgRenderer(content.encode('utf-8'))
            image = QImage(size, size, QImage.Format_ARGB32)
            image.fill(Qt.transparent)
            painter = QPainter(image)
            renderer.render(painter)
            painter.end()
            return QPixmap.fromImage(image)
        except Exception as e:
            pass
    return QIcon(svg_path).pixmap(size, size)


class ModGroupHeader(QFrame):
    clicked = Signal()
    settingsClicked = Signal()
    installAllClicked = Signal()
    uninstallAllClicked = Signal()

    def __init__(self, group_name: str, color_hex: str, collapsed: bool = True, parent=None):
        super().__init__(parent)
        self.group_name = group_name
        self.color_hex = color_hex or "#24638C"
        self.collapsed = collapsed


        icons_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ui_sources", "resources", "icons"))
        self.arrow_down_path = os.path.join(icons_dir, "arrow_drop_down.svg")
        self.arrow_right_path = os.path.join(icons_dir, "arrow_right.svg")
        self.settings_icon_path = os.path.join(icons_dir, "settings.svg")

        self.setFixedHeight(34)
        self.setCursor(Qt.PointingHandCursor)
        self.updateHeaderStyle()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(6)

        # Arrow icon
        self.arrowLabel = QLabel()
        self.arrowLabel.setFixedSize(20, 20)
        self.arrowLabel.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(self.arrowLabel)

        # Icono del grupo (antes del título)
        self.iconLabel = QLabel()
        self.iconLabel.setFixedSize(20, 20)
        self.iconLabel.setStyleSheet("background: transparent; border: none;")
        layout.insertWidget(1, self.iconLabel)

        # Group Title
        self.titleLabel = QLabel(self.group_name)
        self.titleLabel.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.titleLabel.setStyleSheet("color: #FFFFFF; background: transparent; border: none;")
        layout.addWidget(self.titleLabel)

        layout.addStretch()

        # Mod Count Label
        self.countLabel = QLabel("0 mods")
        self.countLabel.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.countLabel.setStyleSheet("color: #E0E0E0; background: transparent; border: none;")
        layout.addWidget(self.countLabel)

        # Install All Button
        self.installAllBtn = QPushButton()
        self.installAllBtn.setFixedSize(24, 24)
        self.installAllBtn.setCursor(Qt.PointingHandCursor)
        self.installAllBtn.setToolTip("Install all mods in this group")
        install_all_icon = os.path.join(icons_dir, "InstallAllMods.png")
        if os.path.exists(install_all_icon):
            self.installAllBtn.setIcon(QIcon(install_all_icon))
        else:
            self.installAllBtn.setIcon(QIcon(":/icons/resources/icons/InstallAllMods.png"))
        self.installAllBtn.setIconSize(QSize(16, 16))
        self.installAllBtn.setStyleSheet("""
            QPushButton { background-color: transparent; border: none; border-radius: 4px; }
            QPushButton:hover { background-color: rgba(255, 255, 255, 0.2); }
        """)
        self.installAllBtn.clicked.connect(self.installAllClicked.emit)
        layout.addWidget(self.installAllBtn)

        # Uninstall All Button
        self.uninstallAllBtn = QPushButton()
        self.uninstallAllBtn.setFixedSize(24, 24)
        self.uninstallAllBtn.setCursor(Qt.PointingHandCursor)
        self.uninstallAllBtn.setToolTip("Uninstall all mods in this group")
        uninstall_all_icon = os.path.join(icons_dir, "UninstallAllMods.png")
        if os.path.exists(uninstall_all_icon):
            self.uninstallAllBtn.setIcon(QIcon(uninstall_all_icon))
        else:
            self.uninstallAllBtn.setIcon(QIcon(":/icons/resources/icons/UninstallAllMods.png"))
        self.uninstallAllBtn.setIconSize(QSize(16, 16))
        self.uninstallAllBtn.setStyleSheet("""
            QPushButton { background-color: transparent; border: none; border-radius: 4px; }
            QPushButton:hover { background-color: rgba(255, 255, 255, 0.2); }
        """)
        self.uninstallAllBtn.clicked.connect(self.uninstallAllClicked.emit)
        layout.addWidget(self.uninstallAllBtn)


        # Settings Button
        self.settingsBtn = QPushButton()
        self.settingsBtn.setFixedSize(24, 24)
        self.settingsBtn.setCursor(Qt.PointingHandCursor)
        self.settingsBtn.setToolTip("Group Settings")
        self.settingsBtn.setIcon(QIcon(load_tinted_svg(self.settings_icon_path, "#FFFFFF", 16)))
        self.settingsBtn.setIconSize(QSize(16, 16))
        self.settingsBtn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.2);
            }
        """)
        self.settingsBtn.clicked.connect(self.settingsClicked.emit)
        layout.addWidget(self.settingsBtn)

        self.updateArrow()

    def updateHeaderStyle(self):
        bg = self.color_hex or "#24638C"
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg};
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 6px;
            }}
            QFrame:hover {{
                border: 1px solid rgba(255, 255, 255, 0.35);
            }}
        """)

    def updateArrow(self):
        icon_path = self.arrow_right_path if self.collapsed else self.arrow_down_path
        pix = load_tinted_svg(icon_path, "#FFFFFF", 20)
        self.arrowLabel.setPixmap(pix)


    def setCollapsed(self, collapsed: bool):
        self.collapsed = collapsed
        self.updateArrow()

    def setGroupData(self, name: str, color_hex: str, count: int, icon: str = ""):
        self.group_name = name
        self.color_hex = color_hex or "#24638C"
        self.titleLabel.setText(name)
        self.updateHeaderStyle()
        self.setModCount(count)
        self.setIcon(icon)

    def setIcon(self, icon_path: str):
        icons_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ui_sources", "resources", "group_icons"))
        full_path = icon_path if os.path.isabs(icon_path or "") else os.path.join(icons_dir, icon_path or "")
        if icon_path and os.path.exists(full_path):
            pix = QPixmap(full_path).scaled(20, 20, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.iconLabel.setPixmap(pix)
        else:
            default_icon = os.path.join(icons_dir, "Folder.png")
            if os.path.exists(default_icon):
                pix = QPixmap(default_icon).scaled(20, 20, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.iconLabel.setPixmap(pix)
            else:
                self.iconLabel.clear()

    def setModCount(self, count: int):
        self.countLabel.setText(f"{count} mod{'s' if count != 1 else ''}")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Check if clicked outside control buttons
            if not (self.settingsBtn.geometry().contains(event.pos()) or
                    self.installAllBtn.geometry().contains(event.pos()) or
                    self.uninstallAllBtn.geometry().contains(event.pos())):
                self.clicked.emit()
        super().mousePressEvent(event)


class ModGroupWidget(QWidget):
    collapseToggled = Signal(str, bool)
    settingsRequested = Signal(str)
    installAllRequested = Signal()
    uninstallAllRequested = Signal()

    def __init__(self, group_id: str, group_name: str, group_color: str, collapsed: bool = True, icon: str = "", parent=None):
        super().__init__(parent)
        self.group_id = group_id
        self.group_name = group_name
        self.group_color = group_color
        self.collapsed = collapsed
        self.icon = icon or ""


        self.mod_buttons = []

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 2, 0, 4)
        main_layout.setSpacing(2)

        # Header
        self.header = ModGroupHeader(self.group_name, self.group_color, self.collapsed, parent=self)
        self.header.setIcon(self.icon)
        self.header.clicked.connect(self.toggleCollapse)
        self.header.settingsClicked.connect(lambda: self.settingsRequested.emit(self.group_id))
        self.header.installAllClicked.connect(self.installAllRequested.emit)
        self.header.uninstallAllClicked.connect(self.uninstallAllRequested.emit)
        main_layout.addWidget(self.header)


        # Content container frame for mod buttons
        self.contentFrame = QFrame()
        self.contentFrame.setStyleSheet("background: transparent; border: none;")
        self.contentLayout = QVBoxLayout(self.contentFrame)
        self.contentLayout.setContentsMargins(12, 0, 0, 0)
        self.contentLayout.setSpacing(1)

        main_layout.addWidget(self.contentFrame)

        if self.collapsed:
            self.contentFrame.hide()

    def toggleCollapse(self):
        self.collapsed = not self.collapsed
        self.header.setCollapsed(self.collapsed)
        if self.collapsed:
            self.contentFrame.hide()
        else:
            self.contentFrame.show()
        self.collapseToggled.emit(self.group_id, self.collapsed)

    def setCollapsed(self, collapsed: bool):
        self.collapsed = collapsed
        self.header.setCollapsed(collapsed)
        if self.collapsed:
            self.contentFrame.hide()
        else:
            self.contentFrame.show()

    def setIcon(self, icon_path: str):
        self.icon = icon_path or ""
        self.header.setIcon(self.icon)

    def updateGroupData(self, name: str, color: str, icon: str = ""):
        self.group_name = name
        self.group_color = color
        self.icon = icon or ""
        self.header.setGroupData(name, color, len(self.mod_buttons), self.icon)
        for btn in self.mod_buttons:
            if hasattr(btn, 'setGroup'):
                btn.setGroup(self.group_id, self.group_color)

                btn.setGroup(self.group_id, self.group_color)

    def addModButton(self, mod_button):
        if mod_button not in self.mod_buttons:
            self.mod_buttons.append(mod_button)
            if hasattr(mod_button, 'setGroup'):
                mod_button.setGroup(self.group_id, self.group_color)
            mod_button.setParent(self.contentFrame)
            self.contentLayout.addWidget(mod_button)
            self.header.setModCount(len(self.mod_buttons))

    def removeModButton(self, mod_button):
        if mod_button in self.mod_buttons:
            self.mod_buttons.remove(mod_button)
            self.contentLayout.removeWidget(mod_button)
            mod_button.setParent(None)
            self.header.setModCount(len(self.mod_buttons))

    def clearModButtons(self):
        for btn in list(self.mod_buttons):
            self.removeModButton(btn)

    def count(self) -> int:
        return len(self.mod_buttons)

    def onParentResize(self):
        for btn in self.mod_buttons:
            if hasattr(btn, 'onParentResize'):
                btn.onParentResize()

