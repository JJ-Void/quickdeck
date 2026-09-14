"""Оформление: шрифт Manrope, токены цвета, стекло Windows.

Цвет описан ролями, а не значениями: компоненты просят `TEXT`, `HAIRLINE`,
`SURFACE`, а не «серый 20%». Один акцент на экран — у выбранного пункта.
"""
import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
FONT_DIR = os.path.join(ASSETS, "fonts")

FAMILY = "Manrope"          # подменяется на системный, если файлы не нашлись
_loaded = False

# --- роли цвета (светлая нейтраль) ---
TEXT = QColor(18, 20, 24)                 # основной текст
TEXT_MUTED = QColor(18, 20, 24, 130)      # подписи соседних пунктов
TEXT_FAINT = QColor(18, 20, 24, 78)       # служебные подсказки
SURFACE = QColor(255, 255, 255, 232)      # карточка на стекле
SURFACE_SOFT = QColor(255, 255, 255, 96)  # капсула невыбранного пункта
HAIRLINE = QColor(18, 20, 24, 28)         # тонкая линия-структура
HAIRLINE_SOFT = QColor(18, 20, 24, 16)
GLASS = QColor(248, 249, 251, 170)        # подложка панели, если блюра нет
SHADOW = QColor(18, 20, 24, 30)

WEIGHT = {400: QFont.Normal, 500: QFont.Medium, 600: QFont.DemiBold, 700: QFont.Bold}


def load_fonts() -> str:
    """Регистрирует Manrope. Возвращает имя семейства, доступное приложению."""
    global FAMILY, _loaded
    if _loaded:
        return FAMILY
    _loaded = True
    families = set()
    if os.path.isdir(FONT_DIR):
        for name in sorted(os.listdir(FONT_DIR)):
            if name.lower().endswith((".ttf", ".otf")):
                fid = QFontDatabase.addApplicationFont(os.path.join(FONT_DIR, name))
                if fid != -1:
                    families.update(QFontDatabase.applicationFontFamilies(fid))
    if families:
        FAMILY = sorted(families)[0]
    else:
        FAMILY = "Segoe UI"     # запасной вариант, чтобы приложение всё равно поднялось
    return FAMILY


def font(size: float, weight: int = 400, tracking: float = 0.0) -> QFont:
    f = QFont(load_fonts())
    f.setPointSizeF(size)
    f.setWeight(WEIGHT.get(weight, QFont.Normal))
    if tracking:
        f.setLetterSpacing(QFont.AbsoluteSpacing, tracking)
    f.setHintingPreference(QFont.PreferNoHinting)   # ровные штрихи на дробном DPI
    return f


def alpha(color: QColor, a: int) -> QColor:
    c = QColor(color)
    c.setAlpha(a)
    return c


def enable_glass(widget, tint: QColor = QColor(250, 251, 253), opacity: int = 150) -> bool:
    """Акриловое размытие позади окна (Windows 10/11).

    Официального API нет, поэтому идём через недокументированную
    SetWindowCompositionAttribute. Не вышло — возвращаем False, и виджет
    рисует свою полупрозрачную подложку сам.
    """
    if not sys.platform.startswith("win"):
        return False
    try:
        import ctypes
        from ctypes import wintypes

        class ACCENTPOLICY(ctypes.Structure):
            _fields_ = [
                ("AccentState", ctypes.c_int),
                ("AccentFlags", ctypes.c_int),
                ("GradientColor", ctypes.c_uint),
                ("AnimationId", ctypes.c_int),
            ]

        class WINCOMPATTRDATA(ctypes.Structure):
            _fields_ = [
                ("Attribute", ctypes.c_int),
                ("Data", ctypes.POINTER(ACCENTPOLICY)),
                ("SizeOfData", ctypes.c_size_t),
            ]

        ACCENT_ENABLE_ACRYLICBLURBEHIND = 4
        WCA_ACCENT_POLICY = 19

        # цвет задаётся как AABBGGRR
        gradient = (opacity << 24) | (tint.blue() << 16) | (tint.green() << 8) | tint.red()
        policy = ACCENTPOLICY(ACCENT_ENABLE_ACRYLICBLURBEHIND, 2, gradient, 0)
        data = WINCOMPATTRDATA(WCA_ACCENT_POLICY, ctypes.pointer(policy),
                               ctypes.sizeof(policy))
        user32 = ctypes.windll.user32
        fn = user32.SetWindowCompositionAttribute
        fn.argtypes = [wintypes.HWND, ctypes.POINTER(WINCOMPATTRDATA)]
        fn.restype = ctypes.c_int
        return bool(fn(int(widget.winId()), ctypes.byref(data)))
    except Exception:
        return False
