#!/usr/bin/env python3
"""Generates every image asset used by the Stickers app.

Outputs (all committed to the repo, so Xcode needs nothing extra):
  Shared/StickerLibrary/catalog.json      sticker packs, names, emojis, keywords
  Shared/StickerLibrary/png/*.png         512x512 transparent stickers (copy, drag, iMessage)
  Shared/StickerLibrary/webp/*.webp       512x512 WebP stickers, <= 100 KB (WhatsApp)
  Shared/StickerLibrary/tray/*.png        96x96 tray icons, <= 50 KB (WhatsApp)
  Stickers/Assets.xcassets                app icon, hero, category banners, clouds
  StickersMessages/Assets.xcassets        iMessage app icon

Sticker art:
  - Microsoft Fluent Emoji 3D (MIT license), pinned to one commit.
  - Text stickers drawn with the Fredoka font (SIL Open Font License).
  - Illustrations cut from Design/LandingPage-reference.png.
  - Love stickers cut from Design/Love-sheet-1.png and Love-sheet-2.png.

Usage:  python3 Tools/generate_assets.py      (needs Pillow with WebP support, numpy, scipy)
"""
from __future__ import annotations

import io
import json
import math
import shutil
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
DESIGN = ROOT / "Design"
CACHE = ROOT / "Tools" / ".cache"
LIBRARY = ROOT / "Shared" / "StickerLibrary"
APP_ASSETS = ROOT / "Stickers" / "Assets.xcassets"
MSG_ASSETS = ROOT / "StickersMessages" / "Assets.xcassets"

FLUENT_COMMIT = "1ffb34c752ecf5d402f04cfb4b392c77f57c54bc"
FLUENT_RAW = f"https://raw.githubusercontent.com/microsoft/fluentui-emoji/{FLUENT_COMMIT}/assets/"
FONT_URL = ("https://raw.githubusercontent.com/google/fonts/47d54ca1ebb14fd864695f1d39dc734f39017c33/"
            "ofl/fredoka/Fredoka%5Bwdth%2Cwght%5D.ttf")

STICKER_SIZE = 512             # WhatsApp: exactly 512x512. iMessage: 300...618 px.
TRAY_SIZE = 96                 # WhatsApp tray icon: exactly 96x96.
MAX_WEBP_BYTES = 100 * 1024    # WhatsApp static sticker limit.
MAX_TRAY_BYTES = 50 * 1024     # WhatsApp tray icon limit.
MAX_PNG_BYTES = 500 * 1024     # iMessage MSSticker limit.
OUTLINE = 12                   # White die-cut border (WhatsApp recommends ~8 px).
MARGIN = 22                    # Empty space around the outline.

# Crop boxes inside Design/LandingPage-reference.png (853 x 1844 px).
HERO_BOX = (0, 0, 853, 460)
CLOUDS_BOX = (0, 1700, 853, 1844)
HERO_CHARACTER_BOX = (10, 60, 468, 452)
BANNER_BOXES = {
    "love": (18, 582, 250, 738),
    "friendship": (18, 760, 250, 916),
    "sisters": (18, 938, 250, 1098),
    "family": (18, 1122, 250, 1292),
    "feelings": (18, 1316, 250, 1486),
    "selfcare": (18, 1510, 250, 1696),
}


# --------------------------------------------------------------------------- sticker specs

def emoji(folder, emojis, name, keywords="", skin=False):
    return {"kind": "fluent", "folder": folder, "skin": skin, "emojis": emojis.split(),
            "name": name, "keywords": keywords}


def text(label, emojis, name, keywords="", style="bubble"):
    return {"kind": "text", "label": label, "style": style, "emojis": emojis.split(),
            "name": name, "keywords": keywords}


def art(box, emojis, name, keywords=""):
    return {"kind": "art", "box": box, "emojis": emojis.split(), "name": name, "keywords": keywords}


def sheet(file, index, emojis, name, keywords, label=None, description=None):
    """Sticker number `index` (reading order, 0-based) cut out of a sticker sheet in Design/."""
    return {"kind": "sheet", "file": file, "index": index, "emojis": emojis.split(), "name": name,
            "keywords": keywords, "label": label, "description": description}


PACKS = [
    {
        "id": "love", "title": "Love", "subtitle": "Hearts, hugs and sweet notes",
        "tint": "#F2559A", "top": "#FFE1EE", "bottom": "#FFF4F9", "ink": ["#FF6FAE", "#E0368A"],
        "tray": "Red heart",
        "stickers": [
            sheet("Love-sheet-1.png", 0, "❤️ 🧸", "Love You", "love you teddy bear heart", label="Love You"),
            sheet("Love-sheet-1.png", 1, "💐 💕", "Lots of Love", "lots of love flowers tulips bouquet", label="Lots of Love"),
            sheet("Love-sheet-1.png", 2, "🤗 🐰", "Sending Hugs", "sending hugs bunny heart", label="Sending Hugs"),
            sheet("Love-sheet-1.png", 3, "🤗 🐱", "Big Hugs", "big hugs kittens cats scarf", label="Big Hugs"),
            sheet("Love-sheet-1.png", 4, "💌 💕", "You Are Loved", "you are loved letter envelope hearts", label="You Are Loved"),
            sheet("Love-sheet-1.png", 5, "😘 💕", "Hugs and Kisses", "hugs kisses hearts", label="Hugs & Kisses"),
            sheet("Love-sheet-1.png", 6, "🎈 🐶", "Love Always", "love always puppy balloon", label="Love Always"),
            sheet("Love-sheet-1.png", 7, "🎁 ❤️", "With Love", "with love gift present box", label="With Love"),
            sheet("Love-sheet-1.png", 8, "😘 💋", "XOXO", "xoxo hugs kisses bow", label="XOXO"),
            sheet("Love-sheet-1.png", 9, "☕ 💭", "Thinking of You", "thinking of you cocoa mug", label="Thinking of You"),
            sheet("Love-sheet-2.png", 0, "❤️ 🧸", "Love You More", "love you more teddy bear", label="Love You More"),
            sheet("Love-sheet-2.png", 1, "💕 🐱", "Together Forever", "together forever kittens cats couple", label="Together Forever"),
            sheet("Love-sheet-2.png", 2, "❤️ 🐰", "I Love You", "i love you bunny heart", label="I Love You"),
            sheet("Love-sheet-2.png", 3, "💖 🐶", "Sweetheart", "sweetheart puppy heart", label="Sweetheart"),
            sheet("Love-sheet-2.png", 4, "💌 🧸", "Be Mine", "be mine teddy bear letter", label="Be Mine"),
            sheet("Love-sheet-2.png", 5, "💕 😊", "Happy Hearts", "happy hearts smiling cute",
                  description="Three smiling hearts in pink and purple with white flowers"),
            sheet("Love-sheet-2.png", 6, "💘 😊", "Flying Heart", "flying heart wings happy",
                  description="A happy pink heart with little wings flying among hearts and clouds"),
            sheet("Love-sheet-2.png", 7, "😘 💕", "Blowing Kisses", "blowing kisses kiss heart",
                  description="A pink heart blowing a kiss with small hearts floating away"),
            sheet("Love-sheet-2.png", 8, "💐 💕", "Heart Bouquet", "heart bouquet flowers gift",
                  description="A bouquet of pink, red and purple hearts wrapped with a pink bow"),
            sheet("Love-sheet-2.png", 9, "🤗 ❤️", "Heart Hug", "heart hug hugging cute",
                  description="A red heart hugging a pink heart, both smiling, with flowers"),
        ],
    },
    {
        "id": "friendship", "title": "Friendship", "subtitle": "For your besties",
        "tint": "#A16AE8", "top": "#EEE2FF", "bottom": "#F8F3FF", "ink": ["#C084FC", "#8B3FD9"],
        "tray": "Hugging face",
        "stickers": [
            art(BANNER_BOXES["friendship"], "🤗 👭", "Besties Hug", "friends hug bff girls"),
            text("BFF", "👭 💖", "BFF", "bff best friends forever", style="heart"),
            emoji("Raising hands", "🙌", "High Five", "high five yay celebrate", skin=True),
            text("Best\nFriends", "👭", "Best Friends", "best friends bff"),
            emoji("Ribbon", "🎀", "Pink Bow", "bow ribbon cute"),
            emoji("People hugging", "🫂", "Big Hug", "hug friends"),
            emoji("Handshake", "🤝", "Deal", "handshake deal friends"),
            emoji("Hugging face", "🤗", "Hugs", "hug hugs"),
            emoji("Partying face", "🥳", "Party Time", "party celebrate birthday"),
            emoji("Star-struck", "🤩", "Star-Struck", "wow amazing star"),
            emoji("Bubble tea", "🧋", "Boba Date", "boba bubble tea date"),
            emoji("Balloon", "🎈", "Balloon", "party balloon"),
            emoji("Heart hands", "🫶", "Heart Hands", "love heart hands", skin=True),
            emoji("Clapping hands", "👏", "Clapping", "clap bravo well done", skin=True),
            text("Bestie", "👭", "Bestie", "bestie best friend"),
        ],
    },
    {
        "id": "sisters", "title": "Sisters & Siblings", "subtitle": "Sister love, forever",
        "tint": "#F2805E", "top": "#FFE7DA", "bottom": "#FFF5EE", "ink": ["#FFA07A", "#EE5D7A"],
        "tray": "Crown",
        "stickers": [
            art(BANNER_BOXES["sisters"], "🤗 👭", "Sister Hug", "sister sisters hug siblings"),
            emoji("Crown", "👑", "Crown", "queen princess crown"),
            emoji("Growing heart", "💗", "Growing Heart", "love heart"),
            emoji("Wrapped gift", "🎁", "Gift", "gift present birthday"),
            emoji("Rabbit face", "🐰", "Bunny", "bunny rabbit cute"),
            text("Sis", "👭 💖", "Sis", "sis sister", style="heart"),
            emoji("Princess", "👸", "Princess", "princess sister queen", skin=True),
            emoji("Unicorn", "🦄", "Unicorn", "unicorn magic"),
            emoji("Butterfly", "🦋", "Butterfly", "butterfly pretty"),
            emoji("Cupcake", "🧁", "Cupcake", "cupcake sweet treat"),
            emoji("Lollipop", "🍭", "Lollipop", "candy sweet lollipop"),
            emoji("Cherry blossom", "🌸", "Cherry Blossom", "flower blossom"),
            emoji("Shortcake", "🍰", "Cake Slice", "cake dessert sweet"),
            text("Sister\nLove", "👭 ❤️", "Sister Love", "sister love sis"),
            text("Sibling\nGoals", "👫", "Sibling Goals", "siblings brother sister goals"),
        ],
    },
    {
        "id": "family", "title": "Family Love", "subtitle": "Home is where the heart is",
        "tint": "#4C97E8", "top": "#E0EEFF", "bottom": "#F2F8FF", "ink": ["#7CB8FF", "#3D7FE0"],
        "tray": "House with garden",
        "stickers": [
            art(BANNER_BOXES["family"], "👨‍👩‍👧 🤗", "Family Hug", "family hug mom dad"),
            emoji("House with garden", "🏡", "Home", "home house family"),
            text("Family", "👨‍👩‍👧 ❤️", "Family", "family love", style="heart"),
            emoji("Bouquet", "💐", "Bouquet", "flowers bouquet mom"),
            emoji("Light blue heart", "🩵", "Blue Heart", "love heart blue"),
            emoji("Sunflower", "🌻", "Sunflower", "flower sunshine"),
            emoji("Birthday cake", "🎂", "Birthday Cake", "birthday cake party"),
            emoji("Dove", "🕊️", "Peace Dove", "peace dove bird"),
            emoji("Folded hands", "🙏", "Blessed", "thank you pray blessed", skin=True),
            emoji("Baby angel", "👼", "Little Angel", "baby angel cute", skin=True),
            emoji("Teapot", "🫖", "Tea Time", "tea family time"),
            emoji("Hibiscus", "🌺", "Hibiscus", "flower"),
            text("Love You\nMom", "👩 ❤️", "Love You Mom", "mom mother mum love"),
            text("Love You\nDad", "👨 ❤️", "Love You Dad", "dad father love"),
            text("Home Sweet\nHome", "🏡", "Home Sweet Home", "home sweet home"),
        ],
    },
    {
        "id": "feelings", "title": "Feelings & Emotions", "subtitle": "Say how you feel",
        "tint": "#34B57E", "top": "#E0F7EA", "bottom": "#F3FCF6", "ink": ["#5AD39A", "#22A06B"],
        "tray": "Smiling face with smiling eyes",
        "stickers": [
            art(BANNER_BOXES["feelings"], "😊 😢", "Mood Bubbles", "mood feelings emotions"),
            emoji("Smiling face with smiling eyes", "😊", "Happy", "happy smile"),
            emoji("Smiling face with heart-eyes", "😍", "Heart Eyes", "love heart eyes crush"),
            emoji("Face with tears of joy", "😂", "LOL", "lol laugh funny haha"),
            emoji("Crying face", "😢", "Sad", "sad cry tear"),
            emoji("Loudly crying face", "😭", "Sobbing", "cry sob sad"),
            emoji("Pleading face", "🥺", "Pretty Please", "please puppy eyes"),
            emoji("Face holding back tears", "🥹", "Touched", "touched emotional"),
            emoji("Winking face", "😉", "Wink", "wink flirt"),
            emoji("Grinning squinting face", "😆", "So Funny", "laugh funny"),
            emoji("Relieved face", "😌", "Relieved", "calm relieved peaceful"),
            emoji("Smiling face with halo", "😇", "Angel", "angel innocent"),
            emoji("Smiling face with sunglasses", "😎", "Cool", "cool sunglasses"),
            text("Thank\nYou", "🙏 😊", "Thank You", "thank you thanks"),
            text("Sorry", "🥺", "Sorry", "sorry apology"),
            text("Miss\nYou", "🥺 💖", "Miss You", "miss you"),
        ],
    },
    {
        "id": "selfcare", "title": "Self-Love & Self-Care", "subtitle": "Me time, every time",
        "tint": "#E5579E", "top": "#FCE3F3", "bottom": "#FFF3FA", "ink": ["#F48FC5", "#B45BE0"],
        "tray": "Lotus",
        "stickers": [
            art(BANNER_BOXES["selfcare"], "😌 💆‍♀️", "Peaceful Me", "self care relax calm peaceful"),
            emoji("Lotus", "🪷", "Lotus", "lotus calm zen"),
            emoji("Hot beverage", "☕", "Coffee Break", "coffee break cozy"),
            emoji("Woman in lotus position", "🧘‍♀️", "Yoga", "yoga meditate zen", skin=True),
            emoji("Candle", "🕯️", "Candle", "candle cozy relax"),
            text("Self\nLove", "💖 🌸", "Self Love", "self love", style="heart"),
            emoji("Person taking bath", "🛀", "Bath Time", "bath relax spa", skin=True),
            emoji("Bubbles", "🫧", "Bubbles", "bubbles bath"),
            emoji("Nail polish", "💅", "Nails Done", "nails manicure", skin=True),
            emoji("Lipstick", "💄", "Lipstick", "makeup lipstick"),
            emoji("Tulip", "🌷", "Tulip", "flower tulip"),
            emoji("Sparkles", "✨", "Sparkles", "sparkle glow shine"),
            emoji("Crescent moon", "🌙", "Good Night", "night sleep moon"),
            emoji("Teacup without handle", "🍵", "Green Tea", "tea relax"),
            text("Me\nTime", "💆‍♀️", "Me Time", "me time relax"),
            text("You Got\nThis!", "💪 ✨", "You Got This", "motivation you got this"),
        ],
    },
]


# --------------------------------------------------------------------------- helpers

def fetch(url: str, dest: Path) -> Path:
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=60) as response:
            dest.write_bytes(response.read())
    return dest


def fluent_image(folder: str, skin: bool) -> Image.Image:
    base = folder.lower().replace(" ", "_")
    if skin:
        rel = f"{folder}/Default/3D/{base}_3d_default.png"
    else:
        rel = f"{folder}/3D/{base}_3d.png"
    path = fetch(FLUENT_RAW + urllib.parse.quote(rel), CACHE / "fluent" / f"{base}.png")
    return Image.open(path).convert("RGBA")


def font(size: int) -> ImageFont.FreeTypeFont:
    path = fetch(FONT_URL, CACHE / "Fredoka.ttf")
    f = ImageFont.truetype(str(path), size)
    axes = f.get_variation_axes()
    f.set_variation_by_axes([100 if a["name"] in (b"Width", "Width") else 700 for a in axes])
    return f


def hex_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def vertical_gradient(size, top, bottom) -> Image.Image:
    w, h = size
    column = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(h - 1, 1)
        column.putpixel((0, y), tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)))
    return column.resize((w, h))


def fit(img: Image.Image, box: int) -> Image.Image:
    bbox = img.getbbox()
    img = img.crop(bbox) if bbox else img
    scale = box / max(img.size)
    return img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))),
                      Image.LANCZOS)


def die_cut(content: Image.Image) -> Image.Image:
    """Centers artwork on a 512 canvas with a white sticker border and a soft shadow."""
    inner = STICKER_SIZE - 2 * (MARGIN + OUTLINE)
    content = fit(content, inner)
    layer = Image.new("RGBA", (STICKER_SIZE, STICKER_SIZE), (0, 0, 0, 0))
    layer.paste(content, ((STICKER_SIZE - content.width) // 2, (STICKER_SIZE - content.height) // 2))

    alpha = layer.getchannel("A").point(lambda a: 255 if a > 24 else 0)
    border = alpha.filter(ImageFilter.MaxFilter(2 * OUTLINE + 1))
    border = border.filter(ImageFilter.GaussianBlur(1.4)).point(lambda a: 0 if a < 70 else min(255, a * 2))

    shadow = border.filter(ImageFilter.GaussianBlur(7)).point(lambda a: a * 30 // 100)
    out = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    out.paste((150, 70, 130, 255), (0, 5), shadow)
    out.alpha_composite(Image.merge("RGBA", (*Image.new("RGB", layer.size, "white").split(), border)))
    out.alpha_composite(layer)
    return out


def heart_mask(size: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    points = []
    for i in range(720):
        t = 2 * math.pi * i / 720
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        points.append((size / 2 + x * size / 34, size * 0.46 - y * size / 34))
    ImageDraw.Draw(mask).polygon(points, fill=255)
    return mask


def text_layer(label: str, colors, size: int, max_width: int) -> Image.Image:
    lines = label.split("\n")
    while True:
        f = font(size)
        widths = [f.getbbox(line)[2] - f.getbbox(line)[0] for line in lines]
        if max(widths) <= max_width or size < 40:
            break
        size -= 6
    line_h = int(size * 1.02)
    w, h = max(widths) + 40, line_h * len(lines) + 40
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    for i, line in enumerate(lines):
        draw.text((w / 2, 20 + line_h * i + line_h / 2), line, font=f, fill=255, anchor="mm")
    return mask


def text_sticker(spec, pack) -> Image.Image:
    top, bottom = (hex_rgb(c) for c in pack["ink"])
    s = 1024
    canvas = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    if spec["style"] == "heart":
        heart = heart_mask(s)
        canvas.paste(vertical_gradient((s, s), top, bottom), (0, 0), heart)
        gloss = Image.new("L", (s, s), 0)
        ImageDraw.Draw(gloss).ellipse((s * 0.2, s * 0.14, s * 0.46, s * 0.3), fill=110)
        gloss = ImageChops.multiply(gloss.filter(ImageFilter.GaussianBlur(18)), heart)
        canvas.paste((255, 255, 255, 255), (0, 0), gloss)
        mask = text_layer(spec["label"], pack["ink"], 230, int(s * 0.62))
        mask = mask.rotate(-8, resample=Image.BICUBIC, expand=True)
        stroke = mask.filter(ImageFilter.MaxFilter(17))
        x, y = (s - mask.width) // 2, int(s * 0.47) - mask.height // 2
        canvas.paste(bottom + (255,), (x, y), stroke)
        canvas.paste((255, 255, 255, 255), (x, y), mask)
    else:
        mask = text_layer(spec["label"], pack["ink"], 250, int(s * 0.74))
        pad, edge = 44, 60
        bw, bh = mask.width + 2 * pad, mask.height + 2 * pad
        card = Image.new("RGBA", (bw + 2 * edge, bh + 2 * edge), (0, 0, 0, 0))
        box = (edge, edge, edge + bw, edge + bh)
        shape = Image.new("L", card.size, 0)
        ImageDraw.Draw(shape).rounded_rectangle(box, min(bh // 2, 150), fill=255)
        card.paste(top + (255,), (0, 0), shape)
        inner = Image.new("L", card.size, 0)
        ImageDraw.Draw(inner).rounded_rectangle((box[0] + 12, box[1] + 12, box[2] - 12, box[3] - 12),
                                                min(bh // 2, 150) - 12, fill=255)
        card.paste(vertical_gradient(card.size, (255, 255, 255), hex_rgb(pack["top"])), (0, 0), inner)
        x, y = edge + pad, edge + pad
        card.paste(bottom + (255,), (x, y + 8), mask.filter(ImageFilter.MaxFilter(7)))
        card.paste(vertical_gradient(mask.size, top, bottom), (x, y), mask)
        heart = heart_mask(150)
        card.paste(vertical_gradient((150, 150), top, bottom), (box[2] - 110, box[1] - 50), heart)
        canvas = card.rotate(5, resample=Image.BICUBIC, expand=True)
    return die_cut(canvas)


def rounded(img: Image.Image, radius: int) -> Image.Image:
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, img.width - 1, img.height - 1), radius, fill=255)
    out = img.convert("RGBA")
    out.putalpha(mask)
    return out


def art_sticker(spec, reference: Image.Image) -> Image.Image:
    crop = reference.crop(spec["box"])
    scale = 2.2
    crop = crop.resize((round(crop.width * scale), round(crop.height * scale)), Image.LANCZOS)
    return die_cut(rounded(crop, 60))


_sheet_cache: dict[str, list[Image.Image]] = {}


def cut_sheet(file: str) -> list[Image.Image]:
    """Splits a sticker sheet (die-cut stickers on a near-white page) into its stickers,
    in reading order. Each result is the artwork with a thin white base and no background."""
    if file in _sheet_cache:
        return _sheet_cache[file]
    rgb = np.asarray(Image.open(DESIGN / file).convert("RGB")).astype(int)
    low, high = rgb.min(2), rgb.max(2)
    art = ~((low > 200) & (high - low < 16))                    # not paper white or its grey shadow
    art = ndimage.binary_opening(art, iterations=1)

    labels, count = ndimage.label(ndimage.binary_dilation(art, iterations=5))
    sizes = ndimage.sum(art, labels, range(1, count + 1))
    boxes = ndimage.find_objects(labels)

    # Large pieces are sticker bodies; pieces whose boxes overlap belong to one sticker.
    groups: list[dict] = []
    for i in (i for i in range(count) if sizes[i] > 6000):
        y, x = boxes[i]
        box = [x.start, y.start, x.stop, y.stop]
        for g in groups:
            b = g["box"]
            if box[0] < b[2] and b[0] < box[2] and box[1] < b[3] and b[1] < box[3]:
                g["ids"].append(i + 1)
                g["box"] = [min(b[0], box[0]), min(b[1], box[1]), max(b[2], box[2]), max(b[3], box[3])]
                break
        else:
            groups.append({"ids": [i + 1], "box": box})
    assert len(groups) == 10, f"{file}: found {len(groups)} stickers, expected 10"

    # Small pieces (floating hearts, sparkles) join the nearest sticker body.
    nearest = np.zeros(labels.shape, dtype=int)
    distance = np.full(labels.shape, np.inf)
    for n, g in enumerate(groups):
        d = ndimage.distance_transform_edt(~np.isin(labels, g["ids"]))
        closer = d < distance
        nearest[closer], distance[closer] = n, d[closer]
    piece_size = np.concatenate([[0], sizes])[labels]
    keep = (labels > 0) & (piece_size >= 30) & (distance <= 20)    # drop specks and stray bits
    owner = np.where(keep, nearest, -1)

    # Reading order: top to bottom in rows of two, left to right.
    order = sorted(range(10), key=lambda n: (groups[n]["box"][1] + groups[n]["box"][3]) / 2)
    order = [n for row in range(5)
             for n in sorted(order[2 * row:2 * row + 2], key=lambda n: groups[n]["box"][0])]

    stickers = []
    for n in order:
        mine = art & (owner == n)
        base = ndimage.binary_fill_holes(ndimage.distance_transform_edt(~mine) <= 6)
        alpha = Image.fromarray((base * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1))
        color = rgb.copy()
        paper = (low > 238) & (high - low < 12) & ~ndimage.binary_dilation(mine, iterations=2)
        color[paper] = 255                                      # clean white base, no page tint
        out = Image.fromarray(color.astype(np.uint8)).convert("RGBA")
        out.putalpha(alpha)
        stickers.append(out.crop(alpha.getbbox()))
    _sheet_cache[file] = stickers
    return stickers


def save_webp(img: Image.Image, path: Path) -> int:
    for quality in (90, 85, 80, 75, 70, 60, 50):
        buffer = io.BytesIO()
        img.save(buffer, "WEBP", quality=quality, method=6)
        if buffer.tell() <= MAX_WEBP_BYTES:
            path.write_bytes(buffer.getvalue())
            return buffer.tell()
    raise SystemExit(f"{path.name}: WebP is larger than 100 KB")


def save_png(img: Image.Image, path: Path, limit: int) -> int:
    img.save(path, "PNG", optimize=True)
    size = path.stat().st_size
    if size > limit:
        img.quantize(256, method=Image.Quantize.FASTOCTREE).save(path, "PNG", optimize=True)
        size = path.stat().st_size
    if size > limit:
        raise SystemExit(f"{path.name}: {size} bytes is over the {limit} byte limit")
    return size


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def image_set(name: str, img: Image.Image, scale: str = "2x") -> None:
    folder = APP_ASSETS / f"{name}.imageset"
    folder.mkdir(parents=True, exist_ok=True)
    img.save(folder / f"{name}.png", "PNG", optimize=True)
    write_json(folder / "Contents.json", {
        "images": [{"filename": f"{name}.png", "idiom": "universal", "scale": scale}],
        "info": {"author": "xcode", "version": 1},
    })


# --------------------------------------------------------------------------- icons

def app_icon() -> Image.Image:
    """Full-bleed 1024 icon: iOS applies its own rounded mask, so the source's white
    corners and shadow are cropped away and the corners are refilled with the pink."""
    src = Image.open(DESIGN / "AppIcon-source.png").convert("RGB")
    left, top, right, bottom = 50, 57, 1203, 1196        # pink rounded square
    square = src.crop((left, top, right, bottom)).resize((1024, 1024), Image.LANCZOS)
    mask = Image.new("L", square.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((26, 26, 997, 997), 250, fill=255)
    small = square.resize((64, 64), Image.BILINEAR)
    small_mask = mask.resize((64, 64), Image.BILINEAR)
    fill = small.copy()
    for _ in range(40):                                     # spread pink into the corners
        grown = fill.filter(ImageFilter.BoxBlur(2))
        fill = Image.composite(small, grown, small_mask.point(lambda a: 255 if a > 250 else 0))
    fill = fill.resize(square.size, Image.BICUBIC).filter(ImageFilter.GaussianBlur(6))
    return Image.composite(square, fill, mask.filter(ImageFilter.GaussianBlur(4)))


def write_app_icon(icon: Image.Image) -> None:
    folder = APP_ASSETS / "AppIcon.appiconset"
    folder.mkdir(parents=True, exist_ok=True)
    icon.save(folder / "AppIcon-1024.png", "PNG", optimize=True)
    write_json(folder / "Contents.json", {
        "images": [{"filename": "AppIcon-1024.png", "idiom": "universal",
                    "platform": "ios", "size": "1024x1024"}],
        "info": {"author": "xcode", "version": 1},
    })


def write_messages_icon(icon: Image.Image) -> None:
    """Messages extension icon set (Apple: Asset Catalog Format, Messages Extension Icon Type)."""
    wide = icon.resize((1024, 768), Image.BICUBIC).filter(ImageFilter.GaussianBlur(40))
    center = icon.resize((768, 768), Image.LANCZOS)
    feather = Image.new("L", (768, 768), 0)
    ImageDraw.Draw(feather).rectangle((40, 0, 727, 767), fill=255)
    wide.paste(center, (128, 0), feather.filter(ImageFilter.GaussianBlur(28)))

    slots = [  # (idiom, size in points, scale, platform)
        ("iphone", "29x29", 2, None), ("iphone", "29x29", 3, None),
        ("iphone", "60x45", 2, None), ("iphone", "60x45", 3, None),
        ("ipad", "29x29", 2, None), ("ipad", "67x50", 2, None), ("ipad", "74x55", 2, None),
        ("ios-marketing", "1024x1024", 1, None),
        ("universal", "27x20", 2, "ios"), ("universal", "27x20", 3, "ios"),
        ("universal", "32x24", 2, "ios"), ("universal", "32x24", 3, "ios"),
        ("ios-marketing", "1024x768", 1, "ios"),
    ]
    folder = MSG_ASSETS / "iMessage App Icon.stickersiconset"
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    images = []
    for idiom, size, scale, platform in slots:
        w, h = (float(v) for v in size.split("x"))
        px = (round(w * scale), round(h * scale))
        name = f"icon-{idiom}-{size}@{scale}x.png"
        source = icon if px[0] == px[1] else wide
        source.resize(px, Image.LANCZOS).save(folder / name, "PNG", optimize=True)
        entry = {"filename": name, "idiom": idiom, "scale": f"{scale}x", "size": size}
        if platform:
            entry["platform"] = platform
        images.append(entry)
    write_json(folder / "Contents.json", {"images": images, "info": {"author": "xcode", "version": 1}})


# --------------------------------------------------------------------------- main

def main() -> None:
    reference = Image.open(DESIGN / "LandingPage-reference.png").convert("RGB")

    for sub in ("png", "webp", "tray"):
        if (LIBRARY / sub).exists():
            shutil.rmtree(LIBRARY / sub)
        (LIBRARY / sub).mkdir(parents=True)

    catalog = {"publisher": "Stickers App", "packs": []}
    seen = set()
    for pack in PACKS:
        assert 3 <= len(pack["stickers"]) <= 30, "WhatsApp packs need 3...30 stickers"
        stickers = []
        for spec in pack["stickers"]:
            slug = spec["name"].lower().replace("!", "").replace("-", " ").replace("  ", " ").replace(" ", "-")
            sticker_id = f"{pack['id']}-{slug}"
            assert sticker_id not in seen, sticker_id
            seen.add(sticker_id)

            if spec["kind"] == "fluent":
                img = die_cut(fluent_image(spec["folder"], spec["skin"]))
                source = "Microsoft Fluent Emoji (MIT)"
            elif spec["kind"] == "text":
                img = text_sticker(spec, pack)
                source = "Text sticker, Fredoka font (OFL)"
            elif spec["kind"] == "sheet":
                img = die_cut(cut_sheet(spec["file"])[spec["index"]])
                source = f"Love sticker sheet ({spec['file']})"
            else:
                img = art_sticker(spec, reference)
                source = "Stickers landing page illustration"

            png_size = save_png(img, LIBRARY / "png" / f"{sticker_id}.png", MAX_PNG_BYTES)
            webp_size = save_webp(img, LIBRARY / "webp" / f"{sticker_id}.webp")
            label = spec["label"].replace("\n", " ") if spec.get("label") else None
            accessibility = (f'Sticker with text that reads "{label}" in English' if label
                             else spec.get("description") or f"{spec['name']} sticker")
            stickers.append({
                "id": sticker_id,
                "name": spec["name"],
                "emojis": spec["emojis"][:3],
                "keywords": spec["keywords"].split(),
                "accessibilityText": accessibility[:125],
                "source": source,
            })
            print(f"  {sticker_id:<34} png {png_size // 1024:>3} KB   webp {webp_size // 1024:>3} KB")

        tray = fit(fluent_image(pack["tray"], False), TRAY_SIZE - 8)
        tray_canvas = Image.new("RGBA", (TRAY_SIZE, TRAY_SIZE), (0, 0, 0, 0))
        tray_canvas.paste(tray, ((TRAY_SIZE - tray.width) // 2, (TRAY_SIZE - tray.height) // 2), tray)
        save_png(tray_canvas, LIBRARY / "tray" / f"{pack['id']}.png", MAX_TRAY_BYTES)

        catalog["packs"].append({
            "id": pack["id"],
            "title": pack["title"],
            "subtitle": pack["subtitle"],
            "banner": f"Banner-{pack['id']}",
            "colors": {"tint": pack["tint"], "top": pack["top"], "bottom": pack["bottom"]},
            "stickers": stickers,
        })

        image_set(f"Banner-{pack['id']}", reference.crop(BANNER_BOXES[pack["id"]]))

    write_json(LIBRARY / "catalog.json", catalog)

    image_set("Hero", reference.crop(HERO_BOX))
    image_set("CloudsFooter", reference.crop(CLOUDS_BOX))

    icon = app_icon()
    write_app_icon(icon)
    write_messages_icon(icon)
    print(f"Done: {len(seen)} stickers in {len(PACKS)} packs.")


if __name__ == "__main__":
    main()
