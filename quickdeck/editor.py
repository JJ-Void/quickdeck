"""Окно настройки: группы, кнопки, параметры приложения."""
import os

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon, QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem, QPushButton,
    QLabel, QLineEdit, QComboBox, QPlainTextEdit, QWidget, QFormLayout, QCheckBox,
    QFileDialog, QMessageBox, QStackedWidget, QSpinBox, QTabWidget, QGroupBox,
    QListWidget, QListWidgetItem, QDialogButtonBox,
)

from . import config as cfg
from . import icons
from . import presets as presets_mod
from .actions import placeholders


class IconPicker(QDialog):
    """Сетка иконок с поиском — вместо ручного ввода эмодзи."""

    def __init__(self, current: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Выбор иконки")
        self.resize(560, 520)
        self.chosen = current

        lay = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Поиск: folder, mail, calendar…")
        self.search.textChanged.connect(self._refresh)
        lay.addWidget(self.search)

        self.grid = QListWidget()
        self.grid.setViewMode(QListWidget.IconMode)
        self.grid.setIconSize(QSize(26, 26))
        self.grid.setGridSize(QSize(92, 84))
        self.grid.setResizeMode(QListWidget.Adjust)
        self.grid.setMovement(QListWidget.Static)
        self.grid.setSpacing(4)
        self.grid.itemDoubleClicked.connect(lambda _: self.accept())
        lay.addWidget(self.grid, 1)

        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        lay.addWidget(box)
        self._refresh()

    def _refresh(self):
        q = self.search.text().strip().lower()
        self.grid.clear()
        ink = QColor(18, 20, 24)
        for name in icons.names():
            if q and q not in name:
                continue
            row = QListWidgetItem(QIcon(icons.pixmap(name, 26, ink, dpr=2)), name)
            row.setData(Qt.UserRole, name)
            row.setTextAlignment(Qt.AlignCenter)
            self.grid.addItem(row)
            if name == self.chosen:
                self.grid.setCurrentItem(row)
        if not self.grid.currentItem() and self.grid.count():
            self.grid.setCurrentRow(0)

    def accept(self):
        row = self.grid.currentItem()
        if row:
            self.chosen = row.data(Qt.UserRole)
        super().accept()

TYPES = [
    ("open", "Открыть файл / папку / ссылку"),
    ("copy", "Копировать текст"),
    ("template", "Шаблон с подстановкой {поля}"),
    ("doc_copy", "Создать копию шаблона документа"),
]
TYPE_KEYS = [t[0] for t in TYPES]


class Editor(QDialog):
    saved = Signal(dict)

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("QuickDeck — настройка")
        self.resize(940, 620)
        self.config = config

        tabs = QTabWidget()
        tabs.addTab(self._build_content_tab(), "Кнопки")
        tabs.addTab(self._build_settings_tab(), "Параметры")

        root = QVBoxLayout(self)
        root.addWidget(tabs, 1)

        foot = QHBoxLayout()
        self.path_label = QLabel(f"Конфиг: {cfg.config_path()}")
        self.path_label.setStyleSheet("color:#888;")
        foot.addWidget(self.path_label, 1)
        b_sets = QPushButton("Наборы…")
        b_sets.setToolTip("Готовые заготовки, загрузка и выгрузка набора в файл")
        b_sets.clicked.connect(self._presets)
        foot.addWidget(b_sets)
        b_ok = QPushButton("Сохранить")
        b_ok.setDefault(True)
        b_ok.clicked.connect(self._save)
        b_cancel = QPushButton("Закрыть")
        b_cancel.clicked.connect(self.reject)
        foot.addWidget(b_ok)
        foot.addWidget(b_cancel)
        root.addLayout(foot)

        self._fill_tree()


    def _icon_button(self, slot) -> QPushButton:
        b = QPushButton("")
        b.setIconSize(QSize(18, 18))
        b.setMinimumWidth(180)
        b.clicked.connect(slot)
        return b

    def _set_icon_button(self, button: QPushButton, name: str):
        name = name if icons.exists(name) else "folder"
        button.setProperty("icon_name", name)
        button.setIcon(QIcon(icons.pixmap(name, 18, QColor(18, 20, 24), dpr=2)))
        button.setText("  " + name)

    def _pick_icon(self, button: QPushButton, after):
        dlg = IconPicker(button.property("icon_name") or "", self)
        if dlg.exec() == QDialog.Accepted:
            self._set_icon_button(button, dlg.chosen)
            after()

    # ================= вкладка «Кнопки» =================
    def _build_content_tab(self) -> QWidget:
        page = QWidget()
        lay = QHBoxLayout(page)

        left = QVBoxLayout()
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setDragDropMode(QTreeWidget.InternalMove)
        self.tree.currentItemChanged.connect(self._on_select)
        left.addWidget(self.tree, 1)

        btns = QHBoxLayout()
        for text, slot, tip in (
            ("+ группа", self._add_group, "Добавить группу"),
            ("+ кнопка", self._add_item, "Добавить кнопку в выбранную группу"),
            ("▲", lambda: self._move(-1), "Выше"),
            ("▼", lambda: self._move(1), "Ниже"),
            ("✕", self._delete, "Удалить"),
        ):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.clicked.connect(slot)
            btns.addWidget(b)
        left.addLayout(btns)
        lay.addLayout(left, 1)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._empty_page())     # 0
        self.stack.addWidget(self._group_page())     # 1
        self.stack.addWidget(self._item_page())      # 2
        lay.addWidget(self.stack, 2)
        return page

    def _empty_page(self):
        w = QWidget()
        l = QVBoxLayout(w)
        lbl = QLabel("Выберите группу или кнопку слева,\nлибо добавьте новую.")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("color:#888;")
        l.addWidget(lbl)
        return w

    def _group_page(self):
        w = QWidget()
        f = QFormLayout(w)
        self.g_name = QLineEdit()
        self.g_icon = self._icon_button(lambda: self._pick_icon(self.g_icon, self._apply_group))
        self.g_color = QLineEdit()
        self.g_color.setPlaceholderText("#4da3ff")
        for e in (self.g_name, self.g_color):
            e.textChanged.connect(self._apply_group)
        f.addRow("Название:", self.g_name)
        f.addRow("Иконка:", self.g_icon)
        f.addRow("Цвет:", self.g_color)
        return w

    def _item_page(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        f = QFormLayout()
        self.i_title = QLineEdit()
        self.i_icon = self._icon_button(lambda: self._pick_icon(self.i_icon, self._apply_item))
        self.i_type = QComboBox()
        for key, label in TYPES:
            self.i_type.addItem(label, key)
        self.i_note = QLineEdit()
        self.i_note.setPlaceholderText("подсказка, видна в колесе")
        self.i_color = QLineEdit()
        self.i_color.setPlaceholderText("#ff5fa2 — цвет подсветки в колесе (можно пусто)")
        f.addRow("Название:", self.i_title)
        f.addRow("Иконка:", self.i_icon)
        f.addRow("Тип:", self.i_type)
        f.addRow("Подсказка:", self.i_note)
        f.addRow("Цвет:", self.i_color)
        lay.addLayout(f)

        # --- open
        self.box_open = QGroupBox("Что открыть")
        bo = QHBoxLayout(self.box_open)
        self.i_target = QLineEdit()
        self.i_target.setPlaceholderText(r"C:\Work\Шаблоны  или  https://...")
        b_file = QPushButton("Файл…")
        b_dir = QPushButton("Папка…")
        b_file.clicked.connect(lambda: self._pick_file(self.i_target))
        b_dir.clicked.connect(lambda: self._pick_dir(self.i_target))
        bo.addWidget(self.i_target, 1)
        bo.addWidget(b_file)
        bo.addWidget(b_dir)
        lay.addWidget(self.box_open)

        # --- text / template
        self.box_text = QGroupBox("Текст")
        bt = QVBoxLayout(self.box_text)
        self.i_text = QPlainTextEdit()
        self.i_text.setPlaceholderText(
            "Здравствуйте, {имя}!\nПо объекту {объект} сумма {сумма} руб.\n\n"
            "{дата} и {время} подставляются автоматически."
        )
        bt.addWidget(self.i_text)
        self.fields_label = QLabel("")
        self.fields_label.setStyleSheet("color:#888;")
        bt.addWidget(self.fields_label)
        lay.addWidget(self.box_text, 1)

        # --- doc copy
        self.box_doc = QGroupBox("Шаблон документа")
        fd = QFormLayout(self.box_doc)
        row1 = QHBoxLayout()
        self.i_tpl_file = QLineEdit()
        b1 = QPushButton("Обзор…")
        b1.clicked.connect(lambda: self._pick_file(self.i_tpl_file))
        row1.addWidget(self.i_tpl_file, 1)
        row1.addWidget(b1)
        row2 = QHBoxLayout()
        self.i_out_dir = QLineEdit()
        b2 = QPushButton("Обзор…")
        b2.clicked.connect(lambda: self._pick_dir(self.i_out_dir))
        row2.addWidget(self.i_out_dir, 1)
        row2.addWidget(b2)
        self.i_pattern = QLineEdit()
        self.i_pattern.setPlaceholderText("Договор_{дата_файл}_{клиент}")
        self.i_open_after = QCheckBox("Открыть после создания")
        fd.addRow("Файл-шаблон:", row1)
        fd.addRow("Куда сохранять:", row2)
        fd.addRow("Имя файла:", self.i_pattern)
        fd.addRow("", self.i_open_after)
        lay.addWidget(self.box_doc)

        for e in (self.i_title, self.i_note, self.i_color, self.i_target,
                  self.i_tpl_file, self.i_out_dir, self.i_pattern):
            e.textChanged.connect(self._apply_item)
        self.i_text.textChanged.connect(self._apply_item)
        self.i_open_after.toggled.connect(self._apply_item)
        self.i_type.currentIndexChanged.connect(self._type_changed)
        return w

    # ================= вкладка «Параметры» =================
    def _build_settings_tab(self) -> QWidget:
        w = QWidget()
        f = QFormLayout(w)
        s = self.config.get("settings", {})

        self.s_hotkey = QLineEdit(s.get("hotkey_panel", "ctrl+space"))
        self.s_hotkey.setPlaceholderText("ctrl+space, ctrl+alt+q, f9 …")
        self.s_modifier = QComboBox()
        self.s_modifier.addItems(["alt", "ctrl", "shift"])
        self.s_modifier.setCurrentText(s.get("wheel_modifier", "alt"))
        self.s_wheel_side = QComboBox()
        self.s_wheel_side.addItem("справа", "right")
        self.s_wheel_side.addItem("слева", "left")
        self.s_wheel_side.setCurrentIndex(0 if s.get("wheel_side", "right") != "left" else 1)
        self.s_scale = QSpinBox()
        self.s_scale.setRange(70, 180)
        self.s_scale.setSingleStep(5)
        self.s_scale.setSuffix(" %")
        self.s_scale.setValue(int(round(float(s.get("ui_scale", 1.0)) * 100)))
        self.s_handle = QCheckBox("Показывать ручку у края экрана")
        self.s_handle.setChecked(bool(s.get("handle_enabled", True)))
        self.s_paste = QCheckBox("Вставлять сразу в активное окно (Ctrl+V)")
        self.s_paste.setChecked(bool(s.get("paste_after_copy", False)))
        self.s_autostart = QCheckBox("Запускать вместе с Windows")
        self.s_autostart.setChecked(bool(s.get("start_with_windows", False)))
        self.s_accent = QLineEdit(s.get("accent", "#4da3ff"))

        f.addRow("Горячая клавиша поиска:", self.s_hotkey)
        f.addRow("Модификатор колеса:", self.s_modifier)
        f.addRow("Колесо у края:", self.s_wheel_side)
        f.addRow("Масштаб колеса:", self.s_scale)
        f.addRow("", self.s_handle)
        f.addRow("", self.s_paste)
        f.addRow("", self.s_autostart)
        f.addRow("Цвет акцента:", self.s_accent)

        note = QLabel(
            "Колесо: зажать модификатор и крутить колесо мыши.\n"
            "Левая кнопка и Enter — вперёд, правая и Esc — назад.\n"
            "Ручку у края можно перетащить к любой стороне экрана."
        )
        note.setStyleSheet("color:#888;")
        f.addRow(note)
        return w

    # ================= дерево =================
    def _fill_tree(self, select_path=None):
        self.tree.blockSignals(True)
        self.tree.clear()
        for gi, g in enumerate(self.config.get("groups", [])):
            gnode = QTreeWidgetItem([g.get("name", "")])
            gnode.setIcon(0, QIcon(icons.pixmap(
                g.get("icon") or "folder", 16, QColor(g.get("color") or "#3c6df0"), dpr=2)))
            gnode.setData(0, Qt.UserRole, ("group", gi, -1))
            self.tree.addTopLevelItem(gnode)
            for ii, it in enumerate(g.get("items", [])):
                inode = QTreeWidgetItem([it.get("title", "")])
                inode.setIcon(0, QIcon(icons.pixmap(
                    icons.resolve(it), 16,
                    QColor(it.get("color") or g.get("color") or "#3c6df0"), dpr=2)))
                inode.setData(0, Qt.UserRole, ("item", gi, ii))
                gnode.addChild(inode)
            gnode.setExpanded(True)
        self.tree.blockSignals(False)
        if select_path:
            self._select_path(select_path)

    def _select_path(self, path):
        for i in range(self.tree.topLevelItemCount()):
            g = self.tree.topLevelItem(i)
            if g.data(0, Qt.UserRole) == path:
                self.tree.setCurrentItem(g)
                return
            for j in range(g.childCount()):
                c = g.child(j)
                if c.data(0, Qt.UserRole) == path:
                    self.tree.setCurrentItem(c)
                    return

    def _current(self):
        node = self.tree.currentItem()
        return node.data(0, Qt.UserRole) if node else None

    def _on_select(self, *_):
        cur = self._current()
        if not cur:
            self.stack.setCurrentIndex(0)
            return
        kind, gi, ii = cur
        groups = self.config["groups"]
        if kind == "group":
            g = groups[gi]
            self._loading = True
            self.g_name.setText(g.get("name", ""))
            self._set_icon_button(self.g_icon, g.get("icon", ""))
            self.g_color.setText(g.get("color", ""))
            self._loading = False
            self.stack.setCurrentIndex(1)
        else:
            it = groups[gi]["items"][ii]
            self._loading = True
            self.i_title.setText(it.get("title", ""))
            self._set_icon_button(self.i_icon, icons.resolve(it))
            self.i_note.setText(it.get("note", ""))
            self.i_color.setText(it.get("color", ""))
            self.i_type.setCurrentIndex(TYPE_KEYS.index(it.get("type", "copy")))
            self.i_target.setText(it.get("target", ""))
            self.i_text.setPlainText(it.get("text", ""))
            self.i_tpl_file.setText(it.get("template_file", ""))
            self.i_out_dir.setText(it.get("output_dir", ""))
            self.i_pattern.setText(it.get("name_pattern", ""))
            self.i_open_after.setChecked(bool(it.get("open_after", True)))
            self._loading = False
            self._type_changed()
            self.stack.setCurrentIndex(2)

    _loading = False

    # ================= правки =================
    def _apply_group(self):
        if self._loading:
            return
        cur = self._current()
        if not cur or cur[0] != "group":
            return
        g = self.config["groups"][cur[1]]
        g["name"] = self.g_name.text()
        g["icon"] = self.g_icon.property("icon_name") or "folder"
        g["color"] = self.g_color.text() or "#4da3ff"
        node = self.tree.currentItem()
        node.setText(0, g["name"])
        node.setIcon(0, QIcon(icons.pixmap(g["icon"], 16, QColor(g["color"]), dpr=2)))

    def _type_changed(self):
        key = self.i_type.currentData()
        self.box_open.setVisible(key == "open")
        self.box_text.setVisible(key in ("copy", "template"))
        self.box_doc.setVisible(key == "doc_copy")
        self._apply_item()

    def _apply_item(self):
        if self._loading:
            return
        cur = self._current()
        if not cur or cur[0] != "item":
            return
        it = self.config["groups"][cur[1]]["items"][cur[2]]
        it["title"] = self.i_title.text()
        it["icon"] = self.i_icon.property("icon_name") or "folder"
        it["note"] = self.i_note.text()
        it["color"] = self.i_color.text().strip()
        it["type"] = self.i_type.currentData()
        it["target"] = self.i_target.text()
        it["text"] = self.i_text.toPlainText()
        it["template_file"] = self.i_tpl_file.text()
        it["output_dir"] = self.i_out_dir.text()
        it["name_pattern"] = self.i_pattern.text()
        it["open_after"] = self.i_open_after.isChecked()
        node = self.tree.currentItem()
        node.setText(0, it["title"])
        node.setIcon(0, QIcon(icons.pixmap(
            it["icon"], 16, QColor(it.get("color") or "#3c6df0"), dpr=2)))
        fields = placeholders(it["text"])
        self.fields_label.setText(
            "Поля для подстановки: " + ", ".join(fields) if fields
            else "Полей {…} нет — текст копируется как есть."
        )

    # ================= кнопки дерева =================
    def _add_group(self):
        self.config.setdefault("groups", []).append({
            "id": cfg.new_id("g"), "name": "Новая группа", "icon": "📁",
            "color": "#3c6df0", "items": [],
        })
        self._fill_tree(("group", len(self.config["groups"]) - 1, -1))

    def _add_item(self):
        cur = self._current()
        if not cur:
            if not self.config.get("groups"):
                self._add_group()
                cur = ("group", 0, -1)
            else:
                cur = ("group", 0, -1)
        gi = cur[1]
        self.config["groups"][gi].setdefault("items", []).append({
            "id": cfg.new_id(), "type": "copy", "title": "Новая кнопка",
            "icon": "clipboard-copy", "text": "",
        })
        self._fill_tree(("item", gi, len(self.config["groups"][gi]["items"]) - 1))

    def _move(self, delta: int):
        cur = self._current()
        if not cur:
            return
        kind, gi, ii = cur
        if kind == "group":
            arr, idx = self.config["groups"], gi
        else:
            arr, idx = self.config["groups"][gi]["items"], ii
        j = idx + delta
        if 0 <= j < len(arr):
            arr[idx], arr[j] = arr[j], arr[idx]
            self._fill_tree((kind, gi if kind == "item" else j, j if kind == "item" else -1))

    def _delete(self):
        cur = self._current()
        if not cur:
            return
        kind, gi, ii = cur
        name = (self.config["groups"][gi]["name"] if kind == "group"
                else self.config["groups"][gi]["items"][ii]["title"])
        if QMessageBox.question(self, "Удалить", f"Удалить «{name}»?") != QMessageBox.Yes:
            return
        if kind == "group":
            del self.config["groups"][gi]
        else:
            del self.config["groups"][gi]["items"][ii]
        self._fill_tree()
        self.stack.setCurrentIndex(0)

    # ================= файлы =================
    def _pick_file(self, edit: QLineEdit):
        path, _ = QFileDialog.getOpenFileName(self, "Выберите файл", edit.text() or os.path.expanduser("~"))
        if path:
            edit.setText(os.path.normpath(path))

    def _pick_dir(self, edit: QLineEdit):
        path = QFileDialog.getExistingDirectory(self, "Выберите папку", edit.text() or os.path.expanduser("~"))
        if path:
            edit.setText(os.path.normpath(path))

    def _presets(self):
        dlg = presets_mod.PresetDialog(self.config, self)
        dlg.exec()
        if dlg.changed:
            self._fill_tree()
            self.stack.setCurrentIndex(0)

    # ================= сохранение =================
    def _save(self):
        s = self.config.setdefault("settings", {})
        s["hotkey_panel"] = self.s_hotkey.text().strip() or "ctrl+space"
        s["wheel_modifier"] = self.s_modifier.currentText()
        s["wheel_side"] = self.s_wheel_side.currentData()
        s["ui_scale"] = self.s_scale.value() / 100.0
        s["handle_enabled"] = self.s_handle.isChecked()
        s["paste_after_copy"] = self.s_paste.isChecked()
        s["start_with_windows"] = self.s_autostart.isChecked()
        s["accent"] = self.s_accent.text().strip() or "#4da3ff"
        cfg.save(self.config)
        self.saved.emit(self.config)
        self.accept()
