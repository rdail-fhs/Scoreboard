"""Remove a logo's outer white background (keeps white that's inside the logo).

  python3 blender/cutout_logo.py input.png output.png

Only white connected to the image edges is removed, so white lettering and
highlights enclosed by the logo's outline stay. Runs with Blender's Python too:
  Blender -b --python blender/cutout_logo.py -- input.png output.png
"""
import sys
from collections import deque

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
src, dst = args[0], args[1]

try:
    from PIL import Image

    im = Image.open(src).convert("RGBA")
    w, h = im.size
    px = list(im.getdata())
    get = lambda i: px[i]

    def save(pixels):
        out = Image.new("RGBA", (w, h))
        out.putdata(pixels)
        out = out.crop(out.getbbox())
        out.save(dst)
        print(dst, out.size)
except ImportError:  # Blender's Python: no PIL, use bpy images
    import bpy

    img = bpy.data.images.load(src)
    w, h = img.size
    flat = list(img.pixels[:])
    px = [tuple(int(flat[i + k] * 255) for k in range(4)) for i in range(0, len(flat), 4)]
    # bpy images are bottom-up; edges are edges either way

    def save(pixels):
        out = bpy.data.images.new("cutout", w, h, alpha=True)
        out.pixels[:] = [c / 255 for p in pixels for c in p]
        out.filepath_raw = dst
        out.file_format = "PNG"
        out.save()
        print(dst, (w, h))

LIGHT = 228
light = lambda p: p[0] > LIGHT and p[1] > LIGHT and p[2] > LIGHT
removed = bytearray(w * h)
q = deque([(x, y) for x in range(w) for y in (0, h - 1)] + [(x, y) for y in range(h) for x in (0, w - 1)])
while q:
    x, y = q.popleft()
    i = y * w + x
    if removed[i] or not light(px[i]):
        continue
    removed[i] = 1
    px[i] = (255, 255, 255, 0)
    for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
        if 0 <= nx < w and 0 <= ny < h and not removed[ny * w + nx]:
            q.append((nx, ny))
# soften the light anti-aliased fringe next to the removed background
for y in range(1, h - 1):
    for x in range(1, w - 1):
        i = y * w + x
        r, g, b, a = px[i]
        if a and (removed[i - 1] or removed[i + 1] or removed[i - w] or removed[i + w]):
            lum = (r + g + b) / 3
            if lum > 150:
                px[i] = (r, g, b, int(255 * max(0, 255 - lum) / 105))
save(px)
