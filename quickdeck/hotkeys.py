"""Глобальные горячие клавиши и перехват «модификатор + колесо мыши».

Слушатели pynput работают в своих потоках, поэтому наружу всё уходит
сигналами Qt (очередь в главный поток GUI).
"""
from PySide6.QtCore import QObject, Signal

try:
    from pynput import keyboard, mouse
except Exception:  # pynput может отсутствовать при разработке
    keyboard = None
    mouse = None

MOD_KEYS = {
    "alt": {"alt", "alt_l", "alt_r", "alt_gr"},
    "ctrl": {"ctrl", "ctrl_l", "ctrl_r"},
    "shift": {"shift", "shift_l", "shift_r"},
}

NAMED = {
    "space": "space", "enter": "enter", "return": "enter", "tab": "tab",
    "esc": "esc", "escape": "esc", "backspace": "backspace", "insert": "insert",
    "delete": "delete", "home": "home", "end": "end",
    **{f"f{i}": f"f{i}" for i in range(1, 25)},
}


def _key_name(key) -> str:
    """Нормализованное имя нажатой клавиши."""
    if keyboard is None:
        return ""
    if isinstance(key, keyboard.Key):
        return key.name
    ch = getattr(key, "char", None)
    if ch:
        return ch.lower()
    vk = getattr(key, "vk", None)
    if vk is not None and 65 <= vk <= 90:
        return chr(vk).lower()
    return ""


def parse_hotkey(text: str):
    """'ctrl+space' -> ({'ctrl'}, 'space')"""
    parts = [p.strip().lower() for p in (text or "").split("+") if p.strip()]
    mods, main = set(), ""
    for p in parts:
        if p in ("ctrl", "control"):
            mods.add("ctrl")
        elif p == "alt":
            mods.add("alt")
        elif p == "shift":
            mods.add("shift")
        elif p in ("win", "cmd", "super"):
            mods.add("cmd")
        else:
            main = NAMED.get(p, p)
    return mods, main


class HotkeyBridge(QObject):
    """Сигналы в главный поток."""
    scroll = Signal(int, bool)   # шаг колеса и зажат ли модификатор
    mod_released = Signal()      # модификатор отпущен
    panel_hotkey = Signal()      # сработала горячая клавиша поиска


class HotkeyManager:
    def __init__(self, settings: dict):
        self.bridge = HotkeyBridge()
        self.settings = settings
        self._pressed = set()
        self._mod_active = False
        self._k_listener = None
        self._m_listener = None
        self.apply(settings)

    # ------------------------------------------------------------------
    def apply(self, settings: dict):
        self.settings = settings
        self.mod = settings.get("wheel_modifier", "alt")
        self.mod_names = MOD_KEYS.get(self.mod, MOD_KEYS["alt"])
        self.hk_mods, self.hk_main = parse_hotkey(settings.get("hotkey_panel", "ctrl+space"))

    def start(self):
        if keyboard is None or mouse is None:
            return False
        self._k_listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        self._m_listener = mouse.Listener(on_scroll=self._on_scroll)
        self._k_listener.daemon = True
        self._m_listener.daemon = True
        self._k_listener.start()
        self._m_listener.start()
        return True

    def stop(self):
        for l in (self._k_listener, self._m_listener):
            try:
                if l:
                    l.stop()
            except Exception:
                pass

    # ------------------------------------------------------------------
    def _mods_now(self):
        out = set()
        for name, keys in MOD_KEYS.items():
            if self._pressed & keys:
                out.add(name)
        if self._pressed & {"cmd", "cmd_l", "cmd_r"}:
            out.add("cmd")
        return out

    def _on_press(self, key):
        name = _key_name(key)
        if not name:
            return
        self._pressed.add(name)
        if name in self.mod_names:
            self._mod_active = True
        if self.hk_main and name == self.hk_main and self._mods_now() >= self.hk_mods:
            self.bridge.panel_hotkey.emit()

    def _on_release(self, key):
        name = _key_name(key)
        self._pressed.discard(name)
        if name in self.mod_names and self._mod_active:
            self._mod_active = False
            self.bridge.mod_released.emit()

    def _on_scroll(self, x, y, dx, dy):
        # шлём каждую прокрутку: пока колесо открыто, оно слушает их все,
        # даже когда модификатор уже отпущен (режим «закреплено»)
        self.bridge.scroll.emit(-1 if dy > 0 else 1,
                                bool(self._pressed & self.mod_names))
