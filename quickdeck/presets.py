"""Наборы кнопок: экспорт, импорт и готовые заготовки.

Набор — это обычный JSON с категориями и кнопками, без личных путей к
конфигу и без положения виджета на экране. Такой файл можно скинуть
сотруднику: он положит его к себе и получит ровно тот же набор.
"""
import json
import os

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QPushButton,
    QLabel, QFileDialog, QMessageBox, QWidget,
)

from . import config as cfg
from . import icons

KIND = "quickdeck-preset"
EXT = "Наборы QuickDeck (*.qdeck.json *.json)"

BUNDLED_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "presets")


# ----------------------------------------------------------------- файлы
def bundled() -> list:
    """Заготовки, лежащие рядом с программой."""
    out = []
    for folder in (BUNDLED_DIR, os.path.join(cfg.app_dir(), "presets"),
                   os.path.join(cfg.data_dir(), "presets")):
        if not os.path.isdir(folder):
            continue
        for name in sorted(os.listdir(folder)):
            if not name.endswith(".json"):
                continue
            path = os.path.join(folder, name)
            if any(p["path"] == path for p in out):
                continue
            try:
                data = read(path)
            except (OSError, ValueError):
                continue
            out.append({"path": path, "data": data})
    return out


def read(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or not isinstance(data.get("groups"), list):
        raise ValueError("Это не набор QuickDeck: нет списка категорий")
    return data


def write(config: dict, path: str, name: str = "") -> str:
    """Выгрузить текущие категории в файл."""
    data = {
        "kind": KIND,
        "version": 1,
        "name": name or os.path.splitext(os.path.basename(path))[0],
        "accent": config.get("settings", {}).get("accent", "#5b8cff"),
        "groups": json.loads(json.dumps(config.get("groups", []))),
    }
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    return path


def delete(path: str) -> None:
    """Убрать заготовку с диска. Нужно, когда набор раздаётся дальше:
    свой рабочий набор не должен уехать вместе с программой к друзьям."""
    os.remove(path)


def apply(config: dict, preset: dict, mode: str = "replace") -> dict:
    """Влить набор в конфиг. mode: replace — заменить, merge — добавить."""
    groups = json.loads(json.dumps(preset.get("groups", [])))
    for g in groups:                      # свежие id, чтобы не столкнуться
        g["id"] = cfg.new_id("g")
        for it in g.get("items", []):
            it["id"] = cfg.new_id()
    if mode == "merge":
        config.setdefault("groups", []).extend(groups)
    else:
        config["groups"] = groups
        if preset.get("accent"):
            config.setdefault("settings", {})["accent"] = preset["accent"]
    return cfg._migrate(config)


def count(preset: dict) -> tuple:
    groups = preset.get("groups", [])
    return len(groups), sum(len(g.get("items", [])) for g in groups)


# ----------------------------------------------------------------- окно
class PresetDialog(QDialog):
    """Выбор заготовки, загрузка из файла и выгрузка своего набора."""

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Наборы кнопок")
        self.resize(620, 460)
        self.config = config
        self.changed = False

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Готовые заготовки:"))

        self.list = QListWidget()
        self.list.setIconSize(QSize(22, 22))
        self.list.currentItemChanged.connect(self._describe)
        lay.addWidget(self.list, 1)

        self.info = QLabel("")
        self.info.setWordWrap(True)
        self.info.setStyleSheet("color:#666;")
        self.info.setMinimumHeight(54)
        lay.addWidget(self.info)

        row = QHBoxLayout()
        self.b_replace = QPushButton("Заменить моими")
        self.b_replace.setToolTip("Текущие категории будут заменены набором")
        self.b_replace.clicked.connect(lambda: self._apply_selected("replace"))
        self.b_merge = QPushButton("Добавить к моим")
        self.b_merge.clicked.connect(lambda: self._apply_selected("merge"))
        self.b_del = QPushButton("Удалить заготовку")
        self.b_del.setToolTip("Удалить файл набора с диска — например, рабочий набор "
                              "перед тем, как отдать программу кому-то ещё")
        self.b_del.clicked.connect(self._delete_selected)
        row.addWidget(self.b_replace)
        row.addWidget(self.b_merge)
        row.addStretch(1)
        row.addWidget(self.b_del)
        lay.addLayout(row)

        row2 = QHBoxLayout()
        b_open = QPushButton("Загрузить из файла…")
        b_open.clicked.connect(self._from_file)
        b_save = QPushButton("Сохранить мой набор в файл…")
        b_save.clicked.connect(self._to_file)
        b_close = QPushButton("Закрыть")
        b_close.clicked.connect(self.accept)
        row2.addWidget(b_open)
        row2.addWidget(b_save)
        row2.addStretch(1)
        row2.addWidget(b_close)
        lay.addLayout(row2)

        self._fill()

    def _fill(self):
        self.list.clear()
        for p in bundled():
            d = p["data"]
            g, n = count(d)
            row = QListWidgetItem(f"{d.get('name', '—')}    ·  {g} категорий, {n} кнопок")
            first = (d.get("groups") or [{}])[0].get("icon", "layers")
            row.setIcon(QIcon(icons.pixmap(
                first if icons.exists(first) else "layers", 22,
                QColor(d.get("accent") or "#5b8cff"), dpr=2)))
            row.setData(Qt.UserRole, p)
            self.list.addItem(row)
        if self.list.count():
            self.list.setCurrentRow(0)
        else:
            self.info.setText("Заготовок рядом с программой не найдено — "
                              "можно загрузить набор из файла.")
        has = self.list.count() > 0
        self.b_replace.setEnabled(has)
        self.b_merge.setEnabled(has)
        self.b_del.setEnabled(has)

    def _describe(self, *_):
        row = self.list.currentItem()
        if not row:
            return
        d = row.data(Qt.UserRole)["data"]
        names = ", ".join(g.get("name", "") for g in d.get("groups", []))
        self.info.setText(f"{d.get('description', '')}\nКатегории: {names}")

    def _delete_selected(self):
        row = self.list.currentItem()
        if not row:
            return
        entry = row.data(Qt.UserRole)
        name = entry["data"].get("name", os.path.basename(entry["path"]))
        ok = QMessageBox.question(
            self, "Удалить заготовку",
            f"Удалить файл набора «{name}»?\n\n{entry['path']}\n\n"
            "Кнопки, которые уже загружены в программу, останутся на месте — "
            "удаляется только сам файл заготовки.")
        if ok != QMessageBox.Yes:
            return
        try:
            delete(entry["path"])
        except OSError as e:
            QMessageBox.warning(self, "Не получилось удалить", str(e))
            return
        self._fill()

    def _apply_selected(self, mode: str):
        row = self.list.currentItem()
        if row:
            self._apply(row.data(Qt.UserRole)["data"], mode)

    def _apply(self, data: dict, mode: str):
        g, n = count(data)
        if mode == "replace":
            ok = QMessageBox.question(
                self, "Заменить набор",
                f"Текущие категории будут заменены на «{data.get('name', 'набор')}»\n"
                f"({g} категорий, {n} кнопок). Продолжить?")
            if ok != QMessageBox.Yes:
                return
        apply(self.config, data, mode)
        self.changed = True
        QMessageBox.information(
            self, "Готово",
            f"Набор загружен: {g} категорий, {n} кнопок.\n"
            "Пути и тексты можно поправить в «Кнопки и параметры».")

    def _from_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите файл набора", cfg.data_dir(), EXT)
        if not path:
            return
        try:
            data = read(path)
        except (OSError, ValueError) as e:
            QMessageBox.warning(self, "Не получилось", str(e))
            return
        mode = "replace"
        box = QMessageBox(self)
        box.setWindowTitle("Как загрузить")
        box.setText(f"Набор «{data.get('name', os.path.basename(path))}»")
        b_rep = box.addButton("Заменить мои", QMessageBox.AcceptRole)
        b_add = box.addButton("Добавить к моим", QMessageBox.ActionRole)
        box.addButton("Отмена", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is b_add:
            mode = "merge"
        elif box.clickedButton() is not b_rep:
            return
        self._apply(data, mode)

    def _to_file(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить набор",
            os.path.join(cfg.data_dir(), "мой-набор.qdeck.json"), EXT)
        if not path:
            return
        try:
            write(self.config, path)
        except OSError as e:
            QMessageBox.warning(self, "Не получилось", str(e))
            return
        g, n = count({"groups": self.config.get("groups", [])})
        QMessageBox.information(
            self, "Сохранено",
            f"{g} категорий и {n} кнопок записаны в файл:\n{path}\n\n"
            "Этот файл можно отдать сотруднику — он загрузит его тем же окном.")
