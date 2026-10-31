"""Embedded alphabetical game library and account-scoped activity history."""
from datetime import datetime
import math
import string
import unicodedata
from PySide6.QtCore import Qt, QSize, QRectF, QTimer, QPoint
from PySide6.QtGui import QColor, QFont, QPainter, QKeySequence, QShortcut
from PySide6.QtWidgets import (QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QComboBox, QListWidget,
    QListWidgetItem, QStyledItemDelegate, QStyle, QPushButton, QTreeWidget, QTreeWidgetItem,
    QTextEdit, QFileDialog, QButtonGroup)
from design import label, button, icon, draw_match_text
from experience import page_numbers
from compatibility import FILTERS as COMPATIBILITY_FILTERS, status as compatibility_status, details as compatibility_details


def letter_bucket(name):
    normalized = unicodedata.normalize("NFKD", name.replace("™", "").replace("®", "").replace("©", "").strip())
    for character in normalized:
        if character.isalnum():
            letter = character.upper()
            return letter if letter in string.ascii_uppercase else "#"
    return "#"


class GameRowDelegate(QStyledItemDelegate):
    def __init__(self, desk, parent):
        super().__init__(parent)
        self.desk = desk

    def sizeHint(self, option, index):
        return QSize(max(100, self.parent().gridSize().width() - 4), 36)

    def paint(self, painter, option, index):
        game = index.data(Qt.ItemDataRole.UserRole)
        if not game:
            return
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = option.rect.adjusted(2, 1, -4, -1)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hover = bool(option.state & QStyle.StateFlag.State_MouseOver)
        painter.setPen(Qt.PenStyle.NoPen)
        if selected or hover:
            painter.setBrush(QColor("#193856" if selected else "#303034"))
            painter.drawRoundedRect(rect, 6, 6)
        tile = QRectF(rect.x() + 10, rect.y() + 5, 24, 24)
        pixmap = self.desk.game_icon_pixmaps.get(game.app_id)
        if pixmap and not pixmap.isNull():
            painter.drawPixmap(tile, pixmap, QRectF(0, 0, pixmap.width(), pixmap.height()))
        else:
            painter.setBrush(QColor("#303034"))
            painter.drawRoundedRect(tile, 3, 3)
            painter.setPen(QColor("#9999a5"))
            painter.setFont(QFont("Segoe UI", 8))
            painter.drawText(tile, Qt.AlignmentFlag.AlignCenter, game.name[:1].upper())
        favorite = game.app_id in self.desk.profile()["favorites"]
        available = rect.width() - 70 - (24 if favorite else 0)
        painter.setFont(QFont("Segoe UI", 10))
        painter.setPen(QColor("#f5f5f7" if selected else "#b6b6be"))
        name = painter.fontMetrics().elidedText(game.name, Qt.TextElideMode.ElideRight, max(10, available))
        draw_match_text(painter, QRectF(rect.x() + 44, rect.y(), available, rect.height()), name,
                        index.data(Qt.ItemDataRole.UserRole + 2) or "")
        if favorite:
            painter.drawPixmap(int(rect.right() - 20), int(rect.center().y() - 7), icon("star_filled", "#93c5ff").pixmap(14, 14))
        evidence = index.data(Qt.ItemDataRole.UserRole + 1) or {}
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(compatibility_status(evidence)[1]))
        painter.drawEllipse(QRectF(rect.right() - (36 if favorite else 17), rect.center().y() - 3, 6, 6))
        painter.restore()


class LibraryPage(QWidget):
    PAGE_SIZE = 100

    def __init__(self, desk):
        super().__init__(desk)
        self.setObjectName("LibraryPage")
        self.desk, self.page, self.letter = desk, 0, "All"
        self.visible_ids = []
        self.layout_timer = QTimer(self)
        self.layout_timer.setSingleShot(True)
        self.layout_timer.timeout.connect(self.reflow)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 26, 24, 18)
        layout.setSpacing(14)
        heading = QHBoxLayout()
        title = QVBoxLayout()
        title.setSpacing(5)
        title.addWidget(label("Your library", "Title"))
        title.addWidget(label("Choose a letter or search to find your next game.", "Subtitle"))
        heading.addLayout(title, 1)
        self.back = button("Back to achievements", desk.show_achievements)
        heading.addWidget(self.back)
        layout.addLayout(heading)
        controls = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search games or App ID")
        self.search.addAction(icon("search"), QLineEdit.ActionPosition.LeadingPosition)
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.reset)
        controls.addWidget(self.search, 1)
        self.filter = QComboBox()
        self.filter.addItems(["All games", "Favorites", "Recent", "Installed", "Not installed", *COMPATIBILITY_FILTERS])
        self.filter.setCurrentText(desk.library_filter)
        self.filter.currentTextChanged.connect(self.filter_changed)
        controls.addWidget(self.filter)
        layout.addLayout(controls)
        alphabet = QWidget()
        alphabet.setObjectName("AlphabetBar")
        letters = QHBoxLayout(alphabet)
        letters.setContentsMargins(0, 0, 0, 0)
        letters.setSpacing(1)
        self.letter_group = QButtonGroup(self)
        self.letter_buttons = {}
        for value in ("All", "#", *string.ascii_uppercase):
            control = QPushButton(value)
            control.setObjectName("LetterButton")
            control.setFixedSize(34 if value == "All" else 24, 30)
            control.setCheckable(True)
            control.setChecked(value == "All")
            control.setAccessibleName("All initial letters" if value == "All" else "Numbers and other scripts" if value == "#" else f"Games starting with {value}")
            control.clicked.connect(lambda checked=False, value=value: self.set_letter(value))
            self.letter_group.addButton(control)
            self.letter_buttons[value] = control
            letters.addWidget(control)
        letters.addStretch()
        layout.addWidget(alphabet)
        summary = QHBoxLayout()
        self.results = label("", "Small")
        summary.addWidget(self.results, 1)
        summary.addWidget(label("100 games per page", "Small"))
        layout.addLayout(summary)
        self.games = QListWidget()
        self.games.setObjectName("CompactGameList")
        self.games.setViewMode(QListWidget.ViewMode.IconMode)
        self.games.setFlow(QListWidget.Flow.LeftToRight)
        self.games.setWrapping(True)
        self.games.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.games.setMovement(QListWidget.Movement.Static)
        self.games.setGridSize(QSize(320, 36))
        self.games.setItemDelegate(GameRowDelegate(desk, self.games))
        self.games.setMouseTracking(True)
        self.games.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.games.itemDoubleClicked.connect(self.open_selected)
        self.games.itemActivated.connect(self.open_selected)
        self.games.itemSelectionChanged.connect(self.selection_changed)
        self.games.verticalScrollBar().valueChanged.connect(self.request_visible_icons)
        layout.addWidget(self.games, 1)
        self.empty = label("Your library will appear here after Steam discovery.", "Subtitle", True)
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.empty)
        self.page_navigation = QWidget()
        navigation = QHBoxLayout(self.page_navigation)
        navigation.setContentsMargins(0, 0, 0, 0)
        self.previous = button("Previous", lambda: self.turn(-1))
        self.next = button("Next", lambda: self.turn(1))
        navigation.addWidget(self.previous)
        navigation.addStretch()
        self.page_links = QHBoxLayout()
        self.page_links.setSpacing(5)
        navigation.addLayout(self.page_links)
        navigation.addStretch()
        navigation.addWidget(self.next)
        self.page_buttons = {}
        layout.addWidget(self.page_navigation)
        footer = QHBoxLayout()
        self.count = label("", "Small")
        footer.addWidget(self.count, 1)
        self.favorite = button("Favorite", self.toggle_favorite)
        footer.addWidget(self.favorite)
        self.open = button("Open game", self.open_selected, True)
        footer.addWidget(self.open)
        layout.addLayout(footer)
        self.compatibility_hint = label("Compatibility dots: gray · not checked   blue · readable   green · confirmed changes   amber · check details", "Small", True)
        layout.addWidget(self.compatibility_hint)
        self.escape_shortcut = QShortcut(QKeySequence("Esc"), self)
        self.escape_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.escape_shortcut.activated.connect(desk.show_achievements)
        self.render()

    def reset(self):
        self.page = 0
        self.render()

    def filter_changed(self, value):
        self.page = 0
        self.desk.set_library_filter(value)

    def set_letter(self, value):
        if value not in self.letter_buttons:
            return
        self.letter = value
        self.letter_buttons[value].setChecked(True)
        self.reset()

    def turn(self, step):
        self.page += step
        self.render()

    def go_to_page(self, number):
        self.page = number
        self.render()
        if self.page in self.page_buttons:
            self.page_buttons[self.page].setFocus()

    def render_page_links(self, total):
        while self.page_links.count():
            widget = self.page_links.takeAt(0).widget()
            if widget:
                widget.hide()
                widget.deleteLater()
        self.page_buttons = {}
        self.page_navigation.setVisible(total > 0)
        for number in page_numbers(self.page, total):
            if number is None:
                self.page_links.addWidget(label("…", "Small"))
                continue
            control = QPushButton(str(number + 1))
            control.setObjectName("PageNumber")
            control.setCheckable(True)
            control.setChecked(number == self.page)
            control.setFixedSize(max(32, control.fontMetrics().horizontalAdvance(control.text()) + 20), 34)
            control.setAccessibleName(f"{'Current page' if number == self.page else 'Go to page'} {number + 1} of {total}")
            control.setToolTip(f"Page {number + 1} of {total}")
            control.clicked.connect(lambda checked=False, number=number: self.go_to_page(number))
            self.page_links.addWidget(control)
            self.page_buttons[number] = control

    def selected(self):
        item = self.games.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def selection_changed(self):
        game = self.selected()
        self.open.setEnabled(bool(game) and not self.desk.busy)
        self.favorite.setEnabled(bool(game))
        self.favorite.setText("Unfavorite" if game and game.app_id in self.desk.profile()["favorites"] else "Favorite")
        self.back.setEnabled(bool(self.desk.game))
        if hasattr(self, "compatibility_hint"):
            self.compatibility_hint.setText((compatibility_status(self.desk.game_compatibility(game.app_id))[0] + " · " + game.name + " · Hover the game for evidence.") if game else "Compatibility dots: gray · not checked   blue · readable   green · confirmed changes   amber · check details")

    def sync_library(self):
        self.filter.blockSignals(True)
        changed = self.filter.currentText() != self.desk.library_filter
        self.filter.setCurrentText(self.desk.library_filter)
        self.filter.blockSignals(False)
        if changed:
            self.page = 0
        self.render()

    def render(self):
        candidates = self.desk.match_games(self.search.text(), self.filter.currentText())
        if self.filter.currentText() != "Recent":
            candidates = sorted(candidates, key=lambda game: (unicodedata.normalize("NFKD", game.name).casefold(), game.app_id))
        counts = {key: 0 for key in self.letter_buttons}
        for game in candidates:
            counts[letter_bucket(game.name)] += 1
        for key, control in self.letter_buttons.items():
            control.setToolTip(f"{len(candidates) if key == 'All' else counts[key]} games")
        games = [game for game in candidates if self.letter == "All" or letter_bucket(game.name) == self.letter]
        self.page = max(0, min(self.page, max(0, (len(games) - 1) // self.PAGE_SIZE)))
        selected = self.selected() or self.desk.game
        self.games.blockSignals(True)
        self.games.clear()
        self.visible_ids = []
        start = self.page * self.PAGE_SIZE
        for game in games[start:start + self.PAGE_SIZE]:
            item = QListWidgetItem(game.name)
            item.setData(Qt.ItemDataRole.UserRole, game)
            evidence = self.desk.game_compatibility(game.app_id)
            item.setData(Qt.ItemDataRole.UserRole + 1, evidence)
            item.setData(Qt.ItemDataRole.UserRole + 2, self.search.text())
            item.setData(Qt.ItemDataRole.AccessibleDescriptionRole, compatibility_details(evidence))
            item.setToolTip(f"{game.name}\nApp ID {game.app_id} · {'Installed' if game.installed else 'Not installed'}\n{compatibility_details(evidence)}")
            self.games.addItem(item)
            self.visible_ids.append(game.app_id)
            if selected and selected.app_id == game.app_id:
                self.games.setCurrentItem(item)
        self.games.blockSignals(False)
        self.games.verticalScrollBar().setValue(0)
        self.results.setText(f"{len(games):,} games" + (f" starting with {self.letter}" if self.letter != "All" else ""))
        self.count.setText(f"{start + 1}–{min(start + self.PAGE_SIZE, len(games))} of {len(games):,} · Page {self.page + 1} of {max(1, math.ceil(len(games) / self.PAGE_SIZE))}" if games else "0 games")
        self.empty.setVisible(not games)
        self.empty.setText("No games match this letter and search. Choose All or clear the search." if self.desk.library else "Your library will appear here after Steam discovery.")
        self.previous.setEnabled(self.page > 0)
        self.next.setEnabled(start + self.PAGE_SIZE < len(games))
        self.render_page_links(math.ceil(len(games) / self.PAGE_SIZE))
        self.selection_changed()
        self.layout_timer.start(0)

    def reflow(self):
        width = max(1, self.games.viewport().width() - 14)
        columns = max(1, min(4, width // 310))
        size = QSize(width // columns, 36)
        if self.games.gridSize() != size:
            self.games.setGridSize(size)
        self.request_visible_icons()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "layout_timer"):
            self.layout_timer.start(0)

    def showEvent(self, event):
        super().showEvent(event)
        self.layout_timer.start(0)

    def request_visible_icons(self):
        if not self.isVisible():
            return
        first = self.games.indexAt(QPoint(8, 8)).row()
        columns = max(1, self.games.viewport().width() // max(1, self.games.gridSize().width()))
        count = columns * (self.games.viewport().height() // 36 + 2)
        for row in range(max(0, first), min(self.games.count(), max(0, first) + count)):
            self.desk.request_game_icon(self.games.item(row).data(Qt.ItemDataRole.UserRole).app_id)

    def toggle_favorite(self):
        game = self.selected()
        if game:
            self.desk.toggle_favorite(game)

    def open_selected(self, *_):
        game = self.selected()
        if game and not self.desk.busy:
            self.desk.connect(game)


def history_dialog(desk):
    dialog = QDialog(desk)
    dialog.setWindowTitle("Activity history")
    dialog.resize(820, 650)
    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(24, 24, 24, 24)
    layout.addWidget(label("Activity history", "Title"))
    layout.addWidget(label("Local records for the connected account. Unconfirmed means Steam persistence is unknown.", "Small", True))
    tree = QTreeWidget()
    tree.setHeaderLabels(["Date (local)", "Game", "Result", "Changes"])
    tree.setRootIsDecorated(False)
    tree.setColumnWidth(0, 155)
    tree.setColumnWidth(1, 260)
    entries = desk.workspace.history(desk.account_id or desk.library_account_id)
    for entry in entries:
        try:
            date = datetime.fromisoformat(entry["created_utc"]).astimezone().strftime("%Y-%m-%d %H:%M")
        except (ValueError, KeyError, TypeError):
            date = "Unknown date"
        item = QTreeWidgetItem([date, str(entry.get("game", "Unknown game")), str(entry.get("status", "unconfirmed")).capitalize(), str(len(entry.get("changes", [])))])
        item.setData(0, Qt.ItemDataRole.UserRole, entry)
        tree.addTopLevelItem(item)
    layout.addWidget(tree, 1)
    details = QTextEdit()
    details.setReadOnly(True)
    details.setPlaceholderText("Select an activity to inspect its requested changes and recorded result." if entries else "No activity recorded for this account yet.")
    layout.addWidget(details, 1)
    def select():
        item = tree.currentItem()
        if not item:
            return
        entry = item.data(0, Qt.ItemDataRole.UserRole)
        text = [str(entry.get("message", "")), ""]
        for change in entry.get("changes", []):
            result = "confirmed" if change.get("key") in entry.get("confirmed", []) else "rejected" if change.get("key") in entry.get("rejected", []) else "unconfirmed"
            text.append(f"{change.get('name', change.get('key', 'Achievement'))}  ·  {'Unlocked' if change.get('before') else 'Locked'} → {'Unlocked' if change.get('after') else 'Locked'}  ·  {result}")
        details.setPlainText("\n".join(text))
    tree.itemSelectionChanged.connect(select)
    footer = QHBoxLayout()
    footer.addWidget(label(f"{len(entries)} activities · Stored on this device", "Small"), 1)
    def export():
        path, _ = QFileDialog.getSaveFileName(dialog, "Export activity history", "achievement-desk-history.json", "JSON (*.json)")
        if path:
            try:
                from workspace import atomic_json
                atomic_json(path, entries)
            except OSError as exc:
                details.setPlainText(f"Export failed: {exc}")
    footer.addWidget(button("Export history…", export))
    footer.addWidget(button("Done", dialog.accept, True))
    layout.addLayout(footer)
    dialog.tree, dialog.details = tree, details
    return dialog
