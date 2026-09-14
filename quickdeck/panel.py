"""Окно быстрого поиска по всем кнопкам (Ctrl+Space)."""
from PySide6.QtCore import Qt, QTimer, Signal, QEvent
from PySide6.QtGui import QCursor, QIcon, QColor
from PySide6.QtCore import QSize

from . import icons
from . import theme as T
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QApplication, QLineEdit, QListWidget, QListWidgetItem,
)

DARK = """
QWidget#root { background: rgba(250,251,252,214); border: 1px solid rgba(23,25,29,26);
               border-radius: 20px; }
QLabel { color: #171a1d; }
QPushButton#item { color: #171a1d; background: rgba(23,25,29,10);
                   border: 1px solid transparent; border-radius: 12px;
                   padding: 8px 12px; text-align: left; }
QPushButton#item:hover { background: #ffffff; border-color: %ACCENT%; }
QPushButton#item:pressed { background: rgba(23,25,29,16); }
QPushButton#tab { color: rgba(23,25,29,150); background: transparent; border: none;
                  padding: 5px 8px; border-radius: 10px; }
QPushButton#tab:hover { background: rgba(23,25,29,12); color: #171a1d; }
QPushButton#tab[active="true"] { background: %ACCENT%; color: #ffffff; font-weight: 600; }
QPushButton#tool { color: rgba(23,25,29,120); background: transparent; border: none; padding: 3px 6px; }
QPushButton#tool:hover { color: #171a1d; }
QScrollArea, QScrollArea > QWidget, QScrollArea > QWidget > QWidget
    { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 0; }
QScrollBar::handle:vertical { background: rgba(23,25,29,45); border-radius: 4px; min-height: 30px; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
QLineEdit { background: #ffffff; border: 1px solid rgba(23,25,29,32);
            border-radius: 12px; padding: 10px 14px; color: #171a1d; font-size: 14px; }
QListWidget { background: transparent; border: none; color: #171a1d; font-size: 13px; }
QListWidget::item { padding: 8px 12px; border-radius: 10px; }
QListWidget::item:selected { background: %ACCENT%; color: #ffffff; }
"""


def styled(accent: str) -> str:
    return DARK.replace("%ACCENT%", accent or "#4da3ff")


class Palette(QWidget):
    """Быстрый поиск по всем кнопкам (горячая клавиша)."""

    activated = Signal(dict)

    def __init__(self, config: dict):
        super().__init__(None)
        self.config = config
        self.flat = []
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        root = QWidget(objectName="root")
        outer.addWidget(root)
        box = QVBoxLayout(root)
        box.setContentsMargins(14, 14, 14, 14)
        box.setSpacing(8)

        self.edit = QLineEdit()
        self.edit.setPlaceholderText("Поиск по кнопкам…")
        self.edit.textChanged.connect(self.refresh)
        self.edit.installEventFilter(self)
        box.addWidget(self.edit)

        self.list = QListWidget()
        self.list.itemActivated.connect(self._activate_row)
        self.list.itemClicked.connect(self._activate_row)
        box.addWidget(self.list, 1)

        self.reload(config)

    def reload(self, config: dict):
        self.config = config
        self.setStyleSheet(styled(config.get("settings", {}).get("accent")))
        self.flat = []
        for g in config.get("groups", []):
            for it in g.get("items", []):
                self.flat.append((g, it))
        self.refresh()

    def refresh(self):
        q = self.edit.text().strip().lower()
        self.list.clear()
        for g, it in self.flat:
            hay = f"{it.get('title','')} {g.get('name','')} {it.get('note','')}".lower()
            if q and q not in hay:
                continue
            row = QListWidgetItem(f"  {it.get('title','')}     ·  {g.get('name','')}")
            row.setIcon(QIcon(icons.pixmap(
                icons.resolve(it), 17,
                QColor(it.get("color") or g.get("color") or "#3c6df0"), dpr=2)))
            row.setData(Qt.UserRole, it)
            self.list.addItem(row)
        if self.list.count():
            self.list.setCurrentRow(0)

    def eventFilter(self, obj, ev):
        if obj is self.edit and ev.type() == QEvent.KeyPress:
            k = ev.key()
            if k in (Qt.Key_Down, Qt.Key_Up):
                row = self.list.currentRow() + (1 if k == Qt.Key_Down else -1)
                self.list.setCurrentRow(max(0, min(self.list.count() - 1, row)))
                return True
            if k in (Qt.Key_Return, Qt.Key_Enter):
                self._activate_row(self.list.currentItem())
                return True
            if k == Qt.Key_Escape:
                self.hide()
                return True
        return super().eventFilter(obj, ev)

    def _activate_row(self, row):
        if not row:
            return
        item = row.data(Qt.UserRole)
        self.hide()
        self.activated.emit(item)

    def popup(self):
        self.reload(self.config)
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        geo = screen.availableGeometry()
        self.resize(560, 440)
        self.move(geo.center().x() - 280, geo.top() + int(geo.height() * 0.18))
        self.edit.clear()
        self.show()
        self.raise_()
        self.activateWindow()
        if not getattr(self, "_glass", False):
            self._glass = T.enable_glass(self)
        QTimer.singleShot(0, self.edit.setFocus)

    def toggle(self):
        if self.isVisible():
            self.hide()
        else:
            self.popup()
