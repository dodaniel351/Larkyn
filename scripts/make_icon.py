"""Generate assets/larkyn.ico (multi-size) from the programmatic mic icon.

The mic is drawn on a rounded blue tile so it reads well as a desktop/taskbar
icon at every size. Re-run after changing the icon design.
"""

from __future__ import annotations

import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QBuffer, QIODevice, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter
from PySide6.QtWidgets import QApplication

from larkyn.ui.icons import _mic_pixmap

SIZES = [16, 24, 32, 48, 64, 128, 256]
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "assets", "larkyn.ico")


def tile_image(size: int) -> QImage:
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)

    grad = QLinearGradient(0, 0, 0, size)
    grad.setColorAt(0.0, QColor("#3B82F6"))
    grad.setColorAt(1.0, QColor("#1D4ED8"))
    p.setBrush(grad)
    p.setPen(Qt.NoPen)
    radius = size * 0.22
    p.drawRoundedRect(QRectF(0, 0, size, size), radius, radius)

    mic = _mic_pixmap("#FFFFFF", max(16, int(size * 0.9)))
    mic_scaled = mic.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    x = (size - mic_scaled.width()) / 2
    y = (size - mic_scaled.height()) / 2
    p.drawPixmap(int(x), int(y), mic_scaled)
    p.end()
    return img


def write_ico(images: list[QImage], path: str) -> None:
    """Assemble a .ico containing PNG-compressed images (valid since Vista)."""
    pngs: list[bytes] = []
    for img in images:
        buf = QBuffer()
        buf.open(QIODevice.WriteOnly)
        img.save(buf, "PNG")
        pngs.append(bytes(buf.data()))
        buf.close()

    header = struct.pack("<HHH", 0, 1, len(images))
    entries = b""
    offset = len(header) + 16 * len(images)
    for img, png in zip(images, pngs):
        w = img.width() if img.width() < 256 else 0
        h = img.height() if img.height() < 256 else 0
        entries += struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, len(png), offset)
        offset += len(png)

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(header + entries + b"".join(pngs))


def main() -> None:
    QApplication.instance() or QApplication([])
    images = [tile_image(s) for s in SIZES]
    write_ico(images, OUT)
    print(f"wrote {OUT} ({os.path.getsize(OUT)} bytes, sizes {SIZES})")


if __name__ == "__main__":
    main()
