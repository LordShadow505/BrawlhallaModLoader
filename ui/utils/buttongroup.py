from typing import Dict

from PySide6.QtWidgets import QPushButton
from PySide6.QtCore import QObject


class ButtonGroup(QObject):
    _groups: Dict[str, list] = {}

    def __init__(self, group: str, button: QPushButton, isDefault: bool = False, method=None):
        self.group = group

        if group not in self._groups:
            self._groups[group] = []

        if button in self._groups[group]:
            raise Exception(f"This button '{button}' is already in '{group}' group")

        self.button: QPushButton = button
        self._groups[group].append(self)

        if method is None:
            self.pressedMethod = lambda: None
        else:
            self.pressedMethod = method

        if isDefault:
            self.button.setChecked(True)
            self.pressedMethod()

        # Keep the controller owned by its button, but use the native button
        # signals instead of an event filter.  Event filters were being
        # called while Qt was garbage-collecting during window resize and
        # could dereference an invalid QEvent wrapper.
        super().__init__(button)
        self.button.pressed.connect(self.pressed)
        self.button.released.connect(self.released)

    def remove(self):
        self._groups[self.group].pop(self)

    def setPressed(self, method):
        self.pressedMethod = method

    def pressed(self):
        if self.button.isChecked():
            return True
        else:
            self.pressedMethod()
            return False

    def released(self):
        return False

    def enter(self):
        pass

    def leave(self):
        pass

    @classmethod
    def getGroup(cls, group: str) -> list:
        return cls._groups.get(group, [])

    def getSelfGroup(self) -> list:
        return self._groups.get(self.group, [])
