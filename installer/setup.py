"""Установщик QuickDeck. Никаких внешних инструментов — только Python.

Внутрь exe упакована сама программа (папка payload). Установщик копирует её
в %LOCALAPPDATA%\\Programs\\QuickDeck, делает ярлыки, добавляет запись в
«Установка и удаление программ» и умеет удалить всё обратно.

Интерфейс на PySide6 — на том же, на чём сама программа. Пробовал stdlib-интерфейс,
чтобы установщик был легче, но в минимальных сборках Python (pythoncore, nuget,
embeddable) его модуля нет и сборка падала. Qt надёжнее: он в проекте уже есть.
Права администратора не нужны — всё пишется в профиль пользователя.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import threading

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QIcon, QPixmap, QFont
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QLineEdit, QFileDialog, QProgressBar, QMessageBox,
)

if sys.platform.startswith("win"):
    import winreg

APP = "QuickDeck"
EXE = "QuickDeck.exe"
UNINST = "Uninstall.exe"
VERSION = "1.0.0"
REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\QuickDeck"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

NO_WINDOW = 0x08000000          # CREATE_NO_WINDOW


def res(*parts) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


def default_dir() -> str:
    return os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                        "Programs", APP)


def run_hidden(args) -> int:
    try:
        return subprocess.call(args, creationflags=NO_WINDOW)
    except OSError:
        return 1


def make_shortcut(link: str, target: str, workdir: str, icon: str = ""):
    """Ярлык через WScript.Shell — есть в любой Windows, ставить нечего."""
    ps = (
        f"$s=(New-Object -COM WScript.Shell).CreateShortcut('{link}');"
        f"$s.TargetPath='{target}';"
        f"$s.WorkingDirectory='{workdir}';"
        + (f"$s.IconLocation='{icon}';" if icon else "") +
        "$s.Save()"
    )
    os.makedirs(os.path.dirname(link), exist_ok=True)
    run_hidden(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps])


def stop_running():
    run_hidden(["taskkill", "/im", EXE, "/f"])


def shortcut_paths():
    appdata = os.environ.get("APPDATA", "")
    return (
        os.path.join(appdata, r"Microsoft\Windows\Start Menu\Programs", f"{APP}.lnk"),
        os.path.join(os.path.expanduser("~"), "Desktop", f"{APP}.lnk"),
        os.path.join(appdata, r"Microsoft\Windows\Start Menu\Programs\Startup", f"{APP}.lnk"),
    )


def do_install(target: str, desktop: bool, startup: bool, progress):
    progress("Закрываю запущенную копию…", 5)
    stop_running()

    src = res("payload")
    if not os.path.isdir(src):
        raise RuntimeError("В установщике нет файлов программы (payload).\n"
                           "Собери его через build-setup.bat.")

    progress("Копирую файлы…", 15)
    files = [(r, n) for r, _, ns in os.walk(src) for n in ns]
    total = max(1, len(files))
    for i, (root, name) in enumerate(files):
        rel = os.path.relpath(root, src)
        dst_root = self_join(target, rel)
        os.makedirs(dst_root, exist_ok=True)
        shutil.copy2(os.path.join(root, name), os.path.join(dst_root, name))
        if i % 25 == 0:
            progress("Копирую файлы…", 15 + int(55 * i / total))

    progress("Создаю ярлыки…", 75)
    exe = os.path.join(target, EXE)
    start, desk, run = shortcut_paths()
    make_shortcut(start, exe, target, exe)
    if desktop:
        make_shortcut(desk, exe, target, exe)
    if startup:
        make_shortcut(run, exe, target, exe)

    progress("Регистрирую в списке программ…", 90)
    try:
        shutil.copy2(sys.executable, os.path.join(target, UNINST))
    except OSError:
        pass
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_KEY) as k:
        winreg.SetValueEx(k, "DisplayName", 0, winreg.REG_SZ, APP)
        winreg.SetValueEx(k, "DisplayVersion", 0, winreg.REG_SZ, VERSION)
        winreg.SetValueEx(k, "Publisher", 0, winreg.REG_SZ, APP)
        winreg.SetValueEx(k, "DisplayIcon", 0, winreg.REG_SZ, exe)
        winreg.SetValueEx(k, "InstallLocation", 0, winreg.REG_SZ, target)
        winreg.SetValueEx(k, "UninstallString", 0, winreg.REG_SZ,
                          f'"{os.path.join(target, UNINST)}" --uninstall')
        winreg.SetValueEx(k, "NoModify", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(k, "NoRepair", 0, winreg.REG_DWORD, 1)

    progress("Готово", 100)


def self_join(target: str, rel: str) -> str:
    return target if rel == "." else os.path.join(target, rel)


def do_uninstall(target: str):
    stop_running()
    for path in shortcut_paths():
        try:
            os.remove(path)
        except OSError:
            pass
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, APP)
    except OSError:
        pass
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, REG_KEY)
    except OSError:
        pass
    # папку сносим отложенно: деинсталлятор сейчас запущен изнутри неё
    bat = os.path.join(tempfile.gettempdir(), "quickdeck_remove.bat")
    with open(bat, "w", encoding="ascii", errors="ignore") as f:
        f.write("@echo off\r\nping 127.0.0.1 -n 3 >nul\r\n"
                f'rmdir /s /q "{target}"\r\ndel /q "%~f0"\r\n')
    subprocess.Popen(["cmd", "/c", bat], creationflags=NO_WINDOW)


# --------------------------------------------------------------- окно
class Worker(QThread):
    step = Signal(str, int)
    finished_ok = Signal(bool, str)

    def __init__(self, target, desktop, startup):
        super().__init__()
        self.target, self.desktop, self.startup = target, desktop, startup

    def run(self):
        try:
            do_install(self.target, self.desktop, self.startup,
                       lambda t, p: self.step.emit(t, p))
            self.finished_ok.emit(True, self.target)
        except Exception as e:  # noqa: BLE001 — текст ошибки нужен пользователю
            self.finished_ok.emit(False, str(e))


class Wizard(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Установка {APP}")
        self.setFixedWidth(540)
        icon = res("quickdeck.ico")
        if os.path.exists(icon):
            self.setWindowIcon(QIcon(icon))

        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 24, 26, 20)
        lay.setSpacing(12)

        head = QHBoxLayout()
        if os.path.exists(icon):
            pic = QLabel()
            pic.setPixmap(QPixmap(icon).scaled(52, 52, Qt.KeepAspectRatio,
                                               Qt.SmoothTransformation))
            head.addWidget(pic)
            head.addSpacing(6)
        title = QLabel(f"{APP} {VERSION}")
        title.setFont(QFont("Segoe UI", 16, QFont.DemiBold))
        head.addWidget(title, 1)
        lay.addLayout(head)

        sub = QLabel("Быстрый доступ к документам, текстам и папкам.\n"
                     "Ставится в папку пользователя — права администратора не нужны.")
        sub.setWordWrap(True)
        sub.setStyleSheet("color:#6b7280;")
        lay.addWidget(sub)
        lay.addSpacing(6)

        lay.addWidget(QLabel("Куда установить:"))
        row = QHBoxLayout()
        self.path = QLineEdit(default_dir())
        browse = QPushButton("Обзор…")
        browse.clicked.connect(self.pick)
        row.addWidget(self.path, 1)
        row.addWidget(browse)
        lay.addLayout(row)

        self.cb_desktop = QCheckBox("Ярлык на рабочем столе")
        self.cb_desktop.setChecked(True)
        self.cb_startup = QCheckBox("Запускать при входе в Windows")
        self.cb_startup.setChecked(True)
        lay.addWidget(self.cb_desktop)
        lay.addWidget(self.cb_startup)

        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setVisible(False)
        self.status = QLabel("")
        self.status.setStyleSheet("color:#6b7280;")
        lay.addWidget(self.bar)
        lay.addWidget(self.status)

        foot = QHBoxLayout()
        foot.addStretch(1)
        self.b_cancel = QPushButton("Отмена")
        self.b_cancel.clicked.connect(self.close)
        self.b_go = QPushButton("Установить")
        self.b_go.setDefault(True)
        self.b_go.setMinimumWidth(130)
        self.b_go.clicked.connect(self.start)
        foot.addWidget(self.b_cancel)
        foot.addWidget(self.b_go)
        lay.addSpacing(4)
        lay.addLayout(foot)

    def pick(self):
        d = QFileDialog.getExistingDirectory(self, "Куда установить", self.path.text())
        if d:
            d = os.path.normpath(d)
            self.path.setText(d if os.path.basename(d) == APP
                              else os.path.join(d, APP))

    def start(self):
        target = os.path.normpath(self.path.text().strip() or default_dir())
        self.b_go.setEnabled(False)
        self.path.setEnabled(False)
        self.bar.setVisible(True)
        self.worker = Worker(target, self.cb_desktop.isChecked(),
                             self.cb_startup.isChecked())
        self.worker.step.connect(self.on_step)
        self.worker.finished_ok.connect(self.on_done)
        self.worker.start()

    def on_step(self, text: str, pct: int):
        self.status.setText(text)
        self.bar.setValue(pct)

    def on_done(self, ok: bool, info: str):
        if not ok:
            QMessageBox.warning(self, "Не получилось", info)
            self.b_go.setEnabled(True)
            self.path.setEnabled(True)
            return
        ask = QMessageBox.question(
            self, "Установлено",
            f"{APP} установлен:\n{info}\n\nЗапустить сейчас?")
        if ask == QMessageBox.Yes:
            try:
                os.startfile(os.path.join(info, EXE))  # noqa: S606
            except OSError as e:
                QMessageBox.warning(self, APP, str(e))
        self.close()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(f"{APP} Setup")

    if "--uninstall" in sys.argv:
        target = os.path.dirname(os.path.abspath(sys.executable))
        ask = QMessageBox.question(
            None, f"Удаление {APP}",
            f"Удалить {APP} из папки:\n{target}\n\n"
            "Настройки в %APPDATA%\\QuickDeck останутся.")
        if ask == QMessageBox.Yes:
            do_uninstall(target)
            QMessageBox.information(None, APP, f"{APP} удалён.")
        return 0

    w = Wizard()
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
