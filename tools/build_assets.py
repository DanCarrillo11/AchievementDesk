"""Export the approved trophy logo as PNG and multiresolution Windows ICO."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from pathlib import Path
import struct
from PySide6.QtCore import Qt, QBuffer, QIODevice
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])
assets = Path(__file__).resolve().parents[1] / "assets"
master = QPixmap(str(assets / "logo-master.png"))
if master.isNull() or master.width() != master.height():
    raise RuntimeError("assets/logo-master.png must be a readable square PNG.")
images = []
for size in (16, 24, 32, 48, 64, 128, 256):
    pix = master.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not pix.save(buffer, "PNG"):
        raise RuntimeError("Could not encode the application icon.")
    images.append((size, bytes(buffer.data())))
    if size == 256 and not pix.save(str(assets / "app.png")):
        raise RuntimeError("Could not save assets/app.png.")
offset = 6 + 16 * len(images)
directory, data = b"", b""
for size, png in images:
    directory += struct.pack("<BBBBHHII", size if size < 256 else 0, size if size < 256 else 0, 0, 0, 1, 32, len(png), offset)
    data += png
    offset += len(png)
(assets / "app.ico").write_bytes(struct.pack("<HHH", 0, 1, len(images)) + directory + data)
print("Trophy icon exported at seven Windows resolutions.")
