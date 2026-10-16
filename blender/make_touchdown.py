"""Re-skin the Broadcast v2 touchdown animation for any team and render it.

Run with Blender (the "Make Touchdown Animation.command" launcher does this for you):

  Blender -b blender/touchdown_template.blend --python blender/make_touchdown.py -- \
      --name PIRATES --color "#003cc7" --logo assets/galena.png --out assets/anim/galena-td.webm

Options:
  --name     Text on the plate under TOUCHDOWN (e.g. STEAMERS, PIRATES)
  --color    (optional) Team color as hex; replaces the red enamel, glass backing, accents and rim light
  --logo     (optional) Logo image (PNG with transparent background works best)
  --out      Output .webm (transparent VP9) or a folder ending in / for PNG frames
  --keep-logo-tint   Keep the template's "push red pixels to brand red" logo tint (Fulton only)
  --preview  Render only a few still frames (PNG) into --out folder for a quick look
  --save     Also save the re-skinned .blend next to the output
"""
import argparse
import os
import sys

import bpy
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--name", required=True)
ap.add_argument("--color", help="omit to keep the template red")
ap.add_argument("--logo", help="omit to keep the template logo")
ap.add_argument("--out", required=True)
ap.add_argument("--keep-logo-tint", action="store_true")
ap.add_argument("--preview", action="store_true")
ap.add_argument("--save", action="store_true")
args = ap.parse_args(argv)

scene = bpy.context.scene
TEMPLATE_RED = (0xF2, 0x25, 0x00)


# ---------- color helpers ----------
def srgb_to_linear(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_rgb(h):
    h = h.strip().lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def lin(rgb, a=1.0):
    return (*[srgb_to_linear(v) for v in rgb], a)


def shade(rgb, f):
    return tuple(max(0, min(255, int(v * f))) for v in rgb)


def is_template_red(col):
    r, g, b = [int(max(0, min(1, v)) ** (1 / 2.2) * 255) for v in col[:3]]
    return abs(r - TEMPLATE_RED[0]) < 14 and abs(g - TEMPLATE_RED[1]) < 14 and abs(b - TEMPLATE_RED[2]) < 14


team = hex_rgb(args.color or "#F22500")
TEAM = lin(team)
SIDEWALL = lin(shade(team, 0.32))
RIM = tuple(min(1.0, v * 1.0 + 0.25) for v in lin(team)[:3])


# ---------- 1. colors ----------
swapped = 0
for m in (bpy.data.materials if args.color else []):
    if not m.use_nodes:
        continue
    for n in m.node_tree.nodes:
        for sock in n.inputs:
            if sock.type == "RGBA" and not sock.is_linked and is_template_red(sock.default_value):
                sock.default_value = TEAM
                swapped += 1
        if n.type == "VALTORGB":
            for e in n.color_ramp.elements:
                if is_template_red(e.color):
                    e.color = TEAM
                    swapped += 1
    if m.name == "V2 • Dark red sidewalls":
        m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = SIDEWALL
        swapped += 1
for o in (scene.objects if args.color else []):
    if o.type == "LIGHT" and o.name.startswith("RIM"):
        o.data.color = RIM
print(f"[touchdown] team color {args.color or 'template red (unchanged)'}: replaced {swapped} color values")


def reskin_logo():
    # ---------- 2. logo image ----------
    logo_path = os.path.abspath(args.logo)
    img = bpy.data.images.load(logo_path, check_existing=False)
    if max(img.size) < 1200:  # small web logos look blocky when the emblem fills the screen
        k = 1200 / max(img.size)
        img.scale(int(img.size[0] * k), int(img.size[1] * k))
        print(f"[touchdown] note: logo is small; upscaled x{k:.1f}. A larger logo file will look sharper.")
    img.pack()
    art_mat = bpy.data.materials["V2 • Mascot artwork"]
    for n in art_mat.node_tree.nodes:
        if n.type == "TEX_IMAGE":
            n.image = img
    if not args.keep_logo_tint:
        # the template recolors the boat's red pixels to brand red; other logos keep their own colors
        mix = art_mat.node_tree.nodes["Mix (Legacy)"]
        for l in list(art_mat.node_tree.links):
            if l.to_node == mix and l.to_socket == mix.inputs[0]:
                art_mat.node_tree.links.remove(l)
        mix.inputs[0].default_value = 0.0

    aw, ah = img.size
    aspect = aw / ah


    def fit_box(w0, h0):
        """Largest w,h with the logo's aspect that fits inside w0 x h0."""
        return (w0, w0 / aspect) if w0 / h0 < aspect else (h0 * aspect, h0)


    # resize the artwork card (plane) to the new logo's aspect, keeping its center and footprint
    card = scene.objects["Mascot • preserved RGBA artwork"]
    vs = card.data.vertices
    xs = [v.co.x for v in vs]
    ys = [v.co.y for v in vs]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    w0, h0 = max(xs) - min(xs), max(ys) - min(ys)
    nw, nh = fit_box(w0, h0)
    for v in vs:
        v.co.x = cx + (v.co.x - cx) * (nw / w0)
        v.co.y = cy + (v.co.y - cy) * (nh / h0)
    print(f"[touchdown] logo {aw}x{ah}: card {w0:.2f}x{h0:.2f} -> {nw:.2f}x{nh:.2f}")


    # ---------- 3. ghost outline traced from the new logo ----------
    def trace_contours(image, size=320, thresh=0.5):
        """Marching squares on the logo's alpha channel -> list of closed polylines in 0..1 uv space."""
        px = np.array(image.pixels[:], dtype=np.float32).reshape(image.size[1], image.size[0], 4)
        a = px[:, :, 3]
        # downsample to keep the curve light
        step = max(1, int(max(a.shape) / size))
        a = a[::step, ::step]
        a = np.pad(a, 1)
        H, W = a.shape
        b = a > thresh
        segs = {}

        def add(p, q):
            segs.setdefault(p, []).append(q)
            segs.setdefault(q, []).append(p)

        for y in range(H - 1):
            for x in range(W - 1):
                tl, tr, br, bl = b[y, x], b[y, x + 1], b[y + 1, x + 1], b[y + 1, x]
                idx = tl * 8 + tr * 4 + br * 2 + bl
                if idx in (0, 15):
                    continue
                T, R, B, L = (x + .5, y), (x + 1, y + .5), (x + .5, y + 1), (x, y + .5)
                table = {1: [(L, B)], 2: [(B, R)], 3: [(L, R)], 4: [(T, R)], 5: [(L, T), (B, R)], 6: [(T, B)],
                         7: [(L, T)], 8: [(L, T)], 9: [(T, B)], 10: [(T, R), (L, B)], 11: [(T, R)], 12: [(L, R)],
                         13: [(B, R)], 14: [(L, B)]}
                for p, q in table[idx]:
                    add(p, q)
        loops, seen = [], set()
        for start in list(segs):
            if start in seen:
                continue
            loop, prev, cur = [start], None, start
            seen.add(start)
            while True:
                nxt = [n for n in segs[cur] if n != prev and n not in seen]
                if not nxt:
                    break
                prev, cur = cur, nxt[0]
                seen.add(cur)
                loop.append(cur)
            if len(loop) > 24:
                loops.append([(px_ / (W - 1), 1 - py_ / (H - 1)) for px_, py_ in loop])
        loops.sort(key=len, reverse=True)
        return loops[:6]


    def rdp(pts, eps):
        if len(pts) < 3:
            return pts
        p = np.array(pts)
        s, e = p[0], p[-1]
        d = np.abs(np.cross(e - s, p - s)) / (np.linalg.norm(e - s) + 1e-9)
        i = int(np.argmax(d))
        if d[i] > eps:
            return rdp(pts[:i + 1], eps)[:-1] + rdp(pts[i:], eps)
        return [pts[0], pts[-1]]


    contours = [rdp(c, 0.0025) for c in trace_contours(img)]
    for name in ("Mascot • ghost contour 0", "Mascot • ghost contour 1", "Mascot • silver dimensional silhouette"):
        ob = scene.objects.get(name)
        if not ob:
            continue
        cu = ob.data
        pts = [p.co for s in cu.splines for p in (s.bezier_points if s.type == "BEZIER" else s.points)]
        bx = [p[0] for p in pts]
        by = [p[1] for p in pts]
        ccx, ccy = (min(bx) + max(bx)) / 2, (min(by) + max(by)) / 2
        bw, bh = fit_box(max(bx) - min(bx), max(by) - min(by))
        cu.splines.clear()
        for c in contours:
            sp = cu.splines.new("POLY")
            sp.points.add(len(c) - 1)
            for i, (u, v) in enumerate(c):
                sp.points[i].co = (ccx + (u - 0.5) * bw, ccy + (v - 0.5) * bh, 0.0, 1.0)
            sp.use_cyclic_u = True
    print(f"[touchdown] ghost outline: {len(contours)} contours traced from logo")



if args.logo:
    reskin_logo()
else:
    print("[touchdown] logo: template logo (unchanged)")


# ---------- 4. team name on the plate ----------
scene.objects["STEAMERS • team ID"].data.body = args.name.upper()


# ---------- 5. render ----------
r = scene.render
s = r.image_settings
out = os.path.abspath(args.out)
if args.preview:
    os.makedirs(out, exist_ok=True)
    s.media_type = "IMAGE"
    s.file_format = "PNG"
    s.color_mode = "RGBA"
    r.resolution_percentage = 50
    for f in (14, 40, 90, 140, 220):
        scene.frame_set(f)
        r.filepath = os.path.join(out, f"frame_{f:03d}.png")
        bpy.ops.render.render(write_still=True)
    print(f"[touchdown] preview frames -> {out}")
else:
    os.makedirs(os.path.dirname(out), exist_ok=True)
    s.media_type = "VIDEO"
    r.ffmpeg.format = "WEBM"
    r.ffmpeg.codec = "WEBM"
    s.color_mode = "RGBA"
    r.ffmpeg.constant_rate_factor = "HIGH"
    r.ffmpeg.ffmpeg_preset = "GOOD"
    r.ffmpeg.audio_codec = "NONE"
    r.resolution_percentage = 100
    r.filepath = out
    r.use_file_extension = False
    bpy.ops.render.render(animation=True)
    print(f"[touchdown] video -> {out}")

if args.save:
    bpy.ops.wm.save_as_mainfile(filepath=os.path.splitext(out.rstrip("/"))[0] + ".blend", copy=True)
