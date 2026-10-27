"""Turn a Flow-generated team emblem into web/public/team-logos/<ABBR>.webp.

Resizes to 900x900 and fades the outermost ring (the speed-line background) to transparent.

    python scripts/add_team_logo.py TOR path/to/flow.jpg
    python scripts/add_team_logo.py PHI flow.jpg --fade 420 500 --cy 0.46   # tall emblem: widen fade, shift centre

Needs Pillow, which is not a project dependency (use a scratch venv).
"""
import argparse
import math
from pathlib import Path

from PIL import Image

OUT = Path(__file__).resolve().parent.parent / "web" / "public" / "team-logos"
SIZE = 900
FADE_START, FADE_END = 385, 475  # px from centre: opaque inside, transparent outside


def main(abbr: str, src: str, fade=(FADE_START, FADE_END), cx=0.5, cy=0.5) -> None:
    im = Image.open(src).convert("RGB").resize((SIZE, SIZE), Image.LANCZOS)
    mask = Image.new("L", (SIZE, SIZE))
    px = mask.load()
    ox, oy = SIZE * cx, SIZE * cy
    for y in range(SIZE):
        for x in range(SIZE):
            t = min(1, max(0, (math.hypot(x - ox, y - oy) - fade[0]) / (fade[1] - fade[0])))
            px[x, y] = round(255 * (1 - t * t * (3 - 2 * t)))
    im.putalpha(mask)
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / f"{abbr.upper()}.webp"
    im.save(dest, "WEBP", quality=85, method=6)
    print(f"wrote {dest}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("abbr")
    ap.add_argument("src")
    ap.add_argument("--fade", type=float, nargs=2, default=(FADE_START, FADE_END), metavar=("START", "END"))
    ap.add_argument("--cx", type=float, default=0.5, help="emblem centre x as a fraction of the width")
    ap.add_argument("--cy", type=float, default=0.5, help="emblem centre y as a fraction of the height")
    a = ap.parse_args()
    main(a.abbr, a.src, tuple(a.fade), a.cx, a.cy)
