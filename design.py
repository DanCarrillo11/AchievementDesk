"""Dark companion design for UniversalSaveEditor, with locally painted controls."""
import math
from PySide6.QtCore import Qt, QSize, QRectF, QPointF, QPropertyAnimation, Property
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap, QPalette, QPolygonF
from PySide6.QtWidgets import QAbstractButton, QApplication, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

STYLE = """
QWidget { font-family: 'Segoe UI'; font-size: 13px; color: #f5f5f7; }
QMainWindow, QWidget#Workspace, QWidget#ScrollContent, QWidget#LibraryPage { background: #171719; }
QFrame#AppHeader { background: #242426; border-bottom: 1px solid #3a3a3f; }
QWidget#Sidebar { background: #1d1d1f; border-right: 1px solid #3a3a3f; }
QWidget#Hero { background: #242426; border: 1px solid #3a3a3f; border-radius: 16px; }
QWidget#HeroCopy, QWidget#HeroStats { background: transparent; border: none; }
QLabel { background: transparent; border: none; }
QLabel#Brand { font-size: 22px; font-weight: 600; }
QLabel#BrandSub { color: #b6b6be; font-size: 12px; }
QLabel#LibraryTitle { font-size: 23px; font-weight: 600; letter-spacing: -0.4px; }
QLabel#Eyebrow { color: #9999a5; font-size: 11px; font-weight: 600; }
QLabel#Title { font-size: 27px; font-weight: 600; letter-spacing: -0.5px; }
QLabel#Subtitle { color: #b6b6be; font-size: 12px; }
QLabel#Small { color: #9999a5; font-size: 11px; }
QLabel#Metric { font-size: 14px; font-weight: 600; }
QLabel#Percent { color: #93c5ff; font-size: 34px; font-weight: 400; }
QLabel#SectionTitle { font-size: 17px; font-weight: 600; }
QLabel#Count { color: #b6b6be; background: #303034; border-radius: 6px; padding: 3px 8px; font-size: 11px; }
QLabel#Avatar { background: #193856; color: #93c5ff; border-radius: 8px; font-weight: 600; }
QFrame#Rule { background: #3a3a3f; max-height: 1px; border: none; }
QLineEdit { background: #303034; border: 1px solid #3a3a3f; border-radius: 10px; padding: 10px; selection-background-color: #087beb; selection-color: white; }
QLineEdit:focus { border: 1px solid #087beb; }
QLineEdit#AchievementSearch { background: #303034; }
QListWidget { border: none; background: transparent; outline: 0; }
QListWidget::item { border: none; }
QPushButton, QToolButton#MenuButton { border: 1px solid #3a3a3f; border-radius: 10px; background: #242426; padding: 10px 15px; font-weight: 600; }
QPushButton:hover, QToolButton#MenuButton:hover { background: #353538; border-color: #55555d; }
QPushButton:pressed { background: #303034; }
QPushButton:disabled, QToolButton#MenuButton:disabled { color: #767682; border-color: #28282c; background: #28282c; }
QPushButton#Primary { color: white; background: #087beb; border-color: #087beb; font-weight: 600; }
QPushButton#Primary:hover { background: #1989f8; border-color: #1989f8; }
QPushButton#Primary:disabled { color: #767682; background: #28282c; border-color: #28282c; }
QPushButton#SidebarButton, QToolButton#SidebarButton { text-align: left; border: none; background: transparent; color: #b6b6be; padding: 10px 8px; border-radius: 10px; }
QPushButton#SidebarButton:hover, QToolButton#SidebarButton:hover { background: #353538; color: #f5f5f7; }
QToolButton { background: transparent; border: none; border-radius: 4px; padding: 6px; }
QToolButton:hover { background: #353538; }
QToolButton::menu-indicator { image: none; width: 0px; height: 0px; }
QWidget#Segments { background: transparent; }
QPushButton#Segment { border: 1px solid transparent; background: #242426; padding: 9px 13px; color: #b6b6be; border-radius: 9px; font-size: 12px; }
QPushButton#Segment:checked { border-color: #193856; background: #193856; color: #93c5ff; }
QPushButton#Segment:hover { color: #f5f5f7; background: #353538; }
QPushButton#LetterButton { background: transparent; color: #b6b6be; border: none; border-radius: 5px; padding: 0; font-size: 11px; }
QPushButton#LetterButton:checked { background: #193856; color: #93c5ff; }
QPushButton#LetterButton:hover { background: #303034; color: #f5f5f7; }
QPushButton#LibraryBrowse:checked { background: #193856; color: #93c5ff; border-color: #193856; }
QListWidget#CompactGameList { background: transparent; border: 1px solid #3a3a3f; border-radius: 10px; padding: 5px; }
QProgressBar { background: #3a3a3f; border: none; border-radius: 3px; max-height: 5px; min-height: 5px; }
QProgressBar::chunk { background: #087beb; border-radius: 3px; }
QScrollArea { background: transparent; border: none; }
QWidget#Rows { background: transparent; border: none; }
QFrame#AchievementRow { background: #242426; border: 1px solid #3a3a3f; border-radius: 12px; }
QFrame#AchievementRow:hover { background: #303034; border-color: #55555d; }
QFrame#AchievementRow[selected="true"] { background: #193856; border: 1px solid #087beb; }
QFrame#AchievementRow[pending="true"] { border-left: 3px solid #93c5ff; }
QLabel#AchievementName { font-size: 14px; font-weight: 600; }
QLabel#AchievementDescription { color: #b6b6be; font-size: 12px; }
QLabel#AchievementMeta { color: #9999a5; font-size: 10px; }
QLabel#Pending { color: #93c5ff; font-size: 10px; }
QWidget#PendingBar { background: #242426; border: 1px solid #3a3a3f; border-radius: 16px; }
QMenu { background: #242426; border: 1px solid #3a3a3f; padding: 7px; border-radius: 10px; }
QMenu::item { padding: 9px 30px 9px 12px; border-radius: 3px; }
QMenu::item:selected { color: #93c5ff; background: #193856; }
QMenu::item:disabled { color: #767682; }
QMenu::separator { height: 1px; background: #3a3a3f; margin: 6px; }
QDialog { background: #171719; }
QTextEdit { border: 1px solid #3a3a3f; border-radius: 12px; padding: 12px; background: #242426; }
QTreeWidget { border: 1px solid #3a3a3f; border-radius: 10px; padding: 5px; background: #242426; alternate-background-color: #303034; }
QTreeWidget::item { padding: 9px 5px; }
QTreeWidget::item:selected { background: #193856; color: #93c5ff; }
QHeaderView::section { color: #b6b6be; background: #242426; border: none; border-bottom: 1px solid #3a3a3f; padding: 8px; }
QComboBox { background: #303034; border: 1px solid #3a3a3f; border-radius: 8px; padding: 8px 24px 8px 10px; }
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView { color: #f5f5f7; background: #242426; selection-background-color: #193856; selection-color: #93c5ff; }
QCheckBox { spacing: 10px; }
QToolTip { color: #f5f5f7; background: #242426; border: 1px solid #55555d; padding: 6px; }
QScrollBar:vertical { background: transparent; width: 7px; margin: 4px 0; }
QScrollBar::handle:vertical { background: #55555d; min-height: 35px; border-radius: 3px; }
QScrollBar::handle:vertical:hover { background: #767682; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
"""


def apply_dark_palette(app):
    palette = QPalette()
    for role, color in ((QPalette.ColorRole.Window, "#171719"), (QPalette.ColorRole.WindowText, "#f5f5f7"),
                        (QPalette.ColorRole.Base, "#242426"), (QPalette.ColorRole.AlternateBase, "#303034"),
                        (QPalette.ColorRole.Text, "#f5f5f7"), (QPalette.ColorRole.Button, "#242426"),
                        (QPalette.ColorRole.ButtonText, "#f5f5f7"), (QPalette.ColorRole.Highlight, "#087beb"),
                        (QPalette.ColorRole.HighlightedText, "#ffffff"), (QPalette.ColorRole.PlaceholderText, "#7f8998")):
        palette.setColor(role, QColor(color))
    app.setPalette(palette)


def icon(kind, color="#9ba5b4", size=20):
    pix = QPixmap(size * 2, size * 2)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(2, 2)
    painter.setPen(QPen(QColor(color), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    if kind == "search":
        painter.drawEllipse(QRectF(3, 3, 9, 9))
        painter.drawLine(11, 11, 16, 16)
    elif kind == "settings":
        painter.drawEllipse(QRectF(5, 5, 10, 10))
        painter.drawEllipse(QRectF(8, 8, 4, 4))
        for n in range(8):
            angle = n * math.pi / 4
            painter.drawLine(round(10 + math.cos(angle) * 6), round(10 + math.sin(angle) * 6),
                             round(10 + math.cos(angle) * 8), round(10 + math.sin(angle) * 8))
    elif kind == "more":
        painter.setBrush(QColor(color))
        for x in (4, 10, 16):
            painter.drawEllipse(QRectF(x - 1, 9, 2, 2))
    elif kind == "library":
        for x, height in ((3, 12), (8, 15), (13, 10)):
            painter.drawRoundedRect(QRectF(x, 18 - height, 3, height), .5, .5)
    elif kind in ("star", "star_filled"):
        points = [QPointF(10 + math.cos(-math.pi / 2 + n * math.pi / 5) * (8 if n % 2 == 0 else 3.6),
                          10 + math.sin(-math.pi / 2 + n * math.pi / 5) * (8 if n % 2 == 0 else 3.6)) for n in range(10)]
        if kind == "star_filled":
            painter.setBrush(QColor(color))
        painter.drawPolygon(QPolygonF(points))
    elif kind == "down":
        painter.drawLine(6, 8, 10, 12)
        painter.drawLine(10, 12, 14, 8)
    elif kind in ("left", "right"):
        direction = 1 if kind == "right" else -1
        painter.drawLine(10 - 3 * direction, 5, 10 + 2 * direction, 10)
        painter.drawLine(10 + 2 * direction, 10, 10 - 3 * direction, 15)
    elif kind == "trophy":
        painter.drawRoundedRect(QRectF(6, 3, 8, 10), 3, 3)
        painter.drawArc(QRectF(2, 3, 6, 7), 90 * 16, 180 * 16)
        painter.drawArc(QRectF(12, 3, 6, 7), -90 * 16, 180 * 16)
        painter.drawLine(10, 13, 10, 17)
        painter.drawLine(7, 17, 13, 17)
    painter.end()
    pix.setDevicePixelRatio(2)
    return QIcon(pix)


class AchievementMark(QFrame):
    """Status ornament, deliberately distinct from downloaded achievement artwork."""
    def __init__(self, size=36, hero=False):
        super().__init__()
        self.setFixedSize(size, size)
        self.unlocked, self.pending, self.hero = False, False, hero
        self.image = QPixmap()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.image.isNull():
            p.drawPixmap(self.rect(), self.image)
            return
        p.scale(self.width() / 48, self.height() / 48)
        active = self.unlocked or self.pending or self.hero
        p.setPen(QPen(QColor("#38516c" if active else "#55555d"), .8))
        p.setBrush(QColor("#193856" if active else "#303034"))
        p.drawRoundedRect(QRectF(1, 1, 46, 46), 7, 7)
        p.setPen(QPen(QColor("#66d49a" if self.unlocked else "#93c5ff" if active else "#9999a5"), 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        if self.hero:
            p.drawPolygon(QPolygonF([
                QPointF(x, y)
                for x, y in ((24, 7), (38, 16), (38, 32), (24, 41), (10, 32), (10, 16))]))
            p.drawLine(17, 25, 22, 30)
            p.drawLine(22, 30, 31, 18)
        elif self.unlocked:
            p.drawLine(16, 24, 22, 30)
            p.drawLine(22, 30, 33, 18)
        else:
            p.drawRoundedRect(QRectF(17, 21, 14, 12), 2, 2)
            p.drawArc(QRectF(19, 13, 10, 15), 0, 180 * 16)


class Switch(QAbstractButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(44, 27)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._offset = 0.0
        self.animation = QPropertyAnimation(self, b"offset", self)
        self.animation.setDuration(140)
        self.toggled.connect(self.animate)

    def sizeHint(self):
        return QSize(44, 27)

    def get_offset(self):
        return self._offset

    def set_offset(self, value):
        self._offset = value
        self.update()

    offset = Property(float, get_offset, set_offset)

    def animate(self, checked):
        self.animation.stop()
        if self.property("reduce_motion"):
            self.set_offset(1.0 if checked else 0.0)
            return
        self.animation.setStartValue(self._offset)
        self.animation.setEndValue(1.0 if checked else 0.0)
        self.animation.start()

    def set_saved(self, checked):
        self.animation.stop()
        self.blockSignals(True)
        self.setChecked(checked)
        self.blockSignals(False)
        self._offset = 1.0 if checked else 0.0
        self.update()

    def paintEvent(self, _):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(1 if self.isEnabled() else .45)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#087beb" if self.isChecked() else "#55555d"))
        painter.drawRoundedRect(QRectF(1, 3, 42, 22), 6, 6)
        painter.setBrush(QColor("#f5f5f7" if self.isChecked() else "#b6b6be"))
        painter.drawRoundedRect(QRectF(4 + 18 * self._offset, 6, 18, 16), 3, 3)
        if self.hasFocus():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor("#93c5ff"), 1.5))
            painter.drawRoundedRect(QRectF(.8, .8, 42.4, 25.4), 6, 6)


class AchievementRow(QFrame):
    def __init__(self, record, on_toggle, on_select):
        super().__init__()
        self.setObjectName("AchievementRow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._surface = None
        self.key, self.on_select = record["key"], on_select
        self.setProperty("selected", False)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(17, 15, 20, 15)
        layout.setSpacing(16)
        self.mark = AchievementMark()
        layout.addWidget(self.mark, 0, Qt.AlignmentFlag.AlignVCenter)
        text = QVBoxLayout()
        text.setSpacing(5)
        self.title = QLabel()
        self.title.setObjectName("AchievementName")
        self.title.setWordWrap(True)
        self.description = QLabel()
        self.description.setObjectName("AchievementDescription")
        self.description.setWordWrap(True)
        self.meta = QLabel()
        self.meta.setObjectName("AchievementMeta")
        for label in (self.title, self.description, self.meta):
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            text.addWidget(label)
        layout.addLayout(text, 1)
        self.switch = Switch()
        self.switch.clicked.connect(lambda value: on_toggle(self.key, value))
        layout.addWidget(self.switch, 0, Qt.AlignmentFlag.AlignVCenter)
        self.update_record(record)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        selected = bool(self.property("selected"))
        painter.setBrush(QColor("#193856" if selected else "#303034" if self.underMouse() else "#242426"))
        painter.setPen(QPen(QColor("#087beb" if selected else "#55555d" if self.underMouse() else "#3a3a3f"), 1))
        painter.drawRoundedRect(QRectF(.5, .5, self.width() - 1, self.height() - 1), 12, 12)
        if self.property("pending"):
            painter.setPen(QPen(QColor("#93c5ff"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(2, 13, 2, self.height() - 13)

    def enterEvent(self, event):
        self.update_surface()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update_surface()
        super().leaveEvent(event)

    def update_surface(self):
        color = "#193856" if self.property("selected") else "#303034" if self.underMouse() else "#242426"
        if self._surface != color:
            self._surface = color
            # Child labels use the same backing surface when Windows composites them.
            self.setStyleSheet(f"background-color:{color};")
        self.update()

    def update_record(self, record):
        self.title.setText(record["name"])
        self.description.setText(record["description"])
        if self.switch.isChecked() != record["draft"]:
            self.switch.set_saved(record["draft"])
        self.switch.setAccessibleName(f"Unlocked: {record['name']}")
        state = "Unlocked" if record["actual"] else "Locked"
        pending = record["draft"] != record["actual"]
        self.mark.unlocked, self.mark.pending = record["actual"], pending
        self.mark.image = QPixmap(record.get("icon_path") or "")
        self.mark.update()
        self.setProperty("pending", pending)
        text = f"{'Unlock' if record['draft'] else 'Lock'} pending · currently {state.lower()}" if pending else record["date"] if record["actual"] else ""
        if record.get("rarity") is not None:
            text += ("  ·  " if text else "") + f"{record['rarity']:.1f}% of players"
        if record.get("restriction"):
            text += ("  ·  " if text else "") + record["restriction"]
        self.meta.setObjectName("Pending" if pending else "AchievementMeta")
        self.meta.setText(text)
        self.meta.setVisible(bool(text))
        self.meta.style().unpolish(self.meta)
        self.meta.style().polish(self.meta)
        self.update_surface()
        self.setToolTip(f"{record['key']}\nSaved state: {state}")
        self.switch.setAccessibleDescription(text or state)

    def set_preferences(self, compact, reduce_motion):
        margins = self.layout().contentsMargins()
        height = 10 if compact else 15
        if margins.top() != height:
            self.layout().setContentsMargins(17, height, 20, height)
        self.switch.setProperty("reduce_motion", reduce_motion)

    def mousePressEvent(self, event):
        self.on_select(self.key, bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier))
        super().mousePressEvent(event)

    def set_selected(self, selected):
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update_surface()


def label(text, name=None, wrap=False):
    result = QLabel(text)
    result.setTextFormat(Qt.TextFormat.PlainText)
    if name:
        result.setObjectName(name)
    if name == "Count":
        result.setFixedHeight(24)
        result.setAlignment(Qt.AlignmentFlag.AlignCenter)
    result.setWordWrap(wrap)
    return result


def button(text, callback, primary=False):
    result = QPushButton(text)
    if primary:
        result.setObjectName("Primary")
    result.setCursor(Qt.CursorShape.PointingHandCursor)
    result.clicked.connect(callback)
    return result
