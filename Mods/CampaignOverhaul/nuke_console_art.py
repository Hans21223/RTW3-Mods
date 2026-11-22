"""Draws the nuclear strike console's pictures (nuclear_strike.py loads them in battle): the backdrop, the two arming
keys' frames (one set: both keys sit on plain backdrop), and the LAUNCH button under its glass cover (GLASS frames
from shut to open, each with the button dark or lit). Run it to rebuild nuke_console/*.bmp; with a path argument it
also writes a preview sheet.

The live parts (values, gauge fills, the info line, the click areas) are VCL controls at nuclear_strike.LAYOUT's
places; the key and LAUNCH pictures are cut from the backdrop at their places so they sit on it seamlessly.
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from nuclear_strike import CONSOLE as SIZE, FRAMES, GLASS, LAYOUT, PICTURES, TEXT

FOLDER = Path(__file__).resolve().parent/"nuke_console"
SS = 4                                  # supersampling
BG, BOX, CYAN, DIM = (11, 23, 32), (14, 30, 41), (60, 195, 200), (34, 92, 98)
TITLE, LABEL, YELLOW, SYMBOL = (189, 239, 240), (205, 218, 224), (240, 208, 64), (142, 151, 156)
METAL, METAL_DARK, RED, HOLE = (201, 209, 214), (70, 82, 90), (225, 52, 52), (22, 36, 46)
STATS = (("ssbns", "SSBNs READY"), ("warhead", "WARHEAD"), ("target", "TARGET"), ("status", "STATUS"))


def font(size, weight="SemiBold"):
    face = ImageFont.truetype("bahnschrift.ttf", size*SS)
    try: face.set_variation_by_name(weight)
    except (OSError, ValueError): pass
    return face


def spaced(draw, xy, text, face, fill, spacing=0, anchor="la"):
    """Text with extra letter spacing (supersampled units); anchor 'ma' centres it on x."""
    widths = [draw.textlength(ch, font=face) for ch in text]
    x, y = xy
    if anchor == "ma": x -= (sum(widths)+spacing*(len(text)-1))/2
    for ch, w in zip(text, widths):
        draw.text((x, y), ch, font=face, fill=fill)
        x += w+spacing


def frame(draw, left, top, right, bottom, outline=CYAN, fill=BOX):
    draw.rectangle([left*SS, top*SS, right*SS-1, bottom*SS-1], outline=outline, fill=fill, width=SS)


def stat_place(name):
    """The bottom strip's columns: (label x, value top) at 96 DPI."""
    x = LAYOUT["ssbns"][0]+[k for k, _ in STATS].index(name)*LAYOUT["ssbns"][2]
    return x, LAYOUT["ssbns"][1]


def backdrop():
    w, h = SIZE
    img = Image.new("RGB", (w*SS, h*SS), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w*SS-1, h*SS-1], outline=CYAN, width=SS)
    spaced(d, (w*SS/2, 7*SS), "NUCLEAR STRIKE", font(17), TITLE, spacing=3*SS, anchor="ma")
    for y in (32, LAYOUT["ssbns"][1]-24):                     # under the title; over the bottom strip
        d.line([10*SS, y*SS, (w-10)*SS, y*SS], fill=DIM, width=SS)
        for x in (10, w-10): d.line([x*SS, (y-3)*SS, x*SS, (y+3)*SS], fill=CYAN, width=SS)
    caption, small = font(10), font(11)
    for name, text in (("key1", "KEY 1"), ("key2", "KEY 2")):
        x, y, kw, kh = LAYOUT[name]
        spaced(d, ((x+48)*SS, (y+kh+2)*SS), text, caption, LABEL, spacing=SS, anchor="ma")
    for name, text in (("gauge_target", "TGT"), ("gauge_arm", "ARM")):   # gauge frames round the live fills
        x, y, gw, gh = LAYOUT[name]
        frame(d, x-2, y-2, x+gw+2, y+gh+2)
        for k in range(1, 6):
            ty = (y+gh*k/6)*SS
            d.line([(x-2)*SS, ty, (x+1)*SS, ty], fill=DIM, width=SS)
        spaced(d, ((x+gw/2)*SS, (y+gh+5)*SS), text, caption, LABEL, anchor="ma")
    x, y, tw, th = LAYOUT["tgt"]                               # TGT is a button: a crosshair under its caption
    cx, cy, r = (x+tw/2)*SS, (y+th-9)*SS, 6*SS
    d.ellipse([cx-r, cy-r, cx+r, cy+r], outline=CYAN, width=SS)
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        d.line([cx+dx*r*0.5, cy+dy*r*0.5, cx+dx*r*1.5, cy+dy*r*1.5], fill=CYAN, width=SS)
    x, y, lw, lh = LAYOUT["launch"]
    spaced(d, ((x+lw/2)*SS, (y+lh+2)*SS), "LAUNCH", font(12), LABEL, spacing=SS, anchor="ma")
    for name, text in STATS:                                   # the bottom strip's captions
        sx, sy = stat_place(name)
        spaced(d, (sx*SS, (sy-16)*SS), text, small, LABEL, spacing=SS)
    x, y, hw, hh = LAYOUT["warhead_hit"]                       # WARHEAD is a button: a frame, and arrows to cycle
    d.rounded_rectangle([x*SS, y*SS, (x+hw)*SS-1, (y+hh)*SS-1], radius=4*SS, outline=DIM, width=SS)
    for k in range(2):
        ax = (x+hw-16+k*6)*SS
        d.polygon([(ax, (y+4)*SS), (ax+4*SS, (y+8)*SS), (ax, (y+12)*SS)], fill=CYAN)
    x, y, aw, ah = LAYOUT["cancel"]                            # ABORT, a framed button
    frame(d, x, y, x+aw, y+ah, fill=BOX)
    spaced(d, ((x+aw/2)*SS, (y+4)*SS), "ABORT", font(12, "Bold"), CYAN, spacing=2*SS, anchor="ma")
    return img.resize(SIZE, Image.LANCZOS)


def cut(base, name):
    left, top, w, h = LAYOUT[name]
    return base.crop((left, top, left+w, top+h)).resize((w*SS, h*SS), Image.LANCZOS)


def key_frame(base, step):
    """Frame step of FRAMES: the key's bow turned step/(FRAMES-1) of 90 degrees clockwise from upright."""
    img = cut(base, "key1")
    d = ImageDraw.Draw(img)
    cx, cy, ring = 48*SS, 50*SS, 32*SS
    armed = step == FRAMES-1
    colour = RED if armed else CYAN
    d.ellipse([cx-ring, cy-ring, cx+ring, cy+ring], fill=BOX, outline=colour, width=2*SS)
    d.ellipse([cx-ring*0.72, cy-ring*0.72, cx+ring*0.72, cy+ring*0.72], fill=HOLE, outline=METAL_DARK, width=SS)
    for angle, text, at in ((90, "SAFE", (cx, 1*SS)), (0, "ARM", (cx+ring+4*SS, cy-6*SS))):
        tx, ty = cx+math.cos(math.radians(angle))*ring*0.86, cy-math.sin(math.radians(angle))*ring*0.86
        ex, ey = cx+math.cos(math.radians(angle))*ring*1.02, cy-math.sin(math.radians(angle))*ring*1.02
        d.line([tx, ty, ex, ey], fill=colour if (angle == 0) == armed else DIM, width=2*SS)
        spaced(d, at, text, font(10), RED if (angle == 0 and armed) else LABEL, anchor="ma" if angle == 90 else "la")
    turn = math.radians(90*step/(FRAMES-1))
    ux, uy = math.sin(turn), -math.cos(turn)      # along the bow
    vx, vy = -uy, ux                              # across it
    def at(a, b): return (cx+ux*a+vx*b, cy+uy*a+vy*b)
    grip, stub, width = ring*0.95, ring*0.42, ring*0.30
    outline = [at(-stub, -width*0.55), at(grip*0.35, -width*0.6), at(grip*0.45, -width*1.15), at(grip*0.95, -width*1.15),
               at(grip*1.08, -width*0.6), at(grip*1.08, width*0.6), at(grip*0.95, width*1.15), at(grip*0.45, width*1.15),
               at(grip*0.35, width*0.6), at(-stub, width*0.55)]
    d.polygon([(x+1.5*SS, y+1.5*SS) for x, y in outline], fill=(5, 10, 14))          # its shadow
    d.polygon(outline, fill=METAL, outline=METAL_DARK, width=SS)
    hole, r = at(grip*0.78, 0), width*0.45
    d.ellipse([hole[0]-r, hole[1]-r, hole[0]+r, hole[1]+r], fill=HOLE, outline=METAL_DARK, width=SS)
    hub = ring*0.24
    d.ellipse([cx-hub, cy-hub, cx+hub, cy+hub], fill=METAL_DARK, outline=METAL, width=SS)
    return img.resize(LAYOUT["key1"][2:], Image.LANCZOS)


def launch_frame(base, glass, lit):
    """The LAUNCH button (lit: both keys at ARM) under its glass cover, hinged at the top: glass 0 shut .. GLASS-1
    open (flipped up past the hinge)."""
    img = cut(base, "launch").convert("RGBA")
    w, h = img.size
    cx, cy = w/2, h/2
    d = ImageDraw.Draw(img)
    plate = 54*SS
    d.rectangle([cx-plate, cy-plate, cx+plate, cy+plate], fill=BOX, outline=DIM, width=SS)
    for k in range(-8, 9):                                      # a yellow and black hazard ring round the button
        a0, a1 = k*22.5, k*22.5+11.25
        d.pieslice([cx-44*SS, cy-44*SS, cx+44*SS, cy+44*SS], a0, a1, fill=(214, 170, 30))
    d.ellipse([cx-38*SS, cy-38*SS, cx+38*SS, cy+38*SS], fill=(18, 18, 18))
    r = 33*SS
    body, rim = ((226, 36, 36), (255, 120, 110)) if lit else ((92, 24, 24), (130, 52, 52))
    if lit: d.ellipse([cx-r-4*SS, cy-r-4*SS, cx+r+4*SS, cy+r+4*SS], fill=(150, 20, 20))     # a glow
    d.ellipse([cx-r, cy-r, cx+r, cy+r], fill=body, outline=(40, 8, 8), width=2*SS)
    d.arc([cx-r*0.75, cy-r*0.75, cx+r*0.55, cy+r*0.55], 200, 290, fill=rim, width=3*SS)   # its shine
    hinge_y = cy-plate
    for hx in (-30, 30):                                        # the hinge blocks
        d.rectangle([cx+(hx-8)*SS, hinge_y-3*SS, cx+(hx+8)*SS, hinge_y+3*SS], fill=METAL_DARK, outline=METAL)
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    o = ImageDraw.Draw(overlay)
    reach = [1.0, 0.62, 0.24, -0.30][glass] if GLASS == 4 else 1.0-1.3*glass/(GLASS-1)
    span = 2*plate*abs(reach)
    if reach > 0:                                               # still over the button: its pane, shrinking to the hinge
        box = [cx-plate+3*SS, hinge_y, cx+plate-3*SS, hinge_y+span]
        o.rounded_rectangle(box, radius=6*SS, fill=(150, 220, 235, 70), outline=(190, 240, 250, 200), width=2*SS)
        for k in (0.2, 0.45):                                   # reflections
            o.line([box[0]+(box[2]-box[0])*k, box[3]-4*SS, box[0]+(box[2]-box[0])*(k+0.25), box[1]+4*SS],
                   fill=(235, 250, 255, 90), width=3*SS)
        if reach == 1.0:                                        # the lift tab
            o.rounded_rectangle([cx-14*SS, box[3]-7*SS, cx+14*SS, box[3]+3*SS], radius=3*SS, fill=(214, 170, 30, 230))
    else:                                                       # flipped up past the hinge: its underside, dimmer
        box = [cx-plate+3*SS, hinge_y-span, cx+plate-3*SS, hinge_y]
        o.rounded_rectangle(box, radius=6*SS, fill=(90, 140, 150, 120), outline=(160, 210, 220, 200), width=2*SS)
    img = Image.alpha_composite(img, overlay).convert("RGB")
    return img.resize(LAYOUT["launch"][2:], Image.LANCZOS)


def build():
    FOLDER.mkdir(exist_ok=True)
    for old in FOLDER.glob("*.bmp"):
        if old.stem not in PICTURES: old.unlink()
    base = backdrop()
    base.save(FOLDER/"backdrop.bmp")
    for step in range(FRAMES):
        key_frame(base, step).save(FOLDER/f"key{step}.bmp")
    for glass in range(GLASS):
        for lit in (0, 1):
            launch_frame(base, glass, lit).save(FOLDER/f"launch{glass}{'a' if lit else 's'}.bmp")
    return base


def preview(path):
    """Three moments side by side: SAFE with the glass shut; one key turned, the glass opening; ARMED, glass open."""
    base = build()
    gap, w, h = 12, *SIZE
    sheet = Image.new("RGB", (w*3+gap*2, h), (40, 40, 40))
    value = ImageFont.truetype("bahnschrift.ttf", 15)
    for column, (k1, k2, glass, target, status) in enumerate(((0, 0, 0, "NONE", "SAFE"),
                                                              (FRAMES-1, 3, 1, "MARKED", "SAFE"),
                                                              (FRAMES-1, FRAMES-1, GLASS-1, "MARKED", "ARMED"))):
        img = base.copy(); d = ImageDraw.Draw(img)
        lit = k1 == k2 == FRAMES-1
        img.paste(Image.open(FOLDER/f"key{k1}.bmp"), LAYOUT["key1"][:2])
        img.paste(Image.open(FOLDER/f"key{k2}.bmp"), LAYOUT["key2"][:2])
        img.paste(Image.open(FOLDER/f"launch{glass}{'a' if lit else 's'}.bmp"), LAYOUT["launch"][:2])
        for name, text in (("ssbns", "11"), ("warhead", TEXT[f"name{column}"]), ("target", target), ("status", status)):
            x, y = stat_place(name); d.text((x, y), text, font=value, fill=YELLOW)
        for name, full in (("gauge_target", target == "MARKED"), ("gauge_arm", None)):
            x, y, gw, gh = LAYOUT[name]
            share = 1.0 if full else ((k1+k2)/(2*(FRAMES-1)) if full is None else 0)
            if share: d.rectangle([x, y+gh-int(gh*share), x+gw-1, y+gh-1], fill=(217, 115, 122))
        x, y, _, _ = LAYOUT["info"]
        d.text((x, y), "Target marked. Turn both keys, open the glass, LAUNCH.", font=ImageFont.truetype("bahnschrift.ttf", 11),
               fill=(169, 184, 191))
        sheet.paste(img, (column*(w+gap), 0))
    sheet.save(path)


if __name__ == "__main__":
    import sys
    preview(sys.argv[1]) if len(sys.argv) > 1 else build()
