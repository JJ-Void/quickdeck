"""Выполнение действий кнопок: открыть, копировать, шаблон, копия документа."""
import datetime
import os
import re
import shutil
import subprocess
import sys
import webbrowser

from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QMessageBox, QApplication,
    QPlainTextEdit, QLabel, QVBoxLayout,
)
from PySide6.QtCore import Qt

PLACEHOLDER_RE = re.compile(r"\{([^{}\n]{1,60})\}")

# поля, которые подставляются сами и не спрашиваются у пользователя
AUTO_FIELDS = {
    "дата": lambda: datetime.date.today().strftime("%d.%m.%Y"),
    "дата_файл": lambda: datetime.date.today().strftime("%Y-%m-%d"),
    "время": lambda: datetime.datetime.now().strftime("%H:%M"),
    "date": lambda: datetime.date.today().strftime("%d.%m.%Y"),
    "today": lambda: datetime.date.today().strftime("%d.%m.%Y"),
}


def placeholders(text: str):
    """Уникальные поля {...} в порядке появления, без авто-полей."""
    seen, out = set(), []
    for m in PLACEHOLDER_RE.finditer(text or ""):
        name = m.group(1).strip()
        key = name.lower()
        if key in AUTO_FIELDS or key in seen:
            continue
        seen.add(key)
        out.append(name)
    return out


def fill(text: str, values: dict) -> str:
    low = {k.lower(): v for k, v in values.items()}

    def sub(m):
        name = m.group(1).strip()
        key = name.lower()
        if key in AUTO_FIELDS:
            return AUTO_FIELDS[key]()
        return low.get(key, m.group(0))

    return PLACEHOLDER_RE.sub(sub, text or "")


def expand(path: str) -> str:
    return os.path.expandvars(os.path.expanduser((path or "").strip()))


def open_target(target: str):
    """Открыть файл, папку, ссылку или запустить программу системным способом."""
    t = (target or "").strip()
    if not t:
        raise ValueError("Не указан путь или ссылка")
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", t) or t.startswith("mailto:"):
        webbrowser.open(t)
        return
    p = expand(t)
    if not os.path.exists(p):
        raise FileNotFoundError(f"Не найдено: {p}")
    if sys.platform.startswith("win"):
        os.startfile(p)  # noqa: S606  (штатный способ открытия в Windows)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", p])
    else:
        subprocess.Popen(["xdg-open", p])


def copy_text(text: str):
    QApplication.clipboard().setText(text or "")


def paste_to_active_window():
    """Ctrl+V в активное окно (после того как мы спрятались)."""
    try:
        from pynput.keyboard import Controller, Key
        kb = Controller()
        with kb.pressed(Key.ctrl):
            kb.press("v")
            kb.release("v")
    except Exception:
        pass


class FillDialog(QDialog):
    """Окно подстановки значений в шаблон + предпросмотр."""

    def __init__(self, title: str, template: str, fields, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Шаблон: {title}")
        self.setMinimumWidth(520)
        self.template = template
        self.edits = {}

        root = QVBoxLayout(self)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        for name in fields:
            e = QLineEdit()
            e.setPlaceholderText(name)
            e.textChanged.connect(self._refresh)
            self.edits[name] = e
            form.addRow(name + ":", e)
        root.addLayout(form)

        root.addWidget(QLabel("Предпросмотр:"))
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setMinimumHeight(140)
        root.addWidget(self.preview)

        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.button(QDialogButtonBox.Ok).setText("Копировать")
        box.button(QDialogButtonBox.Cancel).setText("Отмена")
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        root.addWidget(box)

        if fields:
            self.edits[fields[0]].setFocus()
        self._refresh()

    def values(self) -> dict:
        return {k: e.text() for k, e in self.edits.items()}

    def result_text(self) -> str:
        return fill(self.template, self.values())

    def _refresh(self):
        self.preview.setPlainText(self.result_text())


def unique_path(path: str) -> str:
    """Не перезатираем существующий файл — добавляем (2), (3)..."""
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    i = 2
    while os.path.exists(f"{base} ({i}){ext}"):
        i += 1
    return f"{base} ({i}){ext}"


def safe_name(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", name).strip() or "Документ"


def run_item(item: dict, parent=None, settings=None) -> str:
    """Выполнить действие. Возвращает текст для уведомления."""
    settings = settings or {}
    kind = item.get("type", "copy")
    title = item.get("title", "")

    if kind == "open":
        open_target(item.get("target", ""))
        return f"Открыто: {title}"

    if kind == "copy":
        text = fill(item.get("text", ""), {})
        copy_text(text)
        if settings.get("paste_after_copy"):
            paste_to_active_window()
        return f"Скопировано: {title}"

    if kind == "template":
        tpl = item.get("text", "")
        fields = placeholders(tpl)
        if not fields:
            copy_text(fill(tpl, {}))
            if settings.get("paste_after_copy"):
                paste_to_active_window()
            return f"Скопировано: {title}"
        dlg = FillDialog(title, tpl, fields, parent)
        if dlg.exec() != QDialog.Accepted:
            return ""
        copy_text(dlg.result_text())
        if settings.get("paste_after_copy"):
            paste_to_active_window()
        return f"Скопировано: {title}"

    if kind == "doc_copy":
        src = expand(item.get("template_file", ""))
        if not os.path.isfile(src):
            raise FileNotFoundError(f"Шаблон не найден: {src}")
        out_dir = expand(item.get("output_dir", "")) or os.path.dirname(src)
        os.makedirs(out_dir, exist_ok=True)

        pattern = item.get("name_pattern") or "{дата_файл}_" + os.path.splitext(os.path.basename(src))[0]
        fields = placeholders(pattern)
        values = {}
        if fields:
            dlg = FillDialog(title, pattern, fields, parent)
            if dlg.exec() != QDialog.Accepted:
                return ""
            values = dlg.values()

        ext = os.path.splitext(src)[1]
        name = safe_name(fill(pattern, values)) + ext
        dst = unique_path(os.path.join(out_dir, name))
        shutil.copy2(src, dst)
        if item.get("open_after", True):
            open_target(dst)
        return f"Создан документ: {os.path.basename(dst)}"

    raise ValueError(f"Неизвестный тип действия: {kind}")


def notify_error(parent, exc: Exception):
    QMessageBox.warning(parent, "QuickDeck", str(exc))
