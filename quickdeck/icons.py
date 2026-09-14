"""Линейные иконки (набор Lucide, ISC) вместо эмодзи.

SVG красим подменой `currentColor` и отдаём готовым QPixmap с учётом
масштаба экрана — на 125–200 % штрихи остаются ровными. Результат кэшируем:
одна и та же иконка рисуется в колесе каждый кадр.
"""
import os
import re

from PySide6.QtCore import QByteArray, Qt, QRectF
from PySide6.QtGui import QPixmap, QPainter, QColor
from PySide6.QtSvg import QSvgRenderer

ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icons")

_cache: dict = {}
_names: list = []

FALLBACK = "circle-check"

# чем подменяем эмодзи из старых конфигов
BY_TYPE = {
    "open": "folder",
    "copy": "clipboard-copy",
    "template": "mail",
    "doc_copy": "file-plus",
}


def names() -> list:
    """Все доступные имена иконок, по алфавиту."""
    global _names
    if not _names and os.path.isdir(ICON_DIR):
        _names = sorted(f[:-4] for f in os.listdir(ICON_DIR) if f.endswith(".svg"))
    return _names


def exists(name: str) -> bool:
    return bool(name) and name in names()


def resolve(item: dict) -> str:
    """Имя иконки для пункта: своё, иначе по типу действия."""
    name = (item.get("icon") or "").strip()
    if exists(name):
        return name
    return BY_TYPE.get(item.get("type", ""), FALLBACK)


def _read(name: str) -> bytes:
    path = os.path.join(ICON_DIR, f"{name}.svg")
    if not os.path.isfile(path):
        path = os.path.join(ICON_DIR, f"{FALLBACK}.svg")
    with open(path, "rb") as f:
        return f.read()


def pixmap(name: str, size: int, color: QColor, width: float = 1.75,
           dpr: float = 1.0) -> QPixmap:
    key = (name, size, color.rgba(), round(width, 2), round(dpr, 2))
    hit = _cache.get(key)
    if hit is not None:
        return hit

    data = _read(name).decode("utf-8")
    data = data.replace('stroke="currentColor"', f'stroke="{color.name()}"')
    data = data.replace('fill="currentColor"', f'fill="{color.name()}"')
    data = re.sub(r'stroke-width="[\d.]+"', f'stroke-width="{width}"', data)

    px = max(1, int(round(size * dpr)))
    pm = QPixmap(px, px)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.SmoothPixmapTransform, True)
    QSvgRenderer(QByteArray(data.encode("utf-8"))).render(p, QRectF(0, 0, px, px))
    p.end()
    pm.setDevicePixelRatio(dpr)

    if color.alpha() < 255:
        # прозрачность даём отдельным проходом: stroke="#rrggbb" альфу не несёт
        out = QPixmap(pm.size())
        out.fill(Qt.transparent)
        out.setDevicePixelRatio(dpr)
        q = QPainter(out)
        q.setOpacity(color.alpha() / 255)
        q.drawPixmap(0, 0, pm)
        q.end()
        pm = out

    _cache[key] = pm
    return pm


def draw(painter: QPainter, name: str, center, size: int, color: QColor,
         width: float = 1.75):
    """Рисует иконку по центру точки `center` в текущей системе координат."""
    dpr = painter.device().devicePixelRatioF() if painter.device() else 1.0
    pm = pixmap(name, size, color, width, max(1.0, dpr * 2))  # x2 — запас на масштаб
    painter.drawPixmap(
        QRectF(center.x() - size / 2, center.y() - size / 2, size, size), pm,
        QRectF(0, 0, pm.width(), pm.height()))
