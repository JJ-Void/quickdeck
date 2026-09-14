"""QuickDeck — быстрый доступ к документам, текстам и папкам.

Запуск: python run.py   (или собранный QuickDeck.exe)
"""
import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QAction
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QMessageBox

from . import config as cfg
from . import actions
from . import theme as T
from .panel import Palette
from .handle import EdgeHandle
from .arcwheel import ArcWheel
from .editor import Editor
from .presets import PresetDialog
from .hotkeys import HotkeyManager

SCALE_STEPS = [0.7, 0.8, 0.9, 1.0, 1.1, 1.25, 1.4, 1.6, 1.8]

# имя замка одно на пользователя: две копии в трее никому не нужны,
# а при двойном запуске логичнее показать колесо, чем поднять второй экземпляр
LOCK_NAME = "QuickDeck-single-instance-" + (os.environ.get("USERNAME") or "user")


def make_icon(accent: str = "#5b8cff") -> QIcon:
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(24, 27, 35))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(2, 2, 60, 60, 16, 16)
    p.setBrush(QColor(accent))
    p.drawEllipse(18, 18, 28, 28)
    p.setBrush(QColor(24, 27, 35))
    p.drawEllipse(27, 27, 10, 10)
    p.end()
    return QIcon(pm)


def set_autostart(enabled: bool):
    """Автозапуск через реестр (только Windows)."""
    if not sys.platform.startswith("win"):
        return
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
        exe = sys.executable if getattr(sys, "frozen", False) else \
            f'"{sys.executable}" -m quickdeck.main'
        if enabled:
            winreg.SetValueEx(key, "QuickDeck", 0, winreg.REG_SZ, exe)
            _drop_startup_shortcut()   # иначе установщик и настройка запустят две копии
        else:
            try:
                winreg.DeleteValue(key, "QuickDeck")
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
    except Exception:
        pass


def _drop_startup_shortcut():
    """Ярлык в автозагрузке мог поставить установщик. Если автозапуск включён
    настройкой через реестр, ярлык — второй источник и лишний экземпляр."""
    link = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows",
                        "Start Menu", "Programs", "Startup", "QuickDeck.lnk")
    try:
        if os.path.exists(link):
            os.remove(link)
    except OSError:
        pass


class QuickDeck:
    def __init__(self, app: QApplication):
        self.app = app
        self.config = cfg.load()
        s = self.config["settings"]

        self.wheel = ArcWheel(self.config)
        self.wheel.reload(self.config)
        self.handle = EdgeHandle(self.config)
        self.palette = Palette(self.config)

        self.wheel.activated.connect(self.run)
        self.palette.activated.connect(self.run)
        self.handle.clicked.connect(self.open_wheel)
        self.handle.moved.connect(self.on_handle_moved)

        self.tray = QSystemTrayIcon(make_icon(s.get("accent")))
        self.tray.setToolTip("QuickDeck")
        menu = QMenu()
        for text, slot in (
            ("Колесо выбора", self.open_wheel),
            ("Быстрый поиск", self.palette.popup),
            ("Настройки…", self.open_editor),
        ):
            a = QAction(text, menu)
            a.triggered.connect(slot)
            menu.addAction(a)
        menu.addSeparator()
        a_quit = QAction("Выход", menu)
        a_quit.triggered.connect(self.quit)
        menu.addAction(a_quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_click)
        self.tray.show()

        self.server = QLocalServer()
        QLocalServer.removeServer(LOCK_NAME)      # подчищаем сокет после падения
        self.server.listen(LOCK_NAME)
        self.server.newConnection.connect(self.on_second_launch)

        self.hk = HotkeyManager(s)
        self.hk.bridge.scroll.connect(self.on_scroll)
        self.hk.bridge.mod_released.connect(self.on_mod_released)
        self.hk.bridge.panel_hotkey.connect(self.palette.toggle)
        if not self.hk.start():
            self.tray.showMessage(
                "QuickDeck",
                "Не установлен пакет pynput — горячие клавиши и колесо отключены.",
                QSystemTrayIcon.Warning, 6000)

        set_autostart(bool(s.get("start_with_windows")))

        if s.get("handle_enabled", True):
            self.handle.show()
        self.tray.showMessage(
            "QuickDeck запущен",
            f"{s.get('wheel_modifier', 'alt')} + колесо мыши — выбор, "
            f"{s.get('hotkey_panel', 'ctrl+space')} — поиск.",
            QSystemTrayIcon.Information, 4000)

    # ------------------------------------------------------------------
    def _tray_click(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.open_wheel()

    def on_second_launch(self):
        """Программу запустили ещё раз — вместо второй копии показываем колесо."""
        conn = self.server.nextPendingConnection()
        if conn:
            conn.disconnectFromServer()
        self.open_wheel()

    def open_wheel(self):
        """Открыто мышью — Alt не зажат, значит сразу закреплено."""
        if not self.wheel.isVisible():
            self.wheel.popup(pinned=True)

    def on_scroll(self, step: int, mod_held: bool):
        if self.wheel.isVisible():
            self.wheel.scroll_step(step)
        elif mod_held:
            self.wheel.popup()

    def on_mod_released(self):
        if self.wheel.isVisible():
            self.wheel.modifier_released()

    def on_handle_moved(self, side: str, pos: float):
        s = self.config["settings"]
        s["wheel_side"] = side
        s["handle_pos"] = round(pos, 4)
        cfg.save(self.config)
        self.wheel.apply_settings(s)

    # ------------------------------------------------------------------
    def run(self, item: dict):
        if item.get("type") == "app":
            self.run_app_action(item.get("action", ""))
            return
        try:
            msg = actions.run_item(item, None, self.config.get("settings", {}))
            if msg:
                self.tray.showMessage("QuickDeck", msg, QSystemTrayIcon.Information, 2200)
        except Exception as e:  # noqa: BLE001 — текст ошибки нужен пользователю
            self.tray.showMessage("QuickDeck — ошибка", str(e), QSystemTrayIcon.Warning, 5000)

    def run_app_action(self, action: str):
        """Пункты встроенной категории «Настройки»."""
        s = self.config["settings"]
        if action == "editor":
            self.open_editor()
        elif action == "presets":
            self.open_presets()
        elif action == "search":
            self.palette.popup()
        elif action == "side":
            s["wheel_side"] = "left" if s.get("wheel_side") != "left" else "right"
            self._save_and_reopen(3)
        elif action in ("scale_up", "scale_down"):
            cur = float(s.get("ui_scale", 1.0))
            idx = min(range(len(SCALE_STEPS)), key=lambda i: abs(SCALE_STEPS[i] - cur))
            idx = min(len(SCALE_STEPS) - 1, idx + 1) if action == "scale_up" else max(0, idx - 1)
            s["ui_scale"] = SCALE_STEPS[idx]
            self._save_and_reopen(4 if action == "scale_up" else 5)
        elif action == "quit":
            self.quit()

    def _save_and_reopen(self, item_index: int):
        """Сохранить и открыть колесо на том же пункте — результат виден сразу."""
        cfg.save(self.config)
        self.wheel.apply_settings(self.config["settings"])
        self.handle.reload(self.config)
        self.wheel.popup("__settings", item_index, pinned=True)

    def open_presets(self):
        dlg = PresetDialog(self.config)
        dlg.exec()
        if dlg.changed:
            cfg.save(self.config)
            self.reload(self.config)
            self.tray.showMessage("QuickDeck", "Набор кнопок загружен",
                                  QSystemTrayIcon.Information, 2500)

    def open_editor(self):
        dlg = Editor(self.config)
        dlg.saved.connect(self.reload)
        dlg.exec()

    def reload(self, config: dict):
        self.config = config
        s = config["settings"]
        self.wheel.reload(config)
        self.palette.reload(config)
        self.handle.reload(config)
        self.hk.apply(s)
        self.tray.setIcon(make_icon(s.get("accent")))
        set_autostart(bool(s.get("start_with_windows")))
        self.handle.setVisible(bool(s.get("handle_enabled", True)))

    def quit(self):
        self.hk.stop()
        self.tray.hide()
        self.app.quit()


def already_running() -> bool:
    """Есть ли уже запущенный экземпляр: стучимся в его сокет и, если ответил,
    просим показать колесо и выходим сами."""
    sock = QLocalSocket()
    sock.connectToServer(LOCK_NAME)
    if not sock.waitForConnected(300):
        return False
    sock.write(b"show")
    sock.flush()
    sock.waitForBytesWritten(300)
    sock.disconnectFromServer()
    return True


def main():
    if hasattr(Qt, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app = QApplication(sys.argv)
    app.setApplicationName("QuickDeck")
    app.setQuitOnLastWindowClosed(False)
    T.load_fonts()
    app.setFont(T.font(10))

    if already_running():
        return 0

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, "QuickDeck", "Системный трей недоступен.")
        return 1

    deck = QuickDeck(app)          # держим ссылку, иначе соберёт сборщик мусора
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
