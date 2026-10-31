"""Qt desktop workspace with secondary operations in contextual menus."""
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import queue
import sys
import threading
import tempfile
import webbrowser

from PySide6.QtCore import Qt, QTimer, QSize, QRectF, QPoint
from PySide6.QtGui import QAction, QActionGroup, QColor, QFont, QPainter, QKeySequence, QShortcut, QPixmap, QIcon
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QFrame, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QStyledItemDelegate, QStyle, QToolButton,
    QMenu, QProgressBar, QScrollArea, QButtonGroup, QPushButton, QMessageBox, QDialog,
    QDialogButtonBox, QCheckBox, QTextEdit, QFileDialog, QInputDialog, QComboBox, QTreeWidget, QTreeWidgetItem, QStackedWidget)

from design import STYLE, AchievementRow, apply_dark_palette, icon, label, button
from domain import Achievement, plan_changes
from library import Game
from transport import GameClient, WorkerClient
from catalog import update_catalog

from workspace import Workspace, VERSION, order_achievements
from media import Media
from library_view import LibraryPage, history_dialog
from completion import CompletionService, unlock_restriction
from completion_view import CompletionPage
from compatibility import FILTERS as COMPATIBILITY_FILTERS, status as compatibility_status, details as compatibility_details, observe_read, observe_result


class GameDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        return QSize(220, 61)

    def paint(self, painter, option, index):
        game = index.data(Qt.ItemDataRole.UserRole)
        if not game:
            return
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = option.rect.adjusted(0, 2, -2, -2)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        if selected:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#193856"))
            painter.drawRoundedRect(rect, 10, 10)
            painter.setBrush(QColor("#087beb"))
            painter.drawRoundedRect(QRectF(rect.x(), rect.y() + 13, 2, rect.height() - 26), 1, 1)
        tile = QRectF(rect.x() + 10, rect.y() + 10, 33, 33)
        painter.setBrush(QColor("#25486a" if selected else "#303034"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(tile, 5, 5)
        font = QFont("Segoe UI", 9)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        game_icon = index.data(Qt.ItemDataRole.DecorationRole)
        if isinstance(game_icon, QPixmap) and not game_icon.isNull():
            image_rect = QRectF(tile.x() + 4.5, tile.y() + 4.5, 24, 24)
            painter.drawPixmap(image_rect, game_icon, QRectF(0, 0, game_icon.width(), game_icon.height()))
        else:
            painter.setPen(QColor("#93c5ff" if selected else "#b6b6be"))
            initials = "".join(word[0] for word in game.name.split()[:2]).upper()
            painter.drawText(tile, Qt.AlignmentFlag.AlignCenter, initials)
        painter.setPen(QColor("#f5f5f7" if selected else "#b6b6be"))
        painter.setFont(QFont("Segoe UI", 9))
        name = painter.fontMetrics().elidedText(game.name, Qt.TextElideMode.ElideRight, rect.width() - 66)
        painter.drawText(rect.x() + 54, rect.y() + 22, name)
        painter.setPen(QColor("#9999a5"))
        painter.setFont(QFont("Segoe UI", 8))
        evidence = index.data(Qt.ItemDataRole.UserRole + 1) or {}
        text = ("Installed" if game.installed else "Not installed") + " · " + compatibility_status(evidence)[0]
        painter.drawText(rect.x() + 54, rect.y() + 39, painter.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, rect.width() - 66))
        painter.restore()


class Desk(QMainWindow):
    PAGE_SIZE = 25

    def __init__(self, demo=False, hidden=False, data_dir=None):
        super().__init__()
        self.demo, self.client, self.game = demo, None, None
        self.rows, self.desired, self.library = [], {}, []
        self.selected, self.cards, self.filtered = set(), {}, []
        self._rendered_keys = None
        self.account_id = self.library_account_id = None
        self.busy, self.page = False, 0
        self.reveal_hidden, self.library_filter, self.achievement_filter = False, "All games", "All"
        self.callbacks = queue.Queue()
        self._temporary_data = tempfile.TemporaryDirectory() if demo and data_dir is None else None
        self.data_dir = Path(data_dir or (self._temporary_data.name if self._temporary_data else Path(os.environ.get("LOCALAPPDATA", str(Path.cwd()))) / "AchievementDesk"))
        self.workspace = Workspace(self.data_dir)
        self.reveal_hidden = self.workspace.settings["reveal_hidden"]
        self.library_filter = self.workspace.settings["library_filter"]
        self.achievement_sort = self.workspace.settings["achievement_sort"]
        self.game_icon_pixmaps, self.icon_paths, self.presentation = {}, {}, {}
        self.pending_game_icons, self.pending_icons = set(), set()
        self.library_page, self.activity_id, self.active_reader = None, None, None
        self.cancel_requested, self.can_cancel = False, False
        self.completions, self.completion_generation, self.achievement_set = {}, 0, None
        self.completion_requests = {}
        self.completion_service = CompletionService(self.callbacks.put)
        self.media = Media(self.data_dir / "public-cache", self.callbacks.put, enabled=not demo and self.workspace.settings["online_art"])
        self.setWindowTitle(f"Achievement Desk — {VERSION}")
        self.setWindowIcon(QIcon(str(Path(__file__).with_name("assets") / "app.ico")))
        self.resize(self.workspace.settings["width"], self.workspace.settings["height"])
        self.setMinimumSize(1020, 760)
        apply_dark_palette(QApplication.instance())
        self.setStyleSheet(STYLE)
        self.build()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(45)
        self.find_shortcut = QShortcut(QKeySequence.StandardKey.Find, self)
        self.find_shortcut.activated.connect(self.focus_search)
        self.refresh_shortcut = QShortcut(QKeySequence("Ctrl+R"), self)
        self.refresh_shortcut.activated.connect(self.refresh_current_view)
        self.extra_shortcuts = []
        for sequence, callback in (("Ctrl+B", self.browse_library), ("Ctrl+H", self.open_history), ("Ctrl+D", self.favorite_current_view), ("Ctrl+Return", self.review), ("F1", self.shortcuts)):
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.activated.connect(callback)
            self.extra_shortcuts.append(shortcut)
        self.render()
        if not hidden:
            QTimer.singleShot(100, self.load_library)

    def tool(self, kind, name, menu=None):
        result = QToolButton()
        result.setIcon(icon(kind))
        result.setIconSize(QSize(20, 20))
        result.setToolTip(name)
        result.setAccessibleName(name)
        result.setFixedSize(32, 32)
        if menu:
            result.setMenu(menu)
            result.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        return result

    def action(self, menu, text, callback, checkable=False):
        action = QAction(text, self)
        action.setCheckable(checkable)
        action.triggered.connect(callback)
        menu.addAction(action)
        return action

    def menu_button(self, text, kind, menu, sidebar=False):
        control = QToolButton()
        control.setObjectName("SidebarButton" if sidebar else "MenuButton")
        control.setText(text)
        control.setIcon(icon(kind))
        control.setIconSize(QSize(17, 17))
        control.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        control.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        control.setMenu(menu)
        control.setCursor(Qt.CursorShape.PointingHandCursor)
        control.setAccessibleName(text)
        return control

    @staticmethod
    def rule():
        line = QFrame()
        line.setObjectName("Rule")
        line.setFixedHeight(1)
        return line

    def build(self):
        central = QWidget()
        window_layout = QVBoxLayout(central)
        window_layout.setContentsMargins(0, 0, 0, 0)
        window_layout.setSpacing(0)
        self.setCentralWidget(central)
        self.app_header = QFrame()
        self.app_header.setObjectName("AppHeader")
        self.app_header.setFixedHeight(80)
        header_layout = QHBoxLayout(self.app_header)
        header_layout.setContentsMargins(24, 12, 24, 12)
        header_layout.setSpacing(14)
        emblem = QLabel()
        emblem.setPixmap(self.windowIcon().pixmap(40, 40) if not self.windowIcon().isNull() else icon("trophy", "#93c5ff", 32).pixmap(32, 32))
        emblem.setFixedWidth(40)
        header_layout.addWidget(emblem)
        brand_copy = QVBoxLayout()
        brand_copy.setSpacing(2)
        brand_copy.addWidget(label("Achievement Desk", "Brand"))
        brand_copy.addWidget(label("Your games. Your progress. Every achievement.", "BrandSub"))
        header_layout.addLayout(brand_copy)
        header_layout.addStretch()
        header_layout.addWidget(label("Steam client workspace", "Small"))
        self.settings_button = button("Settings", self.open_settings)
        self.settings_button.setIcon(icon("settings"))
        header_layout.addWidget(self.settings_button)
        window_layout.addWidget(self.app_header)
        body = QWidget()
        outer = QHBoxLayout(body)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        window_layout.addWidget(body, 1)
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(244)
        left = QVBoxLayout(sidebar)
        left.setContentsMargins(18, 26, 18, 18)
        left.setSpacing(14)
        left.addWidget(label("Workspace", "Eyebrow"))
        library_top = QHBoxLayout()
        library_top.addWidget(label("Library", "LibraryTitle"))
        library_top.addStretch()
        self.library_count = label("0", "Count")
        library_top.addWidget(self.library_count)
        self.library_menu = QMenu(self)
        group = QActionGroup(self)
        for value in ("All games", "Installed", "Not installed", "Favorites", "Recent", *COMPATIBILITY_FILTERS):
            action = self.action(self.library_menu, value, lambda checked=False, v=value: self.set_library_filter(v), True)
            action.setChecked(value == self.library_filter)
            group.addAction(action)
        self.library_filter_group = group
        left.addLayout(library_top)
        self.browse_button = button("Browse library", self.browse_library)
        self.browse_button.setObjectName("LibraryBrowse")
        self.browse_button.setCheckable(True)
        left.addWidget(self.browse_button)
        self.game_search = QLineEdit()
        self.game_search.setPlaceholderText("Search library")
        self.game_search.addAction(icon("search"), QLineEdit.ActionPosition.LeadingPosition)
        self.game_search.setClearButtonEnabled(True)
        self.game_search.textChanged.connect(self.filter_games)
        left.addWidget(self.game_search)
        self.library_filter_button = self.menu_button(self.library_filter, "down", self.library_menu, True)
        self.library_filter_button.setToolTip("Filter library")
        left.addWidget(self.library_filter_button)
        self.games = QListWidget()
        self.games.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.games.setItemDelegate(GameDelegate(self.games))
        self.games.itemClicked.connect(self.open_item)
        self.games.itemActivated.connect(self.open_item)
        self.games.verticalScrollBar().valueChanged.connect(self.request_visible_game_icons)
        left.addWidget(self.games, 1)
        self.library_tools_menu = QMenu(self)
        self.refresh_library_action = self.action(self.library_tools_menu, "Refresh library", lambda checked=False: self.load_library(force=True))
        self.add_id_action = self.action(self.library_tools_menu, "Open game by App ID…", self.open_id)
        self.library_tools_menu.addSeparator()
        self.catalog_action = self.action(self.library_tools_menu, "Update game catalog", self.refresh_catalog)
        left.addWidget(self.rule())
        self.library_tools_button = self.menu_button("Library tools", "library", self.library_tools_menu, True)
        left.addWidget(self.library_tools_button)
        history_button = button("Activity history", self.open_history)
        history_button.setObjectName("SidebarButton")
        left.addWidget(history_button)
        left.addWidget(self.rule())
        account = QHBoxLayout()
        avatar = label("S")
        avatar.setObjectName("Avatar")
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setFixedSize(32, 32)
        account.addWidget(avatar)
        account_text = QVBoxLayout()
        account_text.setSpacing(2)
        account_text.addWidget(label("Demo workspace" if self.demo else "Steam account"))
        self.account_label = label("Synthetic data" if self.demo else "Not connected", "Small")
        account_text.addWidget(self.account_label)
        account.addLayout(account_text, 1)
        self.hidden_action = QAction("Show hidden achievements", self)
        self.hidden_action.setCheckable(True)
        self.hidden_action.setChecked(self.reveal_hidden)
        self.hidden_action.toggled.connect(self.set_reveal)
        left.addLayout(account)
        outer.addWidget(sidebar)
        workspace = QWidget()
        workspace.setObjectName("Workspace")
        main = QVBoxLayout(workspace)
        main.setContentsMargins(32, 26, 32, 18)
        main.setSpacing(0)
        top = QHBoxLayout()
        top.addWidget(label("Library  /  Achievement editor", "Eyebrow"))
        top.addStretch()
        self.game_menu = QMenu(self)
        self.refresh_action = self.action(self.game_menu, "Refresh achievements", self.refresh)
        self.view_action = self.action(self.game_menu, "View on Steam", self.open_steam)
        self.export_action = self.action(self.game_menu, "Export achievement state…", self.export)
        self.action(self.game_menu, "Refresh artwork & rarity", lambda: self.load_presentation(force=True))
        self.selection_menu = QMenu(self)
        self.unlock_action = self.action(self.selection_menu, "Unlock selected", lambda: self.queue_state(True))
        self.lock_action = self.action(self.selection_menu, "Lock selected", lambda: self.queue_state(False))
        self.selection_menu.addSeparator()
        self.action(self.selection_menu, "Clear selection", self.clear_selection)
        self.more_button = self.menu_button("Game tools", "more", self.game_menu)
        self.favorite_button = button("Favorite", self.toggle_favorite)
        self.favorite_button.setToolTip("Favorite this game (Ctrl+D)")
        top.addWidget(self.favorite_button)
        top.addWidget(self.more_button)
        main.addLayout(top)
        main.addSpacing(22)
        hero = QWidget()
        hero.setObjectName("Hero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(24, 20, 24, 20)
        hero_layout.setSpacing(22)
        hero_copy = QWidget()
        hero_copy.setObjectName("HeroCopy")
        hero_text = QVBoxLayout(hero_copy)
        hero_text.setContentsMargins(0, 0, 0, 0)
        hero_text.setSpacing(8)
        self.game_title = label("Your achievements", "Title", True)
        hero_text.addWidget(self.game_title)
        self.caption = label("Choose a game from your library to get started.", "Subtitle")
        hero_text.addWidget(self.caption)
        hero_text.addSpacing(5)
        self.progress_text = label("No game selected", "Metric")
        hero_text.addWidget(self.progress_text)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        hero_text.addWidget(self.progress)
        hero_layout.addWidget(hero_copy, 1)
        stats = QVBoxLayout()
        stats.setContentsMargins(18, 0, 0, 0)
        stats.setSpacing(2)
        stats.addStretch()
        self.percent = label("—", "Percent")
        self.percent.setAlignment(Qt.AlignmentFlag.AlignRight)
        stats.addWidget(self.percent)
        completion = label("ACHIEVEMENTS", "Eyebrow")
        completion.setAlignment(Qt.AlignmentFlag.AlignRight)
        stats.addWidget(completion)
        stats.addStretch()
        hero_layout.addLayout(stats)
        main.addWidget(hero)
        main.addSpacing(12)
        info = QHBoxLayout()
        self.compatibility_button = button("Not checked", self.show_compatibility)
        info.addWidget(self.compatibility_button)
        info.addStretch()
        self.sets_button = button("Sets & trophies", self.show_completion)
        info.addWidget(self.sets_button)
        main.addLayout(info)
        main.addSpacing(14)
        list_header = QHBoxLayout()
        self.achievements_heading = label("Achievements", "SectionTitle")
        list_header.addWidget(self.achievements_heading)
        self.result_count = label("0", "Count")
        list_header.addWidget(self.result_count)
        list_header.addStretch()
        self.all_sets_button = button("All sets", self.clear_set_filter)
        self.all_sets_button.hide()
        list_header.addWidget(self.all_sets_button)
        self.selection_button = self.menu_button("Selection", "down", self.selection_menu)
        list_header.addWidget(self.selection_button)
        main.addLayout(list_header)
        main.addSpacing(12)
        tools = QHBoxLayout()
        tools.setSpacing(18)
        segments = QWidget()
        segments.setObjectName("Segments")
        segment_layout = QHBoxLayout(segments)
        segment_layout.setContentsMargins(0, 0, 0, 0)
        segment_layout.setSpacing(6)
        self.filter_group = QButtonGroup(self)
        self.filter_buttons = {}
        for value in ("All", "Locked", "Unlocked", "Pending"):
            control = QPushButton(value)
            control.setObjectName("Segment")
            control.setCheckable(True)
            control.setChecked(value == "All")
            control.clicked.connect(lambda checked=False, v=value: self.set_filter(v))
            self.filter_group.addButton(control)
            self.filter_buttons[value] = control
            segment_layout.addWidget(control)
        tools.addWidget(segments)
        tools.addStretch(1)
        self.search = QLineEdit()
        self.search.setObjectName("AchievementSearch")
        self.search.setPlaceholderText("Search achievements")
        self.search.addAction(icon("search"), QLineEdit.ActionPosition.LeadingPosition)
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(180)
        self.search.setMaximumWidth(270)
        self.search.textChanged.connect(self.search_changed)
        tools.addWidget(self.search)
        self.sort_menu = QMenu(self)
        self.sort_group = QActionGroup(self)
        for value in ("Steam order", "Name A–Z", "Name Z–A", "Newest unlocks", "Oldest unlocks", "Rarest first", "Most common first"):
            action = self.action(self.sort_menu, value, lambda checked=False, v=value: self.set_sort(v), True)
            action.setChecked(value == self.achievement_sort)
            self.sort_group.addAction(action)
        tools.addWidget(self.menu_button("Sort", "down", self.sort_menu))
        main.addLayout(tools)
        main.addSpacing(14)
        self.operation_bar = QWidget()
        operation_layout = QHBoxLayout(self.operation_bar)
        operation_layout.setContentsMargins(0, 0, 0, 10)
        self.operation_progress = QProgressBar()
        operation_layout.addWidget(self.operation_progress, 1)
        self.cancel_button = button("Cancel read", self.cancel_read)
        operation_layout.addWidget(self.cancel_button)
        main.addWidget(self.operation_bar)
        self.operation_bar.hide()
        self.error_bar = QWidget()
        error_layout = QHBoxLayout(self.error_bar)
        error_layout.setContentsMargins(0, 0, 0, 10)
        self.error_label = label("", "Small", True)
        error_layout.addWidget(self.error_label, 1)
        self.retry_button = button("Retry", self.retry)
        error_layout.addWidget(self.retry_button)
        error_layout.addWidget(button("Dismiss", self.error_bar.hide))
        main.addWidget(self.error_bar)
        self.error_bar.hide()
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_holder = QWidget()
        self.list_holder.setObjectName("ScrollContent")
        self.scroll.viewport().setStyleSheet("background:#171719;")
        self.list_layout = QVBoxLayout(self.list_holder)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(0)
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.rows_panel = QWidget()
        self.rows_panel.setObjectName("Rows")
        self.rows_layout = QVBoxLayout(self.rows_panel)
        self.rows_layout.setContentsMargins(0, 0, 7, 0)
        self.rows_layout.setSpacing(8)
        self.list_layout.addWidget(self.rows_panel)
        self.scroll.setWidget(self.list_holder)
        main.addWidget(self.scroll, 1)
        self.pagination = QWidget()
        pagination_layout = QHBoxLayout(self.pagination)
        pagination_layout.setContentsMargins(2, 10, 2, 0)
        self.page_label = label("", "Small")
        pagination_layout.addWidget(self.page_label)
        pagination_layout.addStretch()
        self.previous = self.tool("left", "Previous achievements")
        self.previous.clicked.connect(lambda: self.turn_page(-1))
        self.next = self.tool("right", "Next achievements")
        self.next.clicked.connect(lambda: self.turn_page(1))
        pagination_layout.addWidget(self.previous)
        pagination_layout.addWidget(self.next)
        main.addWidget(self.pagination)
        main.addSpacing(14)
        self.pending_bar = QWidget()
        self.pending_bar.setObjectName("PendingBar")
        pending_layout = QHBoxLayout(self.pending_bar)
        pending_layout.setContentsMargins(17, 13, 13, 13)
        pending_copy = QVBoxLayout()
        pending_copy.setSpacing(3)
        self.pending_label = label("", "Metric")
        pending_copy.addWidget(self.pending_label)
        pending_copy.addWidget(label("Review before applying to Steam.", "Small"))
        pending_layout.addLayout(pending_copy, 1)
        self.clear_button = button("Discard", self.clear_queue)
        pending_layout.addWidget(self.clear_button)
        self.review_button = button("Review changes", self.review, True)
        pending_layout.addWidget(self.review_button)
        main.addWidget(self.pending_bar)
        self.status = label("", "Small")
        self.status.setWordWrap(False)
        self.status.setMaximumHeight(20)
        main.addSpacing(10)
        main.addWidget(self.status)
        self.editor_page = workspace
        self.content_stack = QStackedWidget()
        self.content_stack.addWidget(self.editor_page)
        self.library_page = LibraryPage(self)
        self.content_stack.addWidget(self.library_page)
        self.completion_page = CompletionPage(self)
        self.content_stack.addWidget(self.completion_page)
        outer.addWidget(self.content_stack, 1)

    def set_status(self, text):
        self.status.setText(text)
        self.status.setToolTip(text)

    def profile(self):
        return self.workspace.profile(self.library_account_id or self.account_id)

    def game_compatibility(self, app_id):
        return self.workspace.compatibility(self.library_account_id or self.account_id, app_id)

    def save_compatibility(self, app_id, value):
        account = self.library_account_id or self.account_id
        if account:
            try:
                self.workspace.save_compatibility(account, app_id, value)
            except OSError:
                self.set_status("Compatibility evidence could not be saved.")

    def show_compatibility(self):
        if self.game:
            QMessageBox.information(self, "Game compatibility", compatibility_details(self.game_compatibility(self.game.app_id)))

    def current_completion(self):
        return self.completions.get((self.account_id, self.game.app_id), {}) if self.game else {}

    def load_completion(self, force=False):
        if not self.game or not self.account_id or not self.workspace.settings["online_completion"]:
            return
        key = (self.account_id, self.game.app_id)
        if self.demo:
            if key not in self.completions:
                self.completions[key] = dict(groups=[dict(id=0, name="Base game achievements", dlc_app_id=0,
                    archived=False, completed=None, achievable=True, time_completed=0,
                    achievements=[dict(key=r.key, archived=False) for r in self.rows])],
                    notice="Synthetic demonstration only. No Steam account or trophy status was requested.")
            return
        if not force and key in self.completions:
            return
        if self.completions.get(key, {}).get("loading") and not force:
            return
        generation = self.completion_generation
        request_id = self.completion_requests.get(key, 0) + 1
        self.completion_requests[key] = request_id
        # Drop previous statuses during a refresh; an old trophy flag is not a new confirmation.
        self.completions[key] = dict(loading=True, groups=[])
        self.render()
        def done(value):
            if (generation != self.completion_generation or self.completion_requests.get(key) != request_id
                    or not self.workspace.settings["online_completion"]):
                return
            self.completions[key] = value
            if self.game and (self.account_id, self.game.app_id) == key:
                invalid = [k for k, state in self.desired.items() if state and unlock_restriction(value, k)]
                for k in invalid:
                    self.desired.pop(k, None)
                self.render()
                if invalid:
                    self.set_status(f"Removed {len(invalid)} pending unlocks that Steam reports as restricted.")
        self.completion_service.load(key[1], key[0], done)

    def show_completion(self):
        if self.game:
            self.load_completion()
            self.completion_page.render()
            self.browse_button.setChecked(False)
            self.content_stack.setCurrentWidget(self.completion_page)

    def clear_set_filter(self):
        self.achievement_set = None
        self.page = 0
        self.render()

    def persist_settings(self):
        try:
            self.workspace.save()
        except OSError:
            self.set_status("Preferences could not be saved. Check your data folder permissions.")

    def match_games(self, query, mode):
        query = query.casefold()
        profile = self.profile()
        games = [game for game in self.library if query in (game.name + " " + str(game.app_id)).casefold()
            and (mode != "Installed" or game.installed) and (mode != "Not installed" or not game.installed)
            and (mode != "Favorites" or game.app_id in profile["favorites"])
            and (mode != "Recent" or game.app_id in profile["recent"])]
        if mode in COMPATIBILITY_FILTERS:
            games = [g for g in games if compatibility_status(self.game_compatibility(g.app_id))[0] == mode]
        if mode == "Recent":
            games.sort(key=lambda game: profile["recent"].index(game.app_id))
        return games

    def toggle_favorite(self, game=None):
        game = game if isinstance(game, Game) else self.game
        if not game:
            return
        try:
            self.workspace.favorite(self.library_account_id or self.account_id, game.app_id)
        except OSError as exc:
            self.set_status(f"Favorite could not be saved: {exc}")
            return
        self.filter_games()
        self.sync_controls()

    def request_game_icon(self, app_id):
        if app_id in self.game_icon_pixmaps or app_id in self.pending_game_icons or not self.media.enabled:
            return
        self.pending_game_icons.add(app_id)
        def done(path):
            self.pending_game_icons.discard(app_id)
            if path is None:
                return
            pixmap = QPixmap(str(path))
            if pixmap.isNull():
                return
            self.game_icon_pixmaps[app_id] = pixmap.scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            for index in range(self.games.count()):
                item = self.games.item(index)
                if item.data(Qt.ItemDataRole.UserRole).app_id == app_id:
                    item.setData(Qt.ItemDataRole.DecorationRole, self.game_icon_pixmaps[app_id])
            if self.library_page:
                self.library_page.games.viewport().update()
        game = next((game for game in self.library if game.app_id == app_id), self.game if self.game and self.game.app_id == app_id else None)
        self.media.game_icon(app_id, done, game.icon_hash if game else "")

    def request_visible_game_icons(self):
        first = self.games.indexAt(QPoint(8, 8)).row()
        for index in range(max(0, first), min(self.games.count(), max(0, first) + 18)):
            self.request_game_icon(self.games.item(index).data(Qt.ItemDataRole.UserRole).app_id)

    def load_presentation(self, force=False):
        if not self.game or self.demo or not self.media.enabled:
            return
        app_id = self.game.app_id
        if force:
            self.pending_game_icons.discard(app_id)
            self.pending_icons.clear()
            self.media.failed.clear()
        self.request_game_icon(app_id)
        def done(value):
            if not isinstance(value, dict):
                return
            self.presentation[app_id] = value
            if self.game and self.game.app_id == app_id:
                self.render()
        self.media.metadata(app_id, done, force=force)

    def request_achievement_icons(self, records):
        if not self.game or not self.media.enabled:
            return
        app_id = self.game.app_id
        icons = self.presentation.get(app_id, {}).get("icons", {})
        for record in records:
            if record.get("concealed"):
                continue
            key = record["key"]
            variant = "unlocked" if record["actual"] else "locked"
            filename = icons.get(key, {}).get(variant)
            cache_key = (app_id, key, variant)
            if filename and cache_key not in self.icon_paths and cache_key not in self.pending_icons:
                self.pending_icons.add(cache_key)
                def done(path, cache_key=cache_key):
                    self.pending_icons.discard(cache_key)
                    if path is None:
                        return
                    self.icon_paths[cache_key] = str(path)
                    if self.game and self.game.app_id == cache_key[0]:
                        self.render()
                self.media.achievement_icon(app_id, filename, done)

    def browse_library(self):
        self.library_page.sync_library()
        self.content_stack.setCurrentWidget(self.library_page)
        self.browse_button.setChecked(True)
        self.library_page.search.setFocus()

    def show_achievements(self):
        self.content_stack.setCurrentWidget(self.editor_page)
        self.browse_button.setChecked(False)

    def focus_search(self):
        target = self.library_page.search if self.content_stack.currentWidget() is self.library_page else self.search
        target.setFocus()

    def refresh_current_view(self):
        if self.content_stack.currentWidget() is self.library_page:
            self.load_library(force=True)
        else:
            self.refresh()

    def favorite_current_view(self):
        game = self.library_page.selected() if self.content_stack.currentWidget() is self.library_page else self.game
        if game:
            self.toggle_favorite(game)

    def open_history(self):
        dialog = history_dialog(self)
        dialog.exec()
        dialog.deleteLater()

    def shortcuts(self):
        QMessageBox.information(self, "Keyboard shortcuts", "Ctrl+B   Browse library\nCtrl+F   Search the current view\nCtrl+D   Favorite selected/current game\nCtrl+H   Activity history\nCtrl+R   Refresh the current view\nCtrl+Enter   Review pending changes\nEsc   Return from library to achievements\nTab / Space   Navigate / toggle switches\nCtrl+click   Select multiple achievement rows\nF1   Keyboard shortcuts")

    def set_sort(self, value):
        self.achievement_sort = value
        self.workspace.settings["achievement_sort"] = value
        self.persist_settings()
        for action in self.sort_group.actions():
            action.setChecked(action.text() == value)
        self.page = 0
        self.render()

    def cancel_read(self):
        if not self.busy or not self.can_cancel:
            return
        self.cancel_requested = True
        self.cancel_button.setEnabled(False)
        reader = self.active_reader
        if reader and hasattr(reader, "cancel"):
            threading.Thread(target=reader.cancel, daemon=True).start()
        self.set_status("Cancelling read…")

    def retry(self):
        callback = getattr(self, "retry_callback", None)
        if callback and not self.busy:
            self.error_bar.hide()
            callback()

    def poll(self):
        try:
            while True:
                self.callbacks.get_nowait()()
        except queue.Empty:
            pass

    def sync_controls(self):
        ready = bool(self.client and self.rows)
        for action in (self.refresh_library_action, self.catalog_action, self.add_id_action, self.hidden_action):
            action.setEnabled(not self.busy)
        self.refresh_action.setEnabled(bool(self.client) and not self.busy)
        self.view_action.setEnabled(bool(self.game and self.account_id and not self.demo) and not self.busy)
        self.export_action.setEnabled(bool(self.rows) and not self.busy)
        for action in (self.unlock_action, self.lock_action):
            action.setEnabled(ready and bool(self.selected) and not self.busy)
        self.selection_button.setVisible(bool(self.selected))
        self.selection_button.setText(f"{len(self.selected)} selected")
        self.selection_button.setEnabled(ready and not self.busy)
        self.clear_button.setEnabled(bool(self.desired) and not self.busy)
        self.review_button.setEnabled(ready and bool(self.desired) and not self.busy)
        self.games.setEnabled(not self.busy)
        self.favorite_button.setEnabled(bool(self.game) and not self.busy)
        self.compatibility_button.setEnabled(bool(self.game))
        self.sets_button.setEnabled(bool(self.game))
        favorite = bool(self.game and self.game.app_id in self.profile()["favorites"])
        self.favorite_button.setText("Favorited" if favorite else "Favorite")
        self.favorite_button.setIcon(icon("star_filled" if favorite else "star", "#93c5ff" if favorite else "#b6b6be"))
        if self.library_page:
            self.library_page.selection_changed()
        for card in self.cards.values():
            row = next((r for r in self.rows if r.key == card.key), None)
            restriction = unlock_restriction(self.current_completion(), card.key)
            card.switch.setEnabled(ready and not self.busy and not (restriction and row and not row.unlocked))
            card.switch.setToolTip(restriction if restriction and row and not row.unlocked else "Prepare an achievement change for review")
        self.completion_page.render()

    def task(self, job, success, uncertain=False, can_cancel=False, retry=None):
        if self.busy:
            return
        self.busy = True
        self.cancel_requested, self.can_cancel = False, can_cancel and not uncertain
        self.retry_callback = retry
        self.error_bar.hide()
        self.operation_progress.setRange(0, 0)
        self.operation_bar.show()
        self.cancel_button.setVisible(self.can_cancel)
        self.cancel_button.setEnabled(True)
        self.sync_controls()
        def finish(value=None, error=None):
            self.busy = False
            self.operation_bar.hide()
            self.active_reader = None
            if self.cancel_requested:
                if isinstance(value, tuple) and hasattr(value[0], "close"):
                    value[0].close()
                if self.client and hasattr(self.client, "reset_cancel"):
                    self.client.reset_cancel()
                self.set_status("Read cancelled. No changes were sent to Steam.")
                self.sync_controls()
                return
            if error:
                if uncertain:
                    self.record_outcome(dict(status="unconfirmed", message=error))
                    self.desired.clear()
                    self.rows.clear()
                    if self.client:
                        self.client.close()
                        self.client = None
                    self.render()
                    error = "The outcome may be partial or unknown. Check Steam before retrying.\n\n" + error
                self.set_status("Request failed. Open the game again to retry.")
                self.error_label.setText(error)
                self.retry_button.setVisible(bool(retry) and not uncertain)
                self.error_bar.show()
            else:
                try:
                    success(value)
                except Exception as exc:
                    self.set_status("Unable to display the result. Reload the game.")
                    QMessageBox.warning(self, "Result unavailable", str(exc))
            self.sync_controls()
        def execute():
            try:
                result = job()
                self.callbacks.put(lambda: finish(value=result))
            except Exception as exc:
                error = str(exc)
                self.callbacks.put(lambda: finish(error=error))
        threading.Thread(target=execute, daemon=True).start()

    def discard_queue(self):
        return not self.desired or QMessageBox.question(self, "Discard changes?",
            "Discard the pending changes? Nothing has been sent to Steam.") == QMessageBox.StandardButton.Yes

    def load_library(self, force=False):
        if self.busy or not self.discard_queue():
            return
        if self.client:
            self.client.close()
        self.client = self.game = self.account_id = self.library_account_id = None
        self.completion_generation += 1
        self.completions.clear()
        self.achievement_set = None
        self.rows, self.desired, self.library = [], {}, []
        self.selected.clear()
        self.filter_games()
        self.game_title.setText("Your achievements")
        self.caption.setText("Choose a game from your library to get started.")
        self.render()
        if self.demo:
            self.library_loaded(dict(account_id="DEMO", games=[asdict(Game(0, "The Last Explorer", True)), asdict(Game(100, "Distant Worlds", False))]))
            self.connect(self.library[0])
            return
        self.account_label.setText("Finding your library…")
        self.set_status("Refreshing your Steam library…" if force else "Checking Steam account and saved library…")
        def report(info):
            text = f"Finding your games · {info['scanned']:,} of {info['total']:,} checked"
            def update():
                if not self.cancel_requested:
                    self.set_status(text)
                    self.operation_progress.setRange(0, info["total"])
                    self.operation_progress.setValue(info["scanned"])
            self.callbacks.put(update)
        def job():
            worker = WorkerClient(0, library=True, refresh_library=force)
            self.active_reader = worker
            if self.cancel_requested:
                worker.cancel()
            try:
                return worker.receive(timeout=120, progress=report)
            finally:
                worker.close()
        self.task(job, self.library_loaded, can_cancel=True, retry=lambda: self.load_library(force=force))

    def library_loaded(self, reply):
        self.library_account_id = reply["account_id"]
        self.library = [Game(**game) for game in reply["games"]]
        self.account_label.setText("Synthetic data" if self.demo else f"Account ending {self.library_account_id[-4:]}")
        self.filter_games()
        source = "Saved library" if reply.get("cached") else "Steam library refreshed"
        self.set_status(f"{source} · {len(self.library):,} games · Use Refresh library to check for changes")

    def set_library_filter(self, value):
        self.library_filter = value
        self.workspace.settings["library_filter"] = value
        self.persist_settings()
        self.library_filter_button.setText(value)
        for action in self.library_filter_group.actions():
            action.setChecked(action.text() == value)
        self.filter_games()

    def filter_games(self, _=None):
        query = self.game_search.text().casefold()
        selected_id = self.game.app_id if self.game else self.profile().get("last_game")
        self.games.blockSignals(True)
        self.games.clear()
        for game in self.match_games(query, self.library_filter):
            item = QListWidgetItem(game.name)
            item.setData(Qt.ItemDataRole.UserRole, game)
            evidence = self.game_compatibility(game.app_id)
            item.setData(Qt.ItemDataRole.UserRole + 1, evidence)
            if game.app_id in self.game_icon_pixmaps:
                item.setData(Qt.ItemDataRole.DecorationRole, self.game_icon_pixmaps[game.app_id])
            item.setToolTip(f"{game.name}\nApp ID {game.app_id}\n{compatibility_details(evidence)}")
            self.games.addItem(item)
            if game.app_id == selected_id:
                self.games.setCurrentItem(item)
        self.games.blockSignals(False)
        self.library_count.setText(str(self.games.count()))
        self.request_visible_game_icons()
        if self.library_page:
            self.library_page.sync_library()

    def open_item(self, item):
        game = item.data(Qt.ItemDataRole.UserRole)
        if self.game and self.game.app_id == game.app_id and self.client:
            self.show_achievements()
            return
        self.connect(game)

    def connect(self, game):
        if self.busy:
            return
        if self.game and self.game.app_id == game.app_id and self.client:
            self.show_achievements()
            return
        if not self.discard_queue():
            return
        self.show_achievements()
        self.achievement_set = None
        self.desired.clear()
        self.rows.clear()
        self.selected.clear()
        self.render()
        self.set_status("Loading achievements…")
        def job():
            if self.client:
                self.client.close()
                self.client = None
            client = GameClient(game.app_id, self.demo)
            self.active_reader = client
            if self.cancel_requested:
                client.cancel()
            try:
                reply = client.receive()
                if self.library_account_id is not None and reply["account_id"] != self.library_account_id:
                    raise RuntimeError("Steam account changed. Refresh your library first.")
            except Exception:
                client.close()
                if not self.cancel_requested and self.library_account_id:
                    self.callbacks.put(lambda: self.failed_game_read(game.app_id))
                raise
            return client, reply
        def done(value):
            self.client, reply = value
            self.game, self.account_id = game, reply["account_id"]
            try:
                self.workspace.visit(self.account_id, game.app_id)
            except OSError:
                pass
            self.set_rows(reply)
            self.game_title.setText(game.name)
            self.caption.setText(f"Achievements · {'Installed' if game.installed else 'Not installed'}")
            self.game_title.setToolTip(f"App ID {game.app_id}")
            self.filter_games()
            self.load_presentation()
            self.load_completion()
        self.task(job, done, can_cancel=True, retry=lambda: self.connect(game))

    def set_rows(self, reply):
        if reply["account_id"] != self.account_id:
            raise RuntimeError("Steam account changed. Refresh your library.")
        self.rows = [Achievement(**row) for row in reply["achievements"]]
        if self.game:
            self.save_compatibility(self.game.app_id, observe_read(self.game_compatibility(self.game.app_id), len(self.rows)))
            self.filter_games()
        self.desired.clear()
        self.selected.clear()
        self.page = 0
        self.render()
        self.set_status("Demo data · Steam is not connected" if self.demo else "Up to date · Steam session closed")

    def failed_game_read(self, app_id):
        if self.cancel_requested:
            return
        self.save_compatibility(app_id, dict(self.game_compatibility(app_id), read="failed"))
        self.filter_games()

    def set_filter(self, value):
        self.achievement_filter = value
        self.filter_buttons[value].setChecked(True)
        self.page = 0
        self.render()

    def search_changed(self, _=None):
        self.page = 0
        self.render()

    def set_reveal(self, checked):
        self.reveal_hidden = checked
        self.workspace.settings["reveal_hidden"] = checked
        self.persist_settings()
        self.hidden_action.blockSignals(True)
        self.hidden_action.setChecked(checked)
        self.hidden_action.blockSignals(False)
        self.render()

    def display_record(self, row):
        hidden = row.hidden and not row.unlocked and not self.reveal_hidden
        date = datetime.fromtimestamp(row.unlock_time, timezone.utc).strftime("%b %d, %Y · UTC") if row.unlock_time else ""
        app_id = self.game.app_id if self.game else 0
        variant = "unlocked" if row.unlocked else "locked"
        return dict(key=row.key, name="Hidden achievement" if hidden else row.name,
            description="Reveal hidden details in Settings." if hidden else row.description or "No description available.",
            date=date, actual=row.unlocked, draft=self.desired.get(row.key, row.unlocked), unlock_time=row.unlock_time,
            rarity=self.presentation.get(app_id, {}).get("percentages", {}).get(row.key), concealed=hidden,
            restriction=unlock_restriction(self.current_completion(), row.key),
            icon_path=None if hidden else self.icon_paths.get((app_id, row.key, variant)))

    def render(self):
        query = self.search.text().casefold()
        self.filtered = []
        group = next((g for g in self.current_completion().get("groups", []) if g["id"] == self.achievement_set), None)
        if not group:
            self.achievement_set = None
        group_keys = {a["key"] for a in group["achievements"]} if group else None
        for row in self.rows:
            if group_keys is not None and row.key not in group_keys:
                continue
            record = self.display_record(row)
            if query not in (record["name"] + " " + record["description"] + " " + row.key).casefold():
                continue
            mode = self.achievement_filter
            if mode == "Locked" and row.unlocked or mode == "Unlocked" and not row.unlocked or mode == "Pending" and row.key not in self.desired:
                continue
            self.filtered.append(record)
        self.filtered = order_achievements(self.filtered, self.achievement_sort)
        self.page = min(self.page, max(0, (len(self.filtered) - 1) // self.PAGE_SIZE))
        page_records = self.filtered[self.page * self.PAGE_SIZE:(self.page + 1) * self.PAGE_SIZE]
        keys = [row["key"] for row in page_records]
        if self._rendered_keys != keys:
            self._rendered_keys = list(keys)
            while self.rows_layout.count():
                item = self.rows_layout.takeAt(0)
                if item.widget():
                    item.widget().hide()
                    item.widget().deleteLater()
            self.cards = {}
            for record in page_records:
                card = AchievementRow(record, self.toggle_achievement, self.select_row)
                card.set_preferences(self.workspace.settings["compact"], self.workspace.settings["reduce_motion"])
                self.cards[record["key"]] = card
                self.rows_layout.addWidget(card)
            if not keys:
                empty = QWidget()
                layout = QVBoxLayout(empty)
                layout.setContentsMargins(30, 55, 30, 55)
                glyph = QLabel()
                glyph.setPixmap(icon("library", "#9999a5", 44).pixmap(44, 44))
                glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.addWidget(glyph)
                title = label("No achievements to display" if self.game else "Choose your next milestone", "Metric")
                title.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.addSpacing(10)
                layout.addWidget(title)
                hint = label("Try another filter or search." if self.game else "Select a game from your library.", "Subtitle")
                hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.addWidget(hint)
                self.rows_layout.addWidget(empty)
            self.scroll.verticalScrollBar().setValue(0)
        else:
            for record in page_records:
                self.cards[record["key"]].update_record(record)
                self.cards[record["key"]].set_preferences(self.workspace.settings["compact"], self.workspace.settings["reduce_motion"])
        valid_keys = {row.key for row in self.rows}
        self.selected.intersection_update(valid_keys)
        for key, card in self.cards.items():
            card.set_selected(key in self.selected)
        unlocked, total = sum(row.unlocked for row in self.rows), len(self.rows)
        self.progress_text.setText(f"{unlocked} of {total} unlocked" if total else "No game selected" if not self.game else "No achievements")
        self.percent.setText(f"{unlocked / total:.0%}" if total else "")
        self.progress.setValue(round(100 * unlocked / total) if total else 0)
        self.result_count.setText(str(len(self.filtered)))
        self.achievements_heading.setText("Achievements" + (" · " + group["name"] if group else ""))
        self.achievements_heading.setMaximumWidth(300)
        self.all_sets_button.setVisible(bool(group))
        evidence = self.game_compatibility(self.game.app_id) if self.game else {}
        self.compatibility_button.setText(compatibility_status(evidence)[0])
        self.compatibility_button.setToolTip(compatibility_details(evidence))
        groups = self.current_completion().get("groups", [])
        completed = sum(g["completed"] is True for g in groups)
        unknown = sum(g["completed"] is None for g in groups)
        self.sets_button.setText((f"Sets & trophies · {len(groups)} sets" if unknown == len(groups) else f"Sets & trophies · {completed} completed") if groups else "Sets & trophies")
        self.pending_bar.setVisible(bool(self.desired))
        self.pending_label.setText(f"{len(self.desired)} {'change' if len(self.desired) == 1 else 'changes'} ready to review")
        self.pagination.setVisible(len(self.filtered) > self.PAGE_SIZE)
        self.page_label.setText(f"{self.page * self.PAGE_SIZE + 1}–{min((self.page + 1) * self.PAGE_SIZE, len(self.filtered))} of {len(self.filtered)}")
        self.previous.setEnabled(self.page > 0)
        self.next.setEnabled((self.page + 1) * self.PAGE_SIZE < len(self.filtered))
        self.sync_controls()
        self.request_achievement_icons(page_records)

    def turn_page(self, step):
        self.page = max(0, min(self.page + step, max(0, (len(self.filtered) - 1) // self.PAGE_SIZE)))
        self.render()

    def select_row(self, key, extend=False):
        if extend:
            self.selected.symmetric_difference_update({key})
        else:
            self.selected = {key}
        for item, card in self.cards.items():
            card.set_selected(item in self.selected)
        self.sync_controls()

    def clear_selection(self):
        self.selected.clear()
        for card in self.cards.values():
            card.set_selected(False)
        self.sync_controls()

    def toggle_achievement(self, key, state):
        if self.busy or not self.client or type(state) is not bool:
            self.render()
            return
        row = next((row for row in self.rows if row.key == key), None)
        if not row:
            return
        if state and not row.unlocked and unlock_restriction(self.current_completion(), key):
            self.render()
            self.set_status(unlock_restriction(self.current_completion(), key))
            return
        if row.unlocked == state:
            self.desired.pop(key, None)
        else:
            self.desired[key] = state
        self.render()
        self.set_status("Changes are pending review" if self.desired else "No pending changes")

    def queue_state(self, state):
        if self.busy or not self.client:
            return
        for row in self.rows:
            if row.key in self.selected:
                if state and not row.unlocked and unlock_restriction(self.current_completion(), row.key):
                    continue
                if row.unlocked == state:
                    self.desired.pop(row.key, None)
                else:
                    self.desired[row.key] = state
        self.render()

    def clear_queue(self):
        if self.busy:
            return
        self.desired.clear()
        self.render()
        self.set_status("Pending changes discarded")

    def refresh(self):
        if self.busy or not self.client or not self.discard_queue():
            return
        self.set_status("Refreshing achievements…")
        if hasattr(self.client, "reset_cancel"):
            self.client.reset_cancel()
        def job():
            self.active_reader = self.client
            if self.cancel_requested:
                self.client.cancel()
            return self.client.exchange(dict(command="read"))
        def done(reply):
            self.set_rows(reply)
            self.load_completion(force=True)
        self.task(job, done, can_cancel=True, retry=self.refresh)

    def make_review_dialog(self):
        changes = plan_changes(self.rows, self.desired)
        if any(c.after and unlock_restriction(self.current_completion(), c.key) for c in changes):
            raise ValueError("A selected achievement is restricted by Steam. Refresh and review again.")
        dialog = QDialog(self)
        dialog.setWindowTitle("Review changes")
        dialog.resize(590, 520)
        dialog.setMinimumSize(500, 430)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(28, 26, 28, 24)
        layout.setSpacing(16)
        layout.addWidget(label("Review your changes", "Title"))
        layout.addWidget(label(f"{self.game.name} · Account …{self.account_id[-4:]}", "Subtitle", True))
        listing = QTreeWidget()
        listing.setHeaderLabels(["Achievement", "Before", "After"])
        listing.setRootIsDecorated(False)
        listing.setColumnWidth(0, 300)
        names = {row.key: self.display_record(row)["name"] for row in self.rows}
        for change in changes:
            item = QTreeWidgetItem([names[change.key], "Unlocked" if change.before else "Locked", "Unlocked" if change.after else "Locked"])
            record = self.display_record(next(row for row in self.rows if row.key == change.key))
            if record.get("icon_path"):
                item.setIcon(0, QIcon(record["icon_path"]))
            listing.addTopLevelItem(item)
        layout.addWidget(listing, 1)
        layout.addWidget(label("A reference snapshot is saved first. Original dates and completion trophies cannot be restored from it. Steam may reject protected achievements.", "Small", True))
        consent = QCheckBox("I reviewed these changes.")
        layout.addWidget(consent)
        actions = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        apply = actions.addButton("Apply to demo" if self.demo else "Apply to Steam", QDialogButtonBox.ButtonRole.AcceptRole)
        apply.setObjectName("Primary")
        apply.setEnabled(False)
        consent.toggled.connect(apply.setEnabled)
        actions.rejected.connect(dialog.reject)
        def submit():
            if any(c.after and unlock_restriction(self.current_completion(), c.key) for c in changes):
                QMessageBox.warning(dialog, "Set restriction", "Steam reports a restriction on a selected achievement. Close this review and check the set.")
                return
            try:
                self.activity_id = self.workspace.start_activity(self.account_id, self.game,
                    [dict(**asdict(change), name=names[change.key]) for change in changes])
            except OSError as exc:
                QMessageBox.warning(dialog, "History unavailable", f"The local activity could not be recorded. No changes were sent.\n\n{exc}")
                return
            dialog.accept()
            request = dict(command="apply", account_id=self.account_id, changes=[asdict(change) for change in changes],
                snapshot_folder=str(self.data_dir / ("demo-snapshots" if self.demo else "snapshots")))
            self.set_status("Applying reviewed changes…")
            self.task(lambda: self.client.exchange(request), self.applied, uncertain=True)
        apply.clicked.connect(submit)
        layout.addWidget(actions)
        dialog.consent, dialog.apply_button, dialog.listing = consent, apply, listing
        return dialog

    def review(self):
        if not self.busy and self.client and self.desired:
            self.make_review_dialog().exec()

    def applied(self, reply):
        result = reply["result"]
        self.record_outcome(result)
        self.desired.clear()
        if result["status"] == "unconfirmed":
            self.rows.clear()
            if self.client:
                self.client.close()
            self.client = None
            self.render()
        else:
            self.set_rows(dict(account_id=self.account_id, achievements=result["achievements"]))
        self.set_status(f"Result: {result['status']} · Steam session closed")
        self.load_completion(force=True)
        message = f"Confirmed: {len(result['confirmed'])}\nRejected: {len(result['rejected'])}\nUnconfirmed: {len(result['unconfirmed'])}\n\n{result['message']}\n\nReference snapshot:\n{result['snapshot']}"
        QMessageBox.information(self, "Change result", message)

    def record_outcome(self, result):
        if self.activity_id:
            try:
                entry = next((x for x in self.workspace.history(self.account_id) if x.get("id") == self.activity_id), None)
                self.workspace.finish_activity(self.account_id, self.activity_id, result)
                if entry:
                    app_id = entry["app_id"]
                    evidence = self.workspace.compatibility(self.account_id, app_id)
                    self.save_compatibility(app_id, observe_result(evidence, result, entry.get("changes", [])))
                self.filter_games()
            except OSError:
                self.error_label.setText("The operation finished, but its history record could not be updated.")
                self.retry_button.hide()
                self.error_bar.show()
            self.activity_id = None

    def refresh_catalog(self):
        if self.busy:
            return
        if self.demo:
            self.set_status("Demo mode · No catalog download needed")
            return
        self.set_status("Updating public game catalog…")
        self.task(lambda: update_catalog(self.data_dir), lambda count:
            self.set_status(f"Catalog updated · {count:,} IDs · Refresh your library to check new games"))

    def open_id(self):
        if self.busy:
            return
        value, accepted = QInputDialog.getText(self, "Open game", "Steam App ID")
        if accepted:
            self.load_id(value)

    def load_id(self, value):
        try:
            app_id = int(value.strip())
            if not 0 < app_id < 2**32:
                raise ValueError()
        except ValueError:
            QMessageBox.information(self, "App ID", "Enter a valid numeric Steam App ID.")
            return
        if self.demo:
            self.set_status("Launch normally to connect to real games")
            return
        self.connect(next((game for game in self.library if game.app_id == app_id), Game(app_id, f"Steam App {app_id}")))

    def export(self):
        if self.busy or not self.rows or not self.game:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export achievement state", f"achievement-desk-{self.game.app_id}.json", "JSON (*.json)")
        if path:
            try:
                Path(path).write_text(json.dumps(dict(schema=1, app_id=self.game.app_id, account_id=self.account_id,
                    achievements=[asdict(row) for row in self.rows], note="Reference only; does not restore dates or trophies."), ensure_ascii=False, indent=2), encoding="utf-8")
                self.set_status("State exported")
            except OSError as exc:
                QMessageBox.warning(self, "Export failed", str(exc))

    def open_steam(self):
        if self.game and self.account_id and not self.demo:
            webbrowser.open(f"https://steamcommunity.com/profiles/{int(self.account_id)}/stats/{self.game.app_id}/achievements/")

    def make_settings_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Settings")
        dialog.resize(600, 760)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(28, 26, 28, 24)
        layout.setSpacing(16)
        layout.addWidget(label("WORKSPACE", "Eyebrow"))
        layout.addWidget(label("Settings", "Title"))
        layout.addWidget(label("Preferences are remembered on this device.", "Subtitle"))
        layout.addWidget(self.rule())
        layout.addWidget(label("Achievement display", "Metric"))
        reveal = QCheckBox("Show hidden achievement details")
        reveal.setChecked(self.reveal_hidden)
        reveal.setEnabled(not self.busy)
        reveal.toggled.connect(self.set_reveal)
        layout.addWidget(reveal)
        layout.addWidget(label("Reveal secret names and descriptions in the list and review screen.", "Small", True))
        density_row = QHBoxLayout()
        density_row.addWidget(label("Row density"), 1)
        density = QComboBox()
        density.addItems(["Comfortable", "Compact"])
        density.setCurrentIndex(int(self.workspace.settings["compact"]))
        density_row.addWidget(density)
        layout.addLayout(density_row)
        def preference(key, value):
            self.workspace.settings[key] = value
            self.persist_settings()
            self.media.enabled = not self.demo and self.workspace.settings["online_art"]
            self.render()
            if key == "online_art" and value:
                self.request_visible_game_icons()
                self.library_page.request_visible_icons()
                self.load_presentation()
            if key == "online_completion":
                self.completion_generation += 1
                self.completions.clear()
                self.achievement_set = None
                if value:
                    self.load_completion()
                self.render()
        density.currentIndexChanged.connect(lambda value: preference("compact", bool(value)))
        motion = QCheckBox("Reduce animations")
        motion.setChecked(self.workspace.settings["reduce_motion"])
        motion.toggled.connect(lambda value: preference("reduce_motion", value))
        layout.addWidget(motion)
        online = QCheckBox("Load public artwork and global rarity from Steam")
        online.setChecked(self.workspace.settings["online_art"])
        online.toggled.connect(lambda value: preference("online_art", value))
        layout.addWidget(online)
        layout.addWidget(label("Images and public metadata are cached locally. No API key or account details are sent.", "Small", True))
        completion = QCheckBox("Check achievement sets and trophies with Steam")
        completion.setChecked(self.workspace.settings["online_completion"])
        completion.toggled.connect(lambda value: preference("online_completion", value))
        layout.addWidget(completion)
        layout.addWidget(label("Completion checks send your Steam account ID and game ID to Steam Community, without cookies or credentials. Private game details may prevent trophy verification.", "Small", True))
        layout.addWidget(self.rule())
        layout.addWidget(label("Updates", "Metric"))
        repo = QLineEdit(self.workspace.settings["release_repository"])
        repo.setPlaceholderText("GitHub repository: owner/name")
        repo.setAccessibleName("Release repository")
        layout.addWidget(repo)
        update_text = label("Release channel not configured." if not repo.text() else "Check for published versions when you choose.", "Small", True)
        update_buttons = QHBoxLayout()
        alive = [True]
        dialog.finished.connect(lambda _: alive.__setitem__(0, False))
        release_url = [""]
        release_button = button("Open release page", lambda: webbrowser.open(release_url[0]) if release_url[0] else None)
        release_button.setEnabled(False)
        def save_repository():
            from updates import repository
            try:
                value = repository(repo.text()) if repo.text().strip() else ""
            except ValueError as exc:
                update_text.setText(str(exc))
                return
            self.workspace.settings["release_repository"] = value
            self.persist_settings()
        repo.editingFinished.connect(save_repository)
        def check():
            from updates import check_release, repository
            try:
                value = repository(repo.text())
            except ValueError as exc:
                update_text.setText(str(exc))
                return
            self.workspace.settings["release_repository"] = value
            self.persist_settings()
            check_button.setEnabled(False)
            update_text.setText("Checking public releases…")
            def job():
                try:
                    return check_release(value, VERSION)
                except Exception as exc:
                    return dict(message=f"Update check failed: {exc}", url="", newer=False)
            def done(result):
                if alive[0]:
                    check_button.setEnabled(True)
                    update_text.setText(("Update available. " if result["newer"] else "") + result["message"])
                    release_url[0] = result["url"]
                    release_button.setEnabled(bool(result["url"]))
            # Release lookup remains available even with optional Steam artwork disabled.
            threading.Thread(target=lambda: self.callbacks.put(lambda result=job(): done(result)), daemon=True).start()
        check_button = button("Check for updates", check)
        update_buttons.addWidget(check_button)
        update_buttons.addWidget(release_button)
        layout.addLayout(update_buttons)
        layout.addWidget(update_text)
        layout.addStretch()
        layout.addWidget(self.rule())
        footer = QHBoxLayout()
        footer.addWidget(label(f"Achievement Desk  /  {VERSION}", "Small"), 1)
        about = button("About", self.about)
        footer.addWidget(about)
        footer.addWidget(button("Shortcuts", self.shortcuts))
        close = button("Done", dialog.accept, True)
        close.setDefault(True)
        footer.addWidget(close)
        layout.addLayout(footer)
        dialog.reveal_checkbox = reveal
        dialog.density, dialog.motion, dialog.online, dialog.repo = density, motion, online, repo
        return dialog

    def open_settings(self):
        dialog = self.make_settings_dialog()
        dialog.exec()
        dialog.deleteLater()

    def about(self):
        QMessageBox.information(self, "Achievement Desk", f"Achievement Desk {VERSION}\n\nIndependent Steam achievement manager.\nRead Steam's achievement sets and reported completion; prepare remaining set unlocks for review.\nCompatibility is based on local evidence for this account.\nSteam controls trophy awards and persistence.\n\nNo password or API key is required.")

    def closeEvent(self, event):
        if self.busy:
            self.set_status("Wait for the current operation to finish before closing")
            event.ignore()
            return
        if not self.discard_queue():
            event.ignore()
            return
        if self.client:
            self.client.close()
        self.workspace.settings.update(width=self.width(), height=self.height())
        self.persist_settings()
        self.media.close()
        self.completion_service.close()
        self.timer.stop()
        event.accept()


def launch(demo=False):
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("DanCarrillo11.AchievementDesk")
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("Achievement Desk")
    window = Desk(demo=demo)
    window.show()
    app.exec()
