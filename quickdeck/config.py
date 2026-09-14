"""Загрузка/сохранение конфигурации QuickDeck."""
import json
import os
import shutil
import sys
import uuid

from . import icons

APP_NAME = "QuickDeck"


def app_dir() -> str:
    """Папка, где лежит .exe (или проект в режиме разработки)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def data_dir() -> str:
    """Папка пользовательских данных: рядом с exe, если туда можно писать,
    иначе %APPDATA%\\QuickDeck. После установки инсталлятором — второй случай."""
    local = app_dir()
    try:
        probe = os.path.join(local, ".write_test")
        with open(probe, "w") as f:
            f.write("")
        os.remove(probe)
        return local
    except OSError:
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        folder = os.path.join(base, APP_NAME)
        os.makedirs(folder, exist_ok=True)
        return folder


def config_path() -> str:
    """Конфиг рядом с .exe — приложение полностью портативное.

    Если папка рядом с .exe недоступна для записи (Program Files),
    падаем в %APPDATA%\\QuickDeck.
    """
    local = os.path.join(app_dir(), "quickdeck.json")
    if os.path.exists(local):
        return local
    return os.path.join(data_dir(), "quickdeck.json")


DEFAULT_CONFIG = {
    "version": 1,
    "settings": {
        "hotkey_panel": "ctrl+space",      # показать/скрыть панель-палитру
        "wheel_modifier": "alt",           # зажать и крутить колесо -> радиальное меню
        "wheel_side": "right",             # к какому краю прижато колесо
        "ui_scale": 1.0,                   # масштаб колеса, 0.7-1.8
        "handle_enabled": True,            # маленькая ручка у края экрана
        "handle_pos": 0.5,                 # её положение по высоте, 0..1
        "accent": "#3c6df0",
                "paste_after_copy": False,         # авто-Ctrl+V после копирования
        "start_with_windows": False,
    },
    "groups": [
        {
            "id": "g-docs",
            "name": "Документы",
            "color": "#3c6df0",
            "icon": "file-text",
            "items": [
                {
                    "id": "i-1",
                    "type": "open",
                    "title": "Папка сделок",
                    "icon": "folder",
                    "target": "C:\\Work\\Сделки",
                    "color": "#f5a524",
                    "note": "Рабочая папка с текущими клиентами",
                },
                {
                    "id": "i-2",
                    "type": "doc_copy",
                    "title": "Договор (новый)",
                    "icon": "file-plus",
                    "template_file": "C:\\Work\\Шаблоны\\Договор.docx",
                    "output_dir": "C:\\Work\\Сделки",
                    "name_pattern": "Договор_{дата_файл}_{клиент}",
                    "color": "#e5484d",
                    "open_after": True,
                },
            ],
        },
        {
            "id": "g-msg",
            "name": "Сообщения",
            "color": "#1f9d6b",
            "icon": "message-square",
            "items": [
                {
                    "id": "i-3",
                    "type": "copy",
                    "title": "Реквизиты",
                    "icon": "building-2",
                    "color": "#3e63dd",
                    "text": "ООО «Компания»\nИНН 0000000000\nР/с 40702810000000000000",
                },
                {
                    "id": "i-4",
                    "type": "template",
                    "title": "КП клиенту",
                    "icon": "mail",
                    "color": "#d6409f",
                    "text": (
                        "Здравствуйте, {имя}!\n\n"
                        "Направляю коммерческое предложение по объекту {объект}.\n"
                        "Стоимость — {сумма} руб. Предложение действует до {срок}.\n\n"
                        "С уважением,\n{подпись}"
                    ),
                },
            ],
        },
        {
            "id": "g-links",
            "name": "Ссылки",
            "color": "#b5651d",
            "icon": "link",
            "items": [
                {
                    "id": "i-5",
                    "type": "open",
                    "title": "CRM",
                    "icon": "globe",
                    "color": "#30a46c",
                    "target": "https://example.com",
                }
            ],
        },
    ],
}


def new_id(prefix: str = "i") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def load() -> dict:
    path = config_path()
    if not os.path.exists(path):
        save(DEFAULT_CONFIG)
        return json.loads(json.dumps(DEFAULT_CONFIG))
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        # битый конфиг не теряем — отводим в сторону
        try:
            shutil.copy2(path, path + ".broken")
        except OSError:
            pass
        data = json.loads(json.dumps(DEFAULT_CONFIG))
    return _migrate(data)


def _migrate(data: dict) -> dict:
    data.setdefault("version", 1)
    settings = data.setdefault("settings", {})
    for k, v in DEFAULT_CONFIG["settings"].items():
        settings.setdefault(k, v)
    groups = data.setdefault("groups", [])
    for g in groups:
        g.setdefault("id", new_id("g"))
        g.setdefault("name", "Без названия")
        g.setdefault("color", settings["accent"])
        g.setdefault("icon", "📁")
        if not icons.exists(g.get("icon", "")):
            g["icon"] = "folder"          # старые конфиги хранили эмодзи
        for it in g.setdefault("items", []):
            it.setdefault("id", new_id())
            it.setdefault("type", "copy")
            it.setdefault("title", "Без названия")
            it["icon"] = icons.resolve(it)
    return data


def save(data: dict) -> str:
    path = config_path()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    return path
