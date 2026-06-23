#!/usr/bin/env python3
"""Generate an original contest-mcp icon: a logbook with a logged-QSO check and
radio waves. Renders at 4x then downsamples for crisp anti-aliasing."""
from PIL import Image, ImageDraw

S = 512
SS = 4  # supersample
W = S * SS


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# Rounded-square background, vertical gradient (deep navy -> radio teal).
top, bot = (16, 30, 64), (12, 92, 110)
radius = int(W * 0.22)
bg = Image.new("RGBA", (W, W), (0, 0, 0, 0))
bgd = ImageDraw.Draw(bg)
for y in range(W):
    bgd.line([(0, y), (W, y)], fill=lerp(top, bot, y / W) + (255,))
mask = Image.new("L", (W, W), 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, W, W], radius=radius, fill=255)
img.paste(bg, (0, 0), mask)
d = ImageDraw.Draw(img)

# Radio waves (concentric arcs) emanating from the lower-left "transmitter" dot.
ox, oy = int(W * 0.30), int(W * 0.74)
wave = (120, 220, 235)
d.ellipse([ox - 14 * SS, oy - 14 * SS, ox + 14 * SS, oy + 14 * SS], fill=wave + (255,))
for i, r in enumerate((46, 78, 110)):
    rr = r * SS
    bbox = [ox - rr, oy - rr, ox + rr, oy + rr]
    d.arc(bbox, start=-78, end=-12, fill=wave + (255,), width=int(6.5 * SS))

# Logbook card (white page with a turned corner) sitting upper-right.
lx0, ly0, lx1, ly1 = int(W * 0.34), int(W * 0.22), int(W * 0.80), int(W * 0.66)
paper = (245, 247, 250)
d.rounded_rectangle([lx0, ly0, lx1, ly1], radius=int(W * 0.035), fill=paper + (255,))
# Header bar.
d.rounded_rectangle(
    [lx0, ly0, lx1, ly0 + int(W * 0.085)],
    radius=int(W * 0.035),
    fill=(28, 52, 96, 255),
)
d.rectangle([lx0, ly0 + int(W * 0.05), lx1, ly0 + int(W * 0.085)], fill=(28, 52, 96, 255))
# Log rows.
row_x0 = lx0 + int(W * 0.05)
row_x1 = lx1 - int(W * 0.05)
ruled = (203, 213, 225)
for k in range(3):
    ry = ly0 + int(W * 0.135) + k * int(W * 0.075)
    d.rounded_rectangle(
        [row_x0, ry, row_x1, ry + int(W * 0.022)],
        radius=int(W * 0.011),
        fill=ruled + (255,),
    )

# Green "logged" check badge overlapping the card's lower-right.
cx, cy, cr = int(W * 0.74), int(W * 0.62), int(W * 0.13)
d.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=(34, 197, 94, 255))
d.ellipse(
    [cx - cr, cy - cr, cx + cr, cy + cr],
    outline=(245, 247, 250, 255),
    width=int(5 * SS),
)
d.line(
    [
        (cx - int(cr * 0.45), cy + int(cr * 0.02)),
        (cx - int(cr * 0.08), cy + int(cr * 0.40)),
        (cx + int(cr * 0.50), cy - int(cr * 0.42)),
    ],
    fill=(255, 255, 255, 255),
    width=int(9 * SS),
    joint="curve",
)

out = img.resize((S, S), Image.LANCZOS)
out.save("icon.png")
for sz in (128, 256, 512):
    out.resize((sz, sz), Image.LANCZOS).save(f"icon_{sz}.png")
print("wrote icon.png + size variants")
