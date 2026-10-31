"""Embedded achievement-set view. All actions prepare drafts for existing review."""
from datetime import datetime, timezone
from PySide6.QtCore import Qt
from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem
from completion import set_progress, unlock_restriction
from design import label, button


class CompletionPage(QWidget):
    def __init__(self, desk):
        super().__init__(desk)
        self.desk = desk
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 26, 24, 18)
        layout.setSpacing(16)
        heading = QHBoxLayout()
        heading.addWidget(label("Achievement sets & trophies", "Title"), 1)
        heading.addWidget(button("Back to achievements", desk.show_achievements))
        layout.addLayout(heading)
        self.game_title = label("", "Subtitle", True)
        layout.addWidget(self.game_title)
        self.summary = label("", "Metric", True)
        layout.addWidget(self.summary)
        self.notice = label("", "Small", True)
        layout.addWidget(self.notice)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Achievement set", "Current progress", "Steam trophy", "Availability"])
        self.tree.setRootIsDecorated(False)
        self.tree.setColumnWidth(0, 195)
        self.tree.setColumnWidth(1, 155)
        self.tree.setColumnWidth(2, 145)
        self.tree.itemSelectionChanged.connect(self.selection_changed)
        layout.addWidget(self.tree, 1)
        self.description = label("", "Small", True)
        layout.addWidget(self.description)
        layout.addWidget(label("Steam awards completion when a set's available achievements are unlocked. Previously earned completion can persist after new achievements are added. Relocking achievements does not guarantee trophy removal.", "Small", True))
        actions = QHBoxLayout()
        self.refresh = button("Refresh from Steam", lambda: desk.load_completion(force=True))
        actions.addWidget(self.refresh)
        actions.addStretch()
        self.show = button("Show achievements", self.show_selected)
        actions.addWidget(self.show)
        self.prepare = button("Prepare remaining unlocks", self.prepare_selected, True)
        actions.addWidget(self.prepare)
        layout.addLayout(actions)
        self.escape = QShortcut(QKeySequence("Esc"), self)
        self.escape.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.escape.activated.connect(desk.show_achievements)

    def selected(self):
        item = self.tree.currentItem()
        return item.data(0, Qt.ItemDataRole.UserRole) if item else None

    def render(self):
        data = self.desk.current_completion()
        selected = self.selected()
        self.tree.blockSignals(True)
        self.tree.clear()
        self.game_title.setText(self.desk.game.name if self.desk.game else "Choose a game first.")
        groups = data.get("groups", [])
        awarded = sum(g["completed"] is True for g in groups)
        unknown = sum(g["completed"] is None for g in groups)
        self.summary.setText((f"{len(groups)} achievement sets · completion unconfirmed" if unknown == len(groups) else f"{awarded} completed sets reported by Steam" + (f" · {unknown} unconfirmed" if unknown else "")) if groups else "Completion data not available")
        if data.get("loading"):
            self.notice.setText("Reading Steam's reported sets and trophies…")
        elif not self.desk.workspace.settings["online_completion"]:
            self.notice.setText("Enable Steam completion checks in Settings to load sets and trophies.")
        else:
            self.notice.setText(data.get("error") or data.get("notice") or ("Checked " + data["checked_utc"][:19].replace("T", " ") + " UTC · Reported status may take time to update after changes." if data.get("checked_utc") else ""))
        for group in groups:
            unlocked, total, missing = set_progress(group, self.desk.rows)
            progress = f"{unlocked} / {total}" + (f" · {missing} unknown" if missing else "")
            trophy = "Completed" if group["completed"] is True else "Not completed" if group["completed"] is False else "Unconfirmed"
            availability = "Archived" if group["archived"] else "Unavailable for account" if group["achievable"] is False else "DLC access unconfirmed" if group["dlc_app_id"] and group["achievable"] is not True else "DLC" if group["dlc_app_id"] else "Base game"
            item = QTreeWidgetItem([group["name"], progress, trophy, availability])
            for column, text in enumerate((group["name"], progress, trophy, availability)):
                item.setToolTip(column, text)
            item.setData(0, Qt.ItemDataRole.UserRole, group)
            if group.get("time_completed") and group["completed"]:
                try:
                    item.setToolTip(2, "Steam completion date: " + datetime.fromtimestamp(group["time_completed"], timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
                except (ValueError, OverflowError, OSError):
                    pass
            self.tree.addTopLevelItem(item)
            if selected and selected["id"] == group["id"]:
                self.tree.setCurrentItem(item)
        self.tree.blockSignals(False)
        if self.tree.currentItem() is None and self.tree.topLevelItemCount():
            self.tree.setCurrentItem(self.tree.topLevelItem(0))
        self.refresh.setEnabled(bool(self.desk.game) and not self.desk.demo and not data.get("loading") and self.desk.workspace.settings["online_completion"] and not self.desk.busy)
        self.selection_changed()

    def selection_changed(self):
        group = self.selected()
        ready = bool(group and self.desk.client and not self.desk.busy)
        self.show.setEnabled(ready)
        keys = {a["key"] for a in group["achievements"]} if group else set()
        remaining = [r for r in self.desk.rows if r.key in keys and not r.unlocked and not unlock_restriction(self.desk.current_completion(), r.key)]
        self.prepare.setEnabled(ready and bool(remaining))
        if group:
            _, total, missing = set_progress(group, self.desk.rows)
            self.description.setText(f"{len(remaining)} remaining achievements can be prepared for review." + (f" {missing} of {total} required achievements were not returned by the local Steam interface." if missing else "") + " Archived achievements are excluded. No trophy is assumed from current progress.")
        else:
            self.description.setText("Public game details are required for Steam to report account completion. No password or API key is needed.")

    def show_selected(self):
        group = self.selected()
        if group:
            self.desk.achievement_set = group["id"]
            self.desk.page = 0
            self.desk.show_achievements()
            self.desk.render()

    def prepare_selected(self):
        group = self.selected()
        if not group or self.desk.busy or not self.desk.client:
            return
        keys = {a["key"] for a in group["achievements"]}
        self.desk.prepare_keys({r.key for r in self.desk.rows if r.key in keys and not r.unlocked}, True)
        self.show_selected()
        self.desk.set_status("Set unlocks prepared. Review and apply to send changes to Steam.")
