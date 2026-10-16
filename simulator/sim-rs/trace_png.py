"""Draw a --terrain run trace over its map.

    python3 sim-rs/trace_png.py <trace.csv> <match seed> <player radius> <out.png>

Needs the release binary (uses `pokesim mapdump`). The map seed is the one
engine.rs derives from the match seed.
"""
import csv
import subprocess
import sys

from PIL import Image, ImageDraw

BIN = "sim-rs/target/release/pokesim"
TS = 32
COLORS = {"0": (111, 138, 79), "1": (90, 80, 66), "2": (79, 143, 208), "3": (30, 80, 30)}


def main():
    path, seed, radius, out = sys.argv[1], int(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
    rows = list(csv.DictReader(open(path)))
    xs = [float(r["x"]) for r in rows]
    ys = [float(r["y"]) for r in rows]
    half = int(max(max(map(abs, xs)), max(map(abs, ys))) / TS) + 24
    world_seed = (seed * 7919 + 1) & 0xFFFFFFFF
    if world_seed >= 1 << 31:
        world_seed -= 1 << 32
    grid = subprocess.run([BIN, "mapdump", str(world_seed), str(half)], capture_output=True, text=True, check=True).stdout.split()
    scale = 4  # px per tile
    side = 2 * half * scale
    img = Image.new("RGB", (side, side))
    d = ImageDraw.Draw(img)
    for j, line in enumerate(grid):
        for i, ch in enumerate(line):
            d.rectangle([i * scale, j * scale, i * scale + scale - 1, j * scale + scale - 1], fill=COLORS[ch])

    def px(x, y):
        return ((x / TS + half) * scale, (y / TS + half) * scale)

    pts = [px(x, y) for x, y in zip(xs, ys)]
    n = len(pts)
    for k in range(1, n):
        c = int(255 * k / n)
        d.line([pts[k - 1], pts[k]], fill=(255, 255 - c, 0), width=2)
    last = rows[-1]
    for e in last["enemies"].split():
        x, y, r, fly = e.split(":")
        cx, cy = px(float(x), float(y))
        rr = float(r) / TS * scale
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=(200, 200, 255) if fly == "1" else (220, 30, 30), width=1)
    cx, cy = pts[-1]
    rr = radius / TS * scale
    d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=(255, 255, 255))
    img.save(out)


if __name__ == "__main__":
    main()
