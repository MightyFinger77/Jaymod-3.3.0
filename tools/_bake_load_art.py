"""Build load-screen coin + camp_side from the original coin art.

Do not recolor letter pixels. Erase the old gradient word, then draw a
clean high-res ^xJay^4mod (Jay orange, mod blue) over the shirt.
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from zipfile import ZipFile
import math
import os
import io
import shutil

ASSETS = r"C:\Users\npere\.cursor\projects\c-projects-JaymodFork\assets"
ROOT = r"C:\projects\JaymodFork\3.1.0"
PAK0 = r"C:\Program Files\ETLegacy\etmain\pak0.pk3"
WORDMARK = os.path.join(
    ASSETS,
    "c__Users_npere_AppData_Roaming_Cursor_User_workspaceStorage_"
    "8a4efb3f062befc9d2f182a97cc3c1f1_images_image-ae6df702-c112-4065-b61f-18d19531b68c.png",
)

# ET g_color_table: ^x = index 8 orange, ^4 = blue
ORANGE = (255, 128, 0)
BLUE = (0, 0, 255)


def circular_alpha(im, feather=6.0):
    im = im.convert("RGBA")
    w, h = im.size
    cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
    r = min(w, h) / 2.0 - 1.0
    px = im.load()
    for y in range(h):
        for x in range(w):
            d = math.hypot(x - cx, y - cy)
            r0, g0, b0, a0 = px[x, y]
            if d >= r:
                a = 0
            elif d > r - feather:
                a = int(round(a0 * (r - d) / feather))
            else:
                a = a0
            px[x, y] = (r0, g0, b0, a)
    return im


# Original 1024 coin: valley between y and m (not the hole in M).
SPLIT_X = 528
LETTER_BOX = (390, 560, 720, 745)


def stamp_jaymod(original):
    """Keep original letter silhouettes. Fill each column's letter span so the
    desaturated blue→orange mid-band cannot survive as a gray stripe.
    Jay = ^x orange, mod = ^4 blue, split after y.
    """
    orig = original.convert("RGB")
    out = orig.convert("RGBA")
    ox = orig.load()
    px = out.load()
    x0, y0, x1, y1 = LETTER_BOX
    spans = {}
    for x in range(x0, x1):
        ys = []
        for y in range(y0, y1):
            r, g, b = ox[x, y]
            chroma = max(r, g, b) - min(r, g, b)
            if chroma > 28 and max(r, g, b) > 50:
                ys.append(y)
        if len(ys) >= 6:
            spans[x] = (min(ys), max(ys))

    def put(x, y, tgt, cover):
        sr, sg, sb, sa = px[x, y]
        nr = int(round(sr * (1.0 - cover) + tgt[0] * cover))
        ng = int(round(sg * (1.0 - cover) + tgt[1] * cover))
        nb = int(round(sb * (1.0 - cover) + tgt[2] * cover))
        px[x, y] = (
            0 if nr < 0 else 255 if nr > 255 else nr,
            0 if ng < 0 else 255 if ng > 255 else ng,
            0 if nb < 0 else 255 if nb > 255 else nb,
            255,
        )

    xs = sorted(spans)
    edge = set()
    for i, x in enumerate(xs):
        if i == 0 or xs[i - 1] != x - 1:
            edge.add(x)
        if i == len(xs) - 1 or xs[i + 1] != x + 1:
            edge.add(x)

    for x, (yt, yb) in spans.items():
        tgt = ORANGE if x < SPLIT_X else BLUE
        side = 0.62 if x in edge else 1.0
        for y in range(yt + 1, yb):
            put(x, y, tgt, side)
        put(x, yt, tgt, 0.5 * side)
        put(x, yb, tgt, 0.5 * side)
    print("letter columns", len(spans), "x", min(spans), max(spans) if spans else None)
    return out


def flood_circle(im, seed, max_sum=55):
    w, h = im.size
    px = im.load()
    sx, sy = seed
    if sum(px[sx, sy][:3]) > max_sum:
        found = None
        for y in range(sy, 0, -1):
            if sum(px[sx, y][:3]) <= max_sum:
                found = (sx, y)
                break
        if not found:
            raise SystemExit("no dark seed")
        sx, sy = found
    seen = set()
    stack = [(sx, sy)]
    xs, ys = [], []
    while stack:
        x, y = stack.pop()
        if (x, y) in seen:
            continue
        if x < 0 or y < 0 or x >= w or y >= h:
            continue
        if sum(px[x, y][:3]) > max_sum:
            continue
        seen.add((x, y))
        xs.append(x)
        ys.append(y)
        stack.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    cx = sum(xs) / len(xs)
    cy = sum(ys) / len(ys)
    rmax = max(math.hypot(x - cx, y - cy) for x, y in zip(xs, ys))
    print("hole n", len(xs), "center", round(cx, 1), round(cy, 1), "r_max", round(rmax, 1))
    return cx, cy, rmax


def find_slot_hud(panel):
    w, h = panel.size
    px = panel.load()
    dark = []
    for y in range(int(h * 0.78), int(h * 0.98)):
        if sum(px[w // 2, y][:3]) > 40:
            continue
        run = best = bl = br = rs = 0
        for x in range(16, w - 16):
            if sum(px[x, y][:3]) < 40:
                if run == 0:
                    rs = x
                run += 1
                if run > best:
                    best = run
                    bl, br = rs, x
            else:
                run = 0
        if best > 160:
            dark.append((y, bl, br))
    if not dark:
        return (472.0, 440.0, 136.0, 14.0)
    best_run = []
    cur = [dark[0]]
    for a, b in zip(dark, dark[1:]):
        if b[0] == a[0] + 1:
            cur.append(b)
        else:
            if len(cur) > len(best_run):
                best_run = cur
            cur = [b]
    if len(cur) > len(best_run):
        best_run = cur
    y0, y1 = best_run[0][0], best_run[-1][0]
    left = int(sum(r[1] for r in best_run) / len(best_run))
    right = int(sum(r[2] for r in best_run) / len(best_run))
    hx = 440 + left * 200 / w
    hy = y0 * 480 / h
    hw = (right - left) * 200 / w
    hh = max(12.0, (y1 - y0 + 1) * 480 / h)
    return (hx, hy, hw, hh)


def find_plaque_hud(panel):
    """Inner brushed plate, in 640x480 HUD pixels."""
    w, h = panel.size
    px = panel.load()
    # Skip porthole (upper ~32%) and slot (lower ~18%).
    y0 = int(h * 0.34)
    y1 = int(h * 0.78)
    # Inner plate is a large mid-luma rectangle, not the rivet frame.
    rows = []
    for y in range(y0, y1):
        run = best = bl = br = rs = 0
        for x in range(8, w - 8):
            s = sum(px[x, y][:3])
            if 90 < s < 280:
                if run == 0:
                    rs = x
                run += 1
                if run > best:
                    best = run
                    bl, br = rs, x
            else:
                run = 0
        if best > int(w * 0.45):
            rows.append((y, bl, br, best))
    if len(rows) < 20:
        return (456.0, 210.0, 168.0, 160.0)
    # longest consecutive y-run
    best_run = []
    cur = [rows[0]]
    for a, b in zip(rows, rows[1:]):
        if b[0] == a[0] + 1:
            cur.append(b)
        else:
            if len(cur) > len(best_run):
                best_run = cur
            cur = [b]
    if len(cur) > len(best_run):
        best_run = cur
    top, bot = best_run[0][0], best_run[-1][0]
    left = int(sum(r[1] for r in best_run) / len(best_run))
    right = int(sum(r[2] for r in best_run) / len(best_run))
    # Inset from the plate bevel so text doesn't sit on the rim.
    pad = 10
    left += pad
    right -= pad
    top += pad
    bot -= pad
    hx = 440 + left * 200 / w
    hy = top * 480 / h
    hw = (right - left) * 200 / w
    hh = (bot - top) * 480 / h
    return (hx, hy, hw, hh)


def build_panel(plaque, coin):
    src = plaque.convert("RGB")
    sw, sh = src.size
    TW, TH = 400, 960
    scale = TW / sw
    scaled = src.resize((TW, int(round(sh * scale))), Image.Resampling.LANCZOS)
    sh2 = scaled.size[1]

    cx_s, cy_s, r_s = flood_circle(scaled.convert("RGBA"), (TW // 2, int(sh2 * 0.18)))
    rivet_m = r_s * 0.42
    top_end = int(min(sh2 - 1, round(cy_s + r_s + rivet_m)))
    slot_start = int(sh2 * 0.80)
    top = scaled.crop((0, 0, TW, top_end))
    mid = scaled.crop((0, top_end, TW, slot_start))
    bot = scaled.crop((0, slot_start, TW, sh2))

    bot_h = bot.size[1]
    bot_y = TH - bot_h
    canvas = Image.new("RGB", (TW, TH), (40, 45, 38))
    canvas.paste(top, (0, 0))
    mid_h = bot_y - top.size[1]
    if mid_h > 0:
        canvas.paste(mid.resize((TW, mid_h), Image.Resampling.LANCZOS), (0, top.size[1]))
    canvas.paste(bot, (0, bot_y))
    print("panel top", top.size, "mid_h", mid_h, "bot", bot.size, "bot_y", bot_y)

    # Fill the inner hole; leave the rivet ring showing.
    diam = int(round(2 * r_s * 1.02))
    cr = coin.resize((diam, diam), Image.Resampling.LANCZOS)
    pxc = int(round(cx_s - diam / 2.0))
    pyc = int(round(cy_s - diam / 2.0))
    out = canvas.convert("RGBA")
    out.paste(cr, (pxc, pyc), cr)
    print("coin diam", diam, "at", pxc, pyc)
    panel = out.convert("RGB")
    slot = find_slot_hud(panel)
    plaque_hud = find_plaque_hud(panel)
    print("slot hud", slot)
    print("plaque hud", plaque_hud)
    return panel, (cx_s, cy_s, r_s), slot, plaque_hud


def font_at(cands, size):
    for p in cands:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def preview_screens(side, slot, plaque_hud, mode):
    pak0 = ZipFile(PAK0)

    def load_pk3(name):
        return Image.open(io.BytesIO(pak0.read(name))).convert("RGBA")

    camp_map = load_pk3("gfx/loading/camp_map.tga")
    pbar_back = load_pk3("gfx/loading/progressbar_back.tga")
    pbar = load_pk3("gfx/loading/progressbar.tga")
    shot = load_pk3("levelshots/battery.tga")
    ff = load_pk3("ui/assets/filter_ff.tga")
    weap = load_pk3("ui/assets/filter_weap.tga")
    al = load_pk3("ui/assets/filter_antilag.tga")
    pin = load_pk3("gfx/loading/pin_shot.tga")

    S = 3
    hud_w, hud_h = 640, 480
    wide_w = int(round(16 / 9 * hud_h))
    off = (wide_w - hud_w) // 2
    canvas = Image.new("RGBA", (wide_w * S, hud_h * S), (37, 44, 37, 255))
    draw = ImageDraw.Draw(canvas)

    def blit(im, x, y, w, h):
        rsz = im.resize((max(1, int(w * S)), max(1, int(h * S))), Image.Resampling.LANCZOS)
        canvas.paste(rsz, (int((off + x) * S), int(y * S)), rsz if rsz.mode == "RGBA" else None)

    blit(camp_map, 0, 0, 440, 480)
    blit(side.convert("RGBA"), 440, 0, 200, 480)

    # Locked to the inner plate / slot on camp_side (400x960 -> 200x480 HUD).
    cx = 540.0
    type_y, name_y, secret_y = 158, 178, 200
    title_y, host_y, motd_y = 222, 240, 268
    icon_y = 386
    # UI connecting flash still uses stock parchment + original type.
    connect_y, connect_text_y = 33, 84
    f_h = font_at([r"C:\Windows\Fonts\courbd.ttf", r"C:\Windows\Fonts\cour.ttf"], int(30 * 0.2 * S))
    f_n = font_at([r"C:\Windows\Fonts\courbd.ttf", r"C:\Windows\Fonts\cour.ttf"], int(30 * 0.30 * S))
    f_t = font_at([r"C:\Windows\Fonts\ariblk.ttf", r"C:\Windows\Fonts\arialbd.ttf"], int(27 * 0.22 * S))
    f_b = font_at([r"C:\Windows\Fonts\courbd.ttf", r"C:\Windows\Fonts\cour.ttf"], int(30 * 0.2 * S))
    f_l = font_at([r"C:\Windows\Fonts\courbd.ttf", r"C:\Windows\Fonts\cour.ttf"], int(30 * 0.22 * S))

    def centre(text, x, y, fnt, fill):
        bbox = draw.textbbox((0, 0), text, font=fnt)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(((off + x) * S - tw / 2, y * S - th), text, font=fnt, fill=fill)

    if mode == "loading":
        blit(shot, 16, 2, 192, 144)
        blit(pin, 96, 8, 20, 20)
        blit(pbar_back, slot[0], slot[1], slot[2], slot[3])
        frac = 0.62
        pbar_crop = pbar.crop((0, 0, max(1, int(pbar.size[0] * frac)), pbar.size[1]))
        blit(pbar_crop, slot[0], slot[1], slot[2] * frac, slot[3])

        centre("Map Voting:", cx, type_y, f_h, (255, 255, 255, 153))
        centre("AE Sniper Challenge", cx, name_y, f_n, (255, 255, 255, 153))
        centre("***TOP SECRET***", cx, secret_y, f_h, (255, 255, 255, 178))
        centre("Jaymod 3.1.0", cx, title_y, f_t, (255, 255, 255, 153))
        centre("~~~[G!X]Jaymod64bit~~~", cx, host_y, f_b, (255, 255, 255, 255))
        y = motd_y
        for line in (
            "Welcome to G!X",
            "Supreme Overlord:",
            "[=G!X=]Conradd[=G!X=]",
            "G!X Supreme & Server",
            "Owner: [=G!X=]Punk!11@",
            "Always recruiting for Fun!!",
            "Website: gixclan.net |",
            "FB: Facebook.com/gixclan",
        ):
            if y > 378:
                break
            centre(line, cx, y, f_b, (255, 255, 255, 255))
            y += 10

        icons = [ff, weap, al]
        icon_size, icon_gap = 16, 8
        n = len(icons)
        row_w = n * icon_size + (n - 1) * icon_gap
        row_x = 440 + (200 - row_w) / 2
        for i, ic in enumerate(icons):
            blit(ic, row_x + i * (icon_size + icon_gap), icon_y, icon_size, icon_size)
        centre("LOADING", 540, slot[1] + slot[3] * 0.72, f_l, (26, 26, 26, 204))
    else:
        def left(text, x, y, fnt, fill):
            bbox = draw.textbbox((0, 0), text, font=fnt)
            th = bbox[3] - bbox[1]
            draw.text(((off + x) * S, y * S - th), text, font=fnt, fill=fill)

        left("CONNECTING...", 470, connect_y, f_n, (255, 255, 255, 153))
        left("Connecting to:", 464, connect_text_y, f_h, (0, 0, 0, 255))
        left("185.143.228.92:27965", 464, connect_text_y + 8, f_b, (0, 0, 0, 255))
        left("*** 2.85.0 Released! ***", 464, connect_text_y + 24, f_b, (0, 0, 0, 255))
        left("Awaiting gamestate...", 464, connect_text_y + 40, f_b, (0, 0, 0, 255))

    return canvas.convert("RGB"), {
        "slot": slot,
        "type_y": type_y,
        "name_y": name_y,
        "secret_y": secret_y,
        "title_y": title_y,
        "host_y": host_y,
        "motd_y": motd_y,
        "icon_y": icon_y,
        "connect_y": connect_y,
        "connect_text_y": connect_text_y,
    }


def main():
    # Original stamped word. Recolor turns it into a sticker.
    src_coin = Image.open(os.path.join(ASSETS, "jaymod-coin-wordmark.png"))
    coin = src_coin.convert("RGBA")
    coin.save(os.path.join(ROOT, "dist", "preview.png"), "PNG", optimize=True)
    coin.save(os.path.join(ASSETS, "jaymod-coin-preview.png"), "PNG", optimize=True)

    circ = circular_alpha(coin)
    coin256 = circ.resize((256, 256), Image.Resampling.LANCZOS)
    coin_path = os.path.join(ROOT, "pak", "gfx", "loading", "jaymod_coin.png")
    os.makedirs(os.path.dirname(coin_path), exist_ok=True)
    coin256.save(coin_path, "PNG", optimize=True)

    plaque = Image.open(os.path.join(ASSETS, "camp-side-tall-plaque.png"))
    panel, hole, slot, plaque_hud = build_panel(plaque, circ)

    side_png = os.path.join(ROOT, "pak", "gfx", "loading", "camp_side.png")
    side_tga = os.path.join(ROOT, "pak", "gfx", "loading", "camp_side.tga")
    panel.save(side_png, "PNG", optimize=True)
    panel.save(side_tga)

    stage = os.path.join(ROOT, "dist", "pk3stage", "gfx", "loading")
    os.makedirs(stage, exist_ok=True)
    shutil.copy2(coin_path, os.path.join(stage, "jaymod_coin.png"))
    shutil.copy2(side_png, os.path.join(stage, "camp_side.png"))
    shutil.copy2(side_tga, os.path.join(stage, "camp_side.tga"))

    loading, layout = preview_screens(panel, slot, plaque_hud, "loading")
    with ZipFile(PAK0) as pak0:
        vanilla_side = Image.open(io.BytesIO(pak0.read("gfx/loading/camp_side.tga"))).convert("RGBA")
    connecting, _ = preview_screens(vanilla_side, slot, plaque_hud, "connecting")
    loading.save(os.path.join(ASSETS, "load-preview-loading.png"), "PNG", optimize=True)
    connecting.save(os.path.join(ASSETS, "load-preview-connecting.png"), "PNG", optimize=True)
    print("layout", layout)
    print("ok", hole)


if __name__ == "__main__":
    main()
