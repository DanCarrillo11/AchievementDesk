"""Embedded, read-only details for the currently loaded achievement snapshot."""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QVBoxLayout, QScrollArea, QWidget, QLineEdit
from design import label, button, icon


class AchievementDetails(QFrame):
    def __init__(self, close, open_steam):
        super().__init__()
        self.setObjectName("AchievementDetails")
        self.setMinimumWidth(260)
        self.setMaximumWidth(320)
        self.key = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        header = QHBoxLayout()
        header.addWidget(label("Achievement details", "Metric"), 1)
        self.close_button = button("×", close)
        self.close_button.setObjectName("IconButton")
        self.close_button.setFixedSize(28, 28)
        self.close_button.setAccessibleName("Close achievement details")
        header.addWidget(self.close_button)
        layout.addLayout(header)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        body.setObjectName("DetailsBody")
        content = QVBoxLayout(body)
        content.setContentsMargins(0, 12, 0, 0)
        content.setSpacing(10)
        self.art = label("")
        self.art.setFixedSize(64, 64)
        self.name = label("", "SectionTitle", True)
        self.state = label("", "DetailState", True)
        identity = QHBoxLayout()
        identity.setSpacing(12)
        identity.addWidget(self.art, 0, Qt.AlignmentFlag.AlignTop)
        identity_text = QVBoxLayout()
        identity_text.setSpacing(5)
        identity_text.addWidget(self.name)
        identity_text.addWidget(self.state)
        identity.addLayout(identity_text, 1)
        content.addLayout(identity)
        self.description = label("", "Subtitle", True)
        self.date = label("", "Small", True)
        self.rarity = label("", "Small", True)
        self.restriction = label("", "Small", True)
        for widget in (self.description, self.date, self.rarity, self.restriction):
            content.addWidget(widget)
        content.addWidget(label("ACHIEVEMENT ID", "Eyebrow"))
        self.identifier = QLineEdit()
        self.identifier.setReadOnly(True)
        self.identifier.setAccessibleName("Achievement API identifier")
        identifier_row = QHBoxLayout()
        identifier_row.addWidget(self.identifier, 1)
        self.copy_button = button("Copy", self.copy_id)
        self.copy_button.setAccessibleName("Copy achievement ID")
        identifier_row.addWidget(self.copy_button)
        content.addLayout(identifier_row)
        content.addStretch()
        scroll.setWidget(body)
        layout.addWidget(scroll, 1)
        self.steam_button = button("View on Steam", open_steam)
        layout.addWidget(self.steam_button)

    def update_record(self, record, steam_available):
        self.key = record["key"]
        hidden = record.get("concealed", False)
        self.name.setText(record["name"])
        self.description.setText(record["description"])
        state = "Unlocked" if record["actual"] else "Locked"
        self.state.setText(state + (" · " + ("Unlock" if record["draft"] else "Lock") + " pending review"
                                   if record["draft"] != record["actual"] else " · Saved state"))
        self.date.setText("Unlocked " + record["date"] if record.get("date") else "No unlock date")
        self.date.setVisible(bool(record.get("date")))
        rarity = record.get("rarity")
        self.rarity.setText(f"{rarity:.1f}% of players" if rarity is not None else "Global rarity unavailable")
        self.restriction.setText(record.get("restriction") or "")
        self.restriction.setVisible(bool(record.get("restriction")))
        image = QPixmap(record.get("icon_path") or "")
        self.art.setPixmap(image.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                           if not image.isNull() else icon("lock" if hidden or not record["actual"] else "trophy", "#93c5ff", 48).pixmap(48, 48))
        self.identifier.setText("Hidden until revealed" if hidden else record["key"])
        self.identifier.setCursorPosition(0)
        self.identifier.setToolTip(self.identifier.text())
        self.copy_button.setEnabled(not hidden)
        self.copy_button.setText("Copy")
        self.steam_button.setEnabled(steam_available)

    def copy_id(self):
        if self.copy_button.isEnabled():
            QApplication.clipboard().setText(self.identifier.text())
            self.copy_button.setText("Copied")
            QTimer.singleShot(1800, self.copy_button, lambda: self.copy_button.setText("Copy"))
