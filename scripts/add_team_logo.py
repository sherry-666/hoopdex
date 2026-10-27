"""Turn a Flow-generated team emblem into web/public/team-logos/<ABBR>.webp.

Resizes to 900x900 and fades the outermost ring (the speed-line background) to transparent.

    python scripts/add_team_logo.py TOR path/to/flow.jpg

Needs Pillow, which is not a project dependency (use a scratch venv).
"""
import math
import sys
from pathlib import Path

from PIL import Image

OUT = Path(__file__).resolve().parent.parent / "web" / "public" / "team-logos"
SIZE = 900
FADE_START, FADE_END = 385, 475  # px from centre: opaque inside, transparent outside


def main(abbr: str, src: str) -> None:
    im = Image.open(src).convert("RGB").resize((SIZE, SIZE), Image.LANCZOS)
    mask = Image.new("L", (SIZE, SIZE))
    px = mask.load()
    c = SIZE / 2
    for y in range(SIZE):
        for x in range(SIZE):
            t = min(1, max(0, (math.hypot(x - c, y - c) - FADE_START) / (FADE_END - FADE_START)))
            px[x, y] = round(255 * (1 - t * t * (3 - 2 * t)))
    im.putalpha(mask)
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / f"{abbr.upper()}.webp"
    im.save(dest, "WEBP", quality=85, method=6)
    print(f"wrote {dest}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
