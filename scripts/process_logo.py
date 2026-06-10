"""Process assets/logo.png into app branding assets.

1. Remove the white background via flood fill from the image edges (interior
   whites — e.g. the bird's body — are preserved because they're enclosed).
2. Save the full transparent logo (wordmark included) -> assets/logo_transparent.png
3. Crop the emblem (the circular bird mark, above the wordmark):
   - transparent -> assets/emblem.png (used inside the dark-themed app UI)
   - on a solid white tile -> assets/emblem_white.png (crisper at small sizes)
4. Build the multi-size assets/hermes.ico from the WHITE-backed emblem — solid
   background keeps full contrast on dark taskbars (user preference).

Re-run whenever assets/logo.png changes.
"""

from __future__ import annotations

import os
import sys
from collections import deque

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")

WHITE_TOLERANCE = 28      # how close to pure white an edge-connected pixel must be
ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]


def remove_background(im: Image.Image) -> Image.Image:
    im = im.convert("RGBA")
    w, h = im.size
    px = im.load()

    def is_whiteish(p) -> bool:
        r, g, b, a = p
        return a > 0 and r >= 255 - WHITE_TOLERANCE and g >= 255 - WHITE_TOLERANCE \
            and b >= 255 - WHITE_TOLERANCE

    seen = [[False] * w for _ in range(h)]
    queue: deque[tuple[int, int]] = deque()
    for x in range(w):
        queue.append((x, 0))
        queue.append((x, h - 1))
    for y in range(h):
        queue.append((0, y))
        queue.append((w - 1, y))

    while queue:
        x, y = queue.popleft()
        if not (0 <= x < w and 0 <= y < h) or seen[y][x]:
            continue
        seen[y][x] = True
        if not is_whiteish(px[x, y]):
            continue
        px[x, y] = (255, 255, 255, 0)
        queue.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    return im


def crop_emblem(im: Image.Image) -> Image.Image:
    """Isolate the circular mark: take rows above the wordmark, then tight-crop."""
    w, h = im.size
    # The wordmark sits in the bottom ~25%; scan for the gap between mark and text.
    alpha = im.split()[-1]
    row_filled = [
        sum(1 for x in range(w) if alpha.getpixel((x, y)) > 16) for y in range(h)
    ]
    # Find the last empty-ish row band after the half-way point -> split there.
    split = h
    for y in range(int(h * 0.55), h):
        if row_filled[y] <= 1:
            split = y
            break
    emblem = im.crop((0, 0, w, split))
    bbox = emblem.getbbox()
    if bbox:
        emblem = emblem.crop(bbox)
    # Square-pad with transparency.
    side = max(emblem.size)
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.paste(emblem, ((side - emblem.width) // 2, (side - emblem.height) // 2))
    return sq


def on_white_tile(emblem: Image.Image, margin_frac: float = 0.08,
                  corner_frac: float = 0.16) -> Image.Image:
    """Composite the emblem onto a white rounded-corner tile (Win11 style).

    A solid tile avoids the gray anti-aliasing halo that background removal
    leaves around the artwork on dark surfaces.
    """
    from PIL import ImageDraw

    side = max(emblem.size)
    tile_side = int(side * (1 + 2 * margin_frac))
    # Draw at 4x and downsample for smooth corners.
    big = tile_side * 4
    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, big - 1, big - 1), radius=int(big * corner_frac), fill=255)
    mask = mask.resize((tile_side, tile_side), Image.LANCZOS)

    tile = Image.new("RGBA", (tile_side, tile_side), (255, 255, 255, 255))
    tile.paste(emblem, ((tile_side - emblem.width) // 2,
                        (tile_side - emblem.height) // 2), emblem)
    tile.putalpha(mask)
    return tile


def build_ico(image: Image.Image, path: str) -> None:
    base = image.resize((256, 256), Image.LANCZOS)
    base.save(path, format="ICO",
              sizes=[(s, s) for s in ICO_SIZES])


def main() -> None:
    src = os.path.join(ASSETS, "logo.png")
    im = Image.open(src)
    transparent = remove_background(im)
    transparent.save(os.path.join(ASSETS, "logo_transparent.png"))

    emblem = crop_emblem(transparent)
    emblem.save(os.path.join(ASSETS, "emblem.png"))

    emblem_white = on_white_tile(emblem)
    emblem_white.save(os.path.join(ASSETS, "emblem_white.png"))

    build_ico(emblem_white, os.path.join(ASSETS, "hermes.ico"))
    print(f"logo_transparent.png {transparent.size}, emblem.png {emblem.size}, "
          f"emblem_white.png {emblem_white.size}, hermes.ico sizes {ICO_SIZES}")


if __name__ == "__main__":
    main()
