"""Coordinate grid and target marks on a screenshot, to read and check emulator tap targets by eye.

  python _PortStudioMain/tools/shot_grid.py <shot.png> [--step 80] [--port <port-dir> --mode handheld|docked] [--out <png>]

Tap coordinates are screen pixels of the shot (handheld 1280x720, docked 1920x1080), the same numbers `tap X Y` and
port.json emulator.targets use. With --port, every target of that mode is drawn as a red ring with its name, so a stale
target (a button that moved) is visible before a scenario run is wasted. The output defaults to <shot>_grid.png.
"""

import argparse
import json
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:  # the tool needs Pillow; say so instead of failing with a traceback
    Image = ImageDraw = None


def targets_for(port, mode):
    config = Path(port) / "port.json"
    if not config.is_file():
        return {}
    data = json.loads(config.read_text(encoding="utf-8-sig"))
    return {name: point[mode] for name, point in data.get("emulator", {}).get("targets", {}).items()
            if isinstance(point, dict) and isinstance(point.get(mode), list) and len(point[mode]) == 2}


def draw_grid(shot, out, step=80, targets=None):
    with Image.open(shot) as image:
        canvas = image.convert("RGB")
    draw = ImageDraw.Draw(canvas)
    width, height = canvas.size
    for x in range(0, width, step):
        draw.line([(x, 0), (x, height)], fill=(0, 255, 255) if x % (step * 4) == 0 else (0, 140, 140), width=1)
        draw.text((x + 2, 2), str(x), fill=(255, 255, 0))
    for y in range(0, height, step):
        draw.line([(0, y), (width, y)], fill=(0, 255, 255) if y % (step * 4) == 0 else (0, 140, 140), width=1)
        draw.text((2, y + 2), str(y), fill=(255, 255, 0))
    outside = []
    for name, (x, y) in (targets or {}).items():
        if not (0 <= x < width and 0 <= y < height):
            outside.append(name)
            continue
        draw.ellipse([(x - 12, y - 12), (x + 12, y + 12)], outline=(255, 0, 0), width=3)
        draw.text((x + 14, y - 6), f"{name} ({x},{y})", fill=(255, 64, 64))
    canvas.save(out)
    return canvas.size, outside


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("shot", type=Path)
    parser.add_argument("--step", type=int, default=80, help="Grid spacing in pixels (default 80).")
    parser.add_argument("--port", type=Path, help="Port folder: draw its emulator.targets for --mode.")
    parser.add_argument("--mode", choices=("handheld", "docked"), default="handheld")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    if Image is None:
        print("Pillow is required: python -m pip install pillow", file=sys.stderr)
        return 2
    if not args.shot.is_file():
        print(f"Error: {args.shot} not found.", file=sys.stderr)
        return 1
    out = args.out or args.shot.with_name(args.shot.stem + "_grid.png")
    targets = targets_for(args.port, args.mode) if args.port else {}
    size, outside = draw_grid(args.shot, out, max(8, args.step), targets)
    print(f"Grid: {out} ({size[0]}x{size[1]}, step {args.step}); targets drawn: {len(targets) - len(outside)}")
    for name in outside:
        print(f"Warning: target {name} lies outside the {size[0]}x{size[1]} shot.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
