"""Ручка у края экрана — всё, что осталось от боковой панели.

Она отвечает ровно за две вещи: показывает, к какому краю привязан виджет,
и позволяет его туда перетащить. Клик открывает колесо, дальше вся работа
идёт там. Ничего не дублирует и почти не занимает места.
"""
from PySide6.QtCore import Qt, Signal, QRectF, QPointF, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QPainter, QColor, QPen, QCursor
from PySide6.QtWidgets import QWidget, QApplication

from . import theme as T

W, H = 22, 74          # сама ручка
PAD = 10               # запас вокруг под свечение и тень


class EdgeHandle(QWidget):
    clicked = Signal()
    moved = Signal(str, float)      # сторона и доля высоты экрана

    def __init__(self, config: dict):
        super().__init__(None)
        self.config = config
        s = config.get("settings", {})
        self.side = "left" if s.get("wheel_side") == "left" else "right"
        self.pos_frac = float(s.get("handle_pos", 0.5))

        self._hover = 0.0
        self._drag_from = None
        self._moved = False

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("QuickDeck — клик открывает колесо, перетаскиванием меняется край")
        self.resize(W + PAD * 2, H + PAD * 2)

        self._a_hover = QPropertyAnimation(self, b"hover", self)
        self._a_hover.setDuration(140)
        self._a_hover.setEasingCurve(QEasingCurve.OutCubic)

    # ---------------- свойства ----------------
    def _get_hover(self):
        return self._hover

    def _set_hover(self, v):
        self._hover = float(v)
        self.update()

    hover = Property(float, _get_hover, _set_hover)

    def accent(self) -> QColor:
        return QColor(self.config.get("settings", {}).get("accent") or "#5b8cff")

    # ---------------- размещение ----------------
    def reload(self, config: dict):
        self.config = config
        s = config.get("settings", {})
        self.side = "left" if s.get("wheel_side") == "left" else "right"
        self.pos_frac = float(s.get("handle_pos", 0.5))
        self.place()

    def place(self):
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        geo = screen.availableGeometry()
        x = geo.right() - self.width() + PAD + 1 if self.side == "right" else geo.left() - PAD
        y = geo.top() + int(geo.height() * self.pos_frac) - self.height() // 2
        y = max(geo.top(), min(geo.bottom() - self.height(), y))
        self.move(x, y)

    # ---------------- мышь ----------------
    def enterEvent(self, e):
        self._run_hover(1.0)

    def leaveEvent(self, e):
        self._run_hover(0.0)

    def _run_hover(self, to):
        self._a_hover.stop()
        self._a_hover.setStartValue(self._hover)
        self._a_hover.setEndValue(to)
        self._a_hover.start()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_from = e.globalPosition().toPoint() - self.pos()
            self._moved = False

    def mouseMoveEvent(self, e):
        if self._drag_from is None:
            return
        p = e.globalPosition().toPoint() - self._drag_from
        if not self._moved and (abs(p.x() - self.x()) + abs(p.y() - self.y())) > 4:
            self._moved = True
        self.move(p)

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        if self._drag_from is not None and self._moved:
            self._snap()
        elif self._drag_from is not None:
            self.clicked.emit()
        self._drag_from = None

    def _snap(self):
        """После перетаскивания прилипаем к ближайшему краю."""
        screen = QApplication.screenAt(self.geometry().center()) or QApplication.primaryScreen()
        geo = screen.availableGeometry()
        center = self.geometry().center()
        self.side = "right" if center.x() > geo.center().x() else "left"
        self.pos_frac = max(0.06, min(0.94, (center.y() - geo.top()) / max(1, geo.height())))
        self.place()
        self.moved.emit(self.side, self.pos_frac)

    # ---------------- отрисовка ----------------
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        hv = self._hover
        body = QRectF(PAD, PAD, W, H)
        if self.side == "right":
            body.translate(-PAD * hv * 0.5, 0)
        else:
            body.translate(PAD * hv * 0.5, 0)

        # мягкое свечение под ручкой, чтобы читалась на любом фоне
        glow = QColor(0, 0, 0, int(26 + 20 * hv))
        p.setPen(Qt.NoPen)
        p.setBrush(glow)
        p.drawRoundedRect(body.adjusted(-4, -3, 4, 5), 15, 15)

        p.setBrush(QColor(22, 24, 30, int(120 + 80 * hv)))
        p.setPen(QPen(QColor(255, 255, 255, int(45 + 45 * hv)), 1))
        p.drawRoundedRect(body, 11, 11)

        # три точки дугой — намёк на колесо
        a = self.accent()
        cx = body.center().x()
        cy = body.center().y()
        bow = 3.0 + 1.5 * hv
        s = 1 if self.side == "right" else -1
        # дуга смотрит так же, как само колесо: середина отходит от края,
        # края подтянуты к нему — иначе значок спорит с тем, что откроется
        for dy in (-13.0, 0.0, 13.0):
            r = 2.6 if dy == 0 else 2.0
            off = (bow if dy == 0 else 0.0) * s
            c = QColor(a) if dy == 0 else QColor(255, 255, 255)
            c.setAlpha(255 if dy == 0 else int(120 + 70 * hv))
            p.setBrush(c)
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(cx - off, cy + dy), r, r)

    def showEvent(self, e):
        super().showEvent(e)
        self.place()
