"""Колесо-дуга: два уровня, управление только колесом, привязка к любому краю.

Зажал Alt — экран притеняется, у края выезжает дуга со списком категорий.
Колесо — выбор, Enter / ПКМ / отпускание Alt — внутрь категории, там тем же
колесом выбираешь кнопку. ПКМ или Esc — на уровень выше.

Про колесо. Событий два: глобальный хук pynput и обычный wheelEvent Qt, когда
курсор оказался над окном. Какой из них доедет — зависит от положения курсора и
настроек Windows, поэтому слушаем оба и гасим дубль по времени: сработавший
первым делает шаг, второй в пределах 60 мс игнорируется.

Геометрия: центр окружности вынесен за край экрана, пункты сидят на дуге с
постоянным угловым шагом. Состояние списка — дробная величина `offset`, её и
анимируем; анимация прерываемая, новая цель подхватывается с текущего места.
"""
import math
import time

from PySide6.QtCore import (
    Qt, QRectF, QPointF, Signal, QEasingCurve, QPropertyAnimation, Property,
)
from PySide6.QtGui import (
    QPainter, QColor, QPen, QRadialGradient, QLinearGradient, QCursor,
    QFontMetricsF, QPainterPath,
)
from PySide6.QtWidgets import QWidget, QApplication

from . import icons
from . import theme as T

# базовые размеры при масштабе 100 %
PANEL_W = 470
ARC_R = 620
ARC_CX_OFF = 450
STEP_DEG = 11.0
MAX_DEG = 46.0

DEDUPE_MS = 0.060      # окно, в котором второй источник прокрутки — дубль

# палитра поверх затемнения
SCRIM = QColor(10, 12, 16, 150)
ON_DARK = QColor(255, 255, 255)
CARD = QColor(255, 255, 255, 247)

TYPE_HINT = {
    "open": "открыть",
    "copy": "копировать",
    "template": "шаблон",
    "doc_copy": "новый документ",
}


def lerp(a, b, t):
    return a + (b - a) * t


class ArcWheel(QWidget):
    activated = Signal(dict)

    def __init__(self, config: dict):
        super().__init__(None)
        self.config = config
        self.groups = []

        self.level = 0
        self.group_index = 0
        self.item_index = 0
        self.pinned = False

        self.scale_ui = 1.0
        self.side = "right"

        self._offset = 0.0
        self._enter = 0.0
        self._dive = 0.0
        self._glass = False
        self._last_scroll = 0.0
        self._opened_at = 0.0

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
            | Qt.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setCursor(Qt.ArrowCursor)

        self._a_offset = self._anim(b"offset", 260)
        self._a_enter = self._anim(b"enter", 220)
        self._a_dive = self._anim(b"dive", 300)
        self.apply_settings(config.get("settings", {}))

    def _anim(self, prop: bytes, ms: int) -> QPropertyAnimation:
        a = QPropertyAnimation(self, prop, self)
        a.setDuration(ms)
        a.setEasingCurve(QEasingCurve.OutCubic)
        return a

    # ---------------- настройки ----------------
    def apply_settings(self, s: dict):
        try:
            self.scale_ui = max(0.7, min(1.8, float(s.get("ui_scale", 1.0))))
        except (TypeError, ValueError):
            self.scale_ui = 1.0
        self.side = "left" if s.get("wheel_side") == "left" else "right"

    @property
    def k(self) -> float:
        return self.scale_ui

    @property
    def sign(self) -> int:
        """+1 — дуга у правого края, -1 — у левого."""
        return 1 if self.side == "right" else -1

    # ---------------- анимируемые свойства ----------------
    def _get_offset(self):
        return self._offset

    def _set_offset(self, v):
        self._offset = float(v)
        self.update()

    offset = Property(float, _get_offset, _set_offset)

    def _get_enter(self):
        return self._enter

    def _set_enter(self, v):
        self._enter = float(v)
        self.update()

    enter = Property(float, _get_enter, _set_enter)

    def _get_dive(self):
        return self._dive

    def _set_dive(self, v):
        self._dive = float(v)
        self.update()

    dive = Property(float, _get_dive, _set_dive)

    # ---------------- данные ----------------
    @property
    def group(self) -> dict:
        if not self.groups:
            return {"name": "Пусто", "items": [], "color": "#5b8cff", "icon": "folder"}
        return self.groups[min(self.group_index, len(self.groups) - 1)]

    @property
    def items(self) -> list:
        return self.group.get("items", [])

    def _row(self, i: int) -> dict:
        if self.level == 0:
            g = self.groups[i]
            n = len(g.get("items", []))
            word = "кнопка" if n == 1 else ("кнопки" if 2 <= n <= 4 else "кнопок")
            return {"icon": g.get("icon") or "folder", "title": g.get("name", ""),
                    "color": g.get("color"), "meta": f"{n} {word}"}
        it = self.items[i]
        return {"icon": icons.resolve(it), "title": it.get("title", ""),
                "color": it.get("color") or self.group.get("color"),
                "meta": it.get("note") or TYPE_HINT.get(it.get("type", ""), "")}

    def _count(self) -> int:
        return len(self.groups) if self.level == 0 else len(self.items)

    def _sel(self) -> int:
        return self.group_index if self.level == 0 else self.item_index

    def _set_sel(self, i: int):
        if self.level == 0:
            self.group_index = i
        else:
            self.item_index = i

    def _settings_group(self) -> dict:
        """Категория «Настройки» живёт в самом колесе, а не в отдельной панели."""
        side = "слева" if self.side == "left" else "справа"
        pct = int(round(self.scale_ui * 100))
        return {
            "id": "__settings", "name": "Настройки", "icon": "settings",
            "color": "#9aa4b2", "system": True,
            "items": [
                {"id": "__editor", "type": "app", "action": "editor",
                 "title": "Кнопки и параметры", "icon": "sliders-horizontal",
                 "note": "добавить или изменить кнопки"},
                {"id": "__presets", "type": "app", "action": "presets",
                 "title": "Наборы кнопок", "icon": "package",
                 "note": "заготовки, импорт и экспорт"},
                {"id": "__search", "type": "app", "action": "search",
                 "title": "Быстрый поиск", "icon": "search",
                 "note": "то же, что Ctrl+Space"},
                {"id": "__side", "type": "app", "action": "side",
                 "title": f"Перенести на другой край", "icon": "arrow-right",
                 "note": f"сейчас {side} — ручку можно и перетащить"},
                {"id": "__up", "type": "app", "action": "scale_up",
                 "title": "Крупнее", "icon": "plus", "note": f"сейчас {pct} %"},
                {"id": "__down", "type": "app", "action": "scale_down",
                 "title": "Мельче", "icon": "minus", "note": f"сейчас {pct} %"},
                {"id": "__quit", "type": "app", "action": "quit",
                 "title": "Выйти из QuickDeck", "icon": "x", "note": "закрыть программу"},
            ],
        }

    def reload(self, config: dict):
        self.config = config
        self.apply_settings(config.get("settings", {}))
        groups = [g for g in config.get("groups", []) if g.get("items")]
        groups = list(groups or config.get("groups", []))
        groups.append(self._settings_group())
        self.groups = groups
        self.group_index = min(self.group_index, max(0, len(self.groups) - 1))
        self.item_index = min(self.item_index, max(0, len(self.items) - 1))

    # ---------------- показ ----------------
    def popup(self, group_id: str = "", item_index: int = -1, pinned: bool = False):
        self.reload(self.config)
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        self.setGeometry(screen.geometry())          # на весь экран — ради затемнения

        self.level = 0
        self.item_index = 0
        self.pinned = pinned
        if group_id:
            for i, g in enumerate(self.groups):
                if g.get("id") == group_id:
                    self.group_index = i
                    break
        if item_index >= 0:
            self.item_index = item_index
            self.level = 1
            self._dive = 1.0
        self._offset = float(self.item_index if self.level else self.group_index)
        self._opened_at = time.monotonic()
        if not self.level:
            self._dive = 0.0

        self.show()
        self.raise_()
        self.activateWindow()
        self._run(self._a_enter, 0.0, 1.0)

    def dismiss(self):
        self.pinned = False
        self.hide()

    def _run(self, anim: QPropertyAnimation, start, end):
        anim.stop()
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.start()

    # ---------------- навигация ----------------
    def scroll_step(self, delta: int):
        """Шаг от любого источника прокрутки, с защитой от дубля."""
        now = time.monotonic()
        if now - self._last_scroll < DEDUPE_MS:
            return
        self._last_scroll = now
        self.step(delta)

    def step(self, delta: int):
        n = self._count()
        if not n:
            return
        self._set_sel(max(0, min(n - 1, self._sel() + delta)))
        self._run(self._a_offset, self._offset, float(self._sel()))

    def enter_level(self):
        if self.level != 0 or not self.groups or not self.items:
            return
        self.level = 1
        self.item_index = 0
        self._offset = 0.0
        self._run(self._a_dive, self._dive, 1.0)

    def back(self):
        if self.level == 1:
            self.level = 0
            self._offset = float(self.group_index)
            self._run(self._a_dive, self._dive, 0.0)
        else:
            self.dismiss()

    def confirm(self):
        if self.level == 0:
            self.enter_level()
            return
        items = self.items
        if items and 0 <= self.item_index < len(items):
            item = items[self.item_index]
            self.dismiss()
            self.activated.emit(item)
        else:
            self.dismiss()

    def modifier_released(self):
        # активация окна при зажатом Alt иногда даёт ложное «отпустили» —
        # первые 350 мс после открытия такое событие игнорируем
        if self.pinned or (time.monotonic() - self._opened_at) < 0.35:
            return
        if self.level == 0:
            if self.items:
                self.pinned = True
                self.enter_level()
            else:
                self.dismiss()
        else:
            self.confirm()

    # ---------------- ввод ----------------
    def keyPressEvent(self, e):
        k = e.key()
        fwd = Qt.Key_Right if self.side == "right" else Qt.Key_Left
        bwd = Qt.Key_Left if self.side == "right" else Qt.Key_Right
        if k == Qt.Key_Escape:
            self.back()
        elif k in (Qt.Key_Down,):
            self.step(1)
        elif k in (Qt.Key_Up,):
            self.step(-1)
        elif k == bwd or k == Qt.Key_Backspace:
            self.back()
        elif k == fwd or k in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.confirm()
        elif Qt.Key_1 <= k <= Qt.Key_9:
            idx = k - Qt.Key_1
            if idx < self._count():
                self._set_sel(idx)
                self._run(self._a_offset, self._offset, float(idx))
                self.confirm()
        else:
            super().keyPressEvent(e)

    def wheelEvent(self, e):
        self.scroll_step(1 if e.angleDelta().y() < 0 else -1)
        e.accept()

    def mouseReleaseEvent(self, e):
        # правая кнопка всегда «на шаг назад», левая — всегда «вперёд».
        # Разное поведение по уровням путало: одна и та же кнопка то входила,
        # то выходила.
        if e.button() == Qt.RightButton:
            self.back()
        elif e.button() == Qt.LeftButton:
            self.confirm()

    # ---------------- геометрия ----------------
    def _focus_x(self) -> float:
        """Край, к которому прижата дуга."""
        return self.width() if self.side == "right" else 0.0

    def _place(self, i: int):
        k = self.k
        cx = self._focus_x() + self.sign * ARC_CX_OFF * k
        cy = self.height() / 2
        deg = (i - self._offset) * STEP_DEG
        rad = math.radians(deg)
        x = cx - self.sign * ARC_R * k * math.cos(rad)
        return x, cy + ARC_R * k * math.sin(rad), deg

    # ---------------- отрисовка ----------------
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.TextAntialiasing, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)

        w, h = self.width(), self.height()
        t = max(0.0, min(1.0, self._enter))

        # затемнение всего экрана — сразу видно, что режим выбора включён
        p.setOpacity(t)
        scrim = QRadialGradient(QPointF(self._focus_x(), h / 2), max(w, h) * 0.9)
        scrim.setColorAt(0.0, QColor(14, 16, 22, int(SCRIM.alpha() * 0.78)))
        scrim.setColorAt(1.0, QColor(6, 7, 10, int(SCRIM.alpha() * 1.25)))
        p.fillRect(self.rect(), scrim)

        p.translate(-self.sign * (1 - t) * 48, 0)

        self._paint_guide(p, w, h)

        n = self._count()
        if not n:
            p.setPen(T.alpha(ON_DARK, 150))
            p.setFont(T.font(12 * self.k))
            p.drawText(self.rect(), Qt.AlignCenter, "Здесь пока ничего нет")
            return

        d = max(0.0, min(1.0, self._dive))
        shift = -self.sign * 34 * self.k * (d if self.level == 1 else -(1 - d))
        p.save()
        p.translate(shift, 0)
        p.setOpacity(t * (d if self.level == 1 else 1.0))
        for i in sorted(range(n), key=lambda i: -abs(i - self._offset)):
            self._draw_row(p, i)
        p.restore()

        # нижние пункты уходят под мягкую растушёвку, чтобы не спорить с подсказками
        p.setOpacity(t)
        fade = QLinearGradient(0, h - 150 * self.k, 0, h)
        fade.setColorAt(0.0, QColor(8, 9, 13, 0))
        fade.setColorAt(1.0, QColor(8, 9, 13, 205))
        p.fillRect(QRectF(0, h - 150 * self.k, w, 150 * self.k), fade)

        self._paint_chrome(p, w, h)

    def _paint_guide(self, p: QPainter, w: int, h: int):
        cx = self._focus_x() + self.sign * ARC_CX_OFF * self.k
        r = (ARC_R - 72) * self.k
        p.setPen(QPen(T.alpha(ON_DARK, 26), 1))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(cx, h / 2), r, r)

    def _draw_row(self, p: QPainter, i: int):
        x, y, deg = self._place(i)
        if abs(deg) > MAX_DEG:
            return

        k = self.k
        s = self.sign
        row = self._row(i)
        near = max(0.0, 1.0 - abs(i - self._offset))
        fade = max(0.0, 1.0 - (abs(deg) / MAX_DEG) ** 1.35)
        scale = lerp(0.9, 1.0, near) * k
        accent = QColor(row.get("color") or "#5b8cff")
        chosen = near > 0.5

        p.save()
        p.translate(x, y)
        p.rotate(-deg * 0.55 * s)
        p.scale(scale, scale)
        p.setOpacity(p.opacity() * max(0.0, min(1.0, fade)))

        cap = QRectF(-34, -28, 68, 56)
        if chosen:
            p.setPen(Qt.NoPen)
            p.setBrush(T.alpha(accent, int(70 * near)))
            p.drawRoundedRect(cap.adjusted(-7, -7, 7, 7), 25, 25)   # 18 + 7
            p.setBrush(CARD)
            p.setPen(QPen(T.alpha(accent, 235), 1.5))
        else:
            p.setBrush(T.alpha(ON_DARK, 18))
            p.setPen(QPen(T.alpha(ON_DARK, 30), 1))
        p.drawRoundedRect(cap, 18, 18)

        icon_color = accent if chosen else T.alpha(ON_DARK, int(lerp(110, 190, near)))
        icons.draw(p, row["icon"], QPointF(0, 0), 23, icon_color,
                   1.75 if chosen else 1.6)

        title = row["title"]
        f = T.font(13 if chosen else 12.5, 600 if chosen else 500, -0.1 if chosen else 0)
        p.setFont(f)
        fm = QFontMetricsF(f)
        title = fm.elidedText(title, Qt.ElideRight, 230)
        tw = fm.horizontalAdvance(title)

        if chosen:
            pill = QRectF(0, -18, tw + 34, 36)
            pill.moveLeft(52 if s < 0 else -52 - tw - 34)
            p.setBrush(CARD)
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(pill, 18, 18)
            p.setPen(T.TEXT)
            p.drawText(pill, Qt.AlignCenter, title)
        else:
            box = QRectF(0, -15, tw + 16, 30)
            box.moveLeft(52 if s < 0 else -52 - tw - 16)
            p.setPen(T.alpha(ON_DARK, int(lerp(95, 175, near))))
            p.drawText(box, (Qt.AlignLeft if s < 0 else Qt.AlignRight) | Qt.AlignVCenter,
                       title)

        p.restore()

    def _paint_chrome(self, p: QPainter, w: int, h: int):
        k, s = self.k, self.sign
        right = s > 0
        margin = 34 * k
        align = Qt.AlignRight if right else Qt.AlignLeft

        # риска уровня выбора у самого края
        p.setPen(Qt.NoPen)
        p.setBrush(T.alpha(ON_DARK, 120))
        bar = QRectF(0, h / 2 - 8 * k, 4, 16 * k)
        bar.moveLeft(w - 22 if right else 18)
        p.drawRoundedRect(bar, 2, 2)

        crumb = "Категории" if self.level == 0 else self.group.get("name", "")
        f = T.font(10.5 * k, 600, 0.3)
        p.setFont(f)
        fm = QFontMetricsF(f)
        pad = (30 if self.level == 1 else 20) * k
        tw = fm.horizontalAdvance(crumb)
        chip = QRectF(0, 28 * k, tw + pad, 32 * k)
        chip.moveLeft(w - margin - chip.width() if right else margin)
        p.setBrush(T.alpha(ON_DARK, 26))
        p.setPen(QPen(T.alpha(ON_DARK, 40), 1))
        p.drawRoundedRect(chip, chip.height() / 2, chip.height() / 2)
        p.setPen(ON_DARK)
        p.drawText(chip.adjusted(13 * k if self.level == 1 else 0, 0, 0, 0),
                   Qt.AlignCenter, crumb)
        if self.level == 1:
            path = QPainterPath()
            bx, by = chip.x() + 14 * k, chip.center().y()
            path.moveTo(bx + 3, by - 4)
            path.lineTo(bx - 1, by)
            path.lineTo(bx + 3, by + 4)
            p.setPen(QPen(T.alpha(ON_DARK, 160), 1.5, Qt.SolidLine, Qt.RoundCap,
                          Qt.RoundJoin))
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)

        n = self._count()
        if n:
            row = self._row(self._sel())
            p.setFont(T.font(10 * k, 500))
            p.setPen(T.alpha(ON_DARK, 130))
            box = QRectF(margin if not right else 0, h - 86 * k, w - margin, 20 * k)
            p.drawText(box, align | Qt.AlignVCenter, row.get("meta", ""))

        hint = ("колесо — категория     ЛКМ или Enter — открыть     ПКМ — закрыть"
                if self.level == 0 else
                "колесо — выбор     ЛКМ или Enter — выполнить     ПКМ — назад")
        p.setFont(T.font(9.5 * k, 500, 0.2))
        p.setPen(T.alpha(ON_DARK, 95))
        box = QRectF(margin if not right else 0, h - 62 * k, w - margin, 20 * k)
        p.drawText(box, align | Qt.AlignVCenter, hint)
