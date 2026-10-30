"""Draw the original app icon and write a multiresolution Windows ICO."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from pathlib import Path
import struct
from PySide6.QtCore import Qt, QRectF, QPointF, QBuffer, QIODevice
from PySide6.QtGui import QPixmap, QPainter, QColor, QLinearGradient, QPen, QPainterPath
from PySide6.QtWidgets import QApplication

app = QApplication([])
assets = Path(__file__).resolve().parents[1] / "assets"
assets.mkdir(exist_ok=True)
images = []
for size in (16, 24, 32, 48, 64, 128, 256):
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(size / 128, size / 128)
    gradient = QLinearGradient(15, 8, 112, 120)
    gradient.setColorAt(0, QColor("#358eea"))
    gradient.setColorAt(1, QColor("#164c89"))
    p.setPen(QPen(QColor("#73b9ff"), 1.5))
    p.setBrush(gradient)
    p.drawRoundedRect(QRectF(7, 7, 114, 114), 27, 27)
    shield = QPainterPath(QPointF(33, 32))
    shield.lineTo(95, 32)
    shield.lineTo(95, 66)
    shield.cubicTo(95, 84, 75, 98, 64, 103)
    shield.cubicTo(53, 98, 33, 84, 33, 66)
    shield.closeSubpath()
    p.setPen(QPen(QColor("#e1f0ff"), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(QColor("#193856"))
    p.drawPath(shield)
    p.setPen(QPen(QColor("#ffffff"), 7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.drawLine(47, 63, 59, 75)
    p.drawLine(59, 75, 82, 49)
    p.end()
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    pix.save(buffer, "PNG")
    images.append((size, bytes(buffer.data())))
    if size == 256:
        pix.save(str(assets / "app.png"))
offset = 6 + 16 * len(images)
directory, data = b"", b""
for size, png in images:
    directory += struct.pack("<BBBBHHII", size if size < 256 else 0, size if size < 256 else 0, 0, 0, 1, 32, len(png), offset)
    data += png
    offset += len(png)
(assets / "app.ico").write_bytes(struct.pack("<HHH", 0, 1, len(images)) + directory + data)
print("Original icon generated at seven Windows resolutions.")
