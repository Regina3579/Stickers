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
  - Friendship stickers from the transparent PNGs in Design/Friendship/.
  - Sisters stickers from Design/Sisters/ (one PNG and two sticker sheets).

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
SHEET_MARGIN = 10              # Wide sheet stickers use less space, so they show bigger.

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


# Sisters sticker sheets (Design/Sisters/): row bands and how many stickers each row holds.
SIS_A, SIS_A_ROWS = "Sisters/sheet-1.jpg", [(0, 512, 5), (512, 1024, 5)]
SIS_B, SIS_B_ROWS = "Sisters/sheet-2.jpg", [(0, 395, 4), (395, 750, 4), (750, 1100, 2)]


# --------------------------------------------------------------------------- sticker specs

def emoji(folder, emojis, name, keywords="", skin=False):
    return {"kind": "fluent", "folder": folder, "skin": skin, "emojis": emojis.split(),
            "name": name, "keywords": keywords}


def text(label, emojis, name, keywords="", style="bubble"):
    return {"kind": "text", "label": label, "style": style, "emojis": emojis.split(),
            "name": name, "keywords": keywords}


def art(box, emojis, name, keywords=""):
    return {"kind": "art", "box": box, "emojis": emojis.split(), "name": name, "keywords": keywords}


def png(file, emojis, name, keywords, label=None, description=None, index=None, count=None):
    """A sticker drawn on a transparent background, stored in Design/. For a transparent
    sheet holding several stickers, `index` picks one (reading order, 0-based) and `count`
    says how many stickers the sheet holds, so stickers that touch can be told apart."""
    return {"kind": "png", "file": file, "index": index, "count": count, "emojis": emojis.split(),
            "name": name, "keywords": keywords, "label": label, "description": description}


def grid(file, rows, index, emojis, name, keywords, label=None, description=None):
    """Sticker number `index` (reading order) from a sticker sheet laid out in rows.
    `rows` lists (top, bottom, columns) in sheet pixels; each row is split into equal columns."""
    return {"kind": "grid", "file": file, "rows": rows, "index": index, "emojis": emojis.split(),
            "name": name, "keywords": keywords, "label": label, "description": description}


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
            png("Friendship/01-bff-girls.png", "👭 💖", "BFF Girls", "bff best friends girls wink", label="BFF"),
            png("Friendship/02-friends-forever.png", "🤗 👭", "Friends Forever", "friends forever hug girls",
                label="Friends Forever"),
            png("Friendship/03-soul-sisters.png", "👭 🌙", "Soul Sisters", "soul sisters moon girls",
                label="Soul Sisters"),
            png("Friendship/04-besties.png", "🤳 👭", "Besties", "besties selfie girls", label="Besties"),
            png("Friendship/05-best-friends-puppies.png", "🐶 💕", "Best Friends Puppies", "best friends puppies dogs",
                label="Best Friends"),
            png("Friendship/06-bff-bear-and-bunny.png", "🧸 🐰", "BFF Bear and Bunny", "bff bear bunny crown",
                label="BFF"),
            png("Friendship/07-happy-friendship-day.png", "🎉 👭", "Happy Friendship Day", "happy friendship day party",
                label="Happy Friendship Day"),
            png("Friendship/08-i-cherish-you.png", "💐 🤗", "I Cherish You", "i cherish you flowers hug",
                label="I Cherish You"),
            png("Friendship/09-sweet-bunnies.png", "🐰 🍦", "Sweet Bunnies", "sweet bunnies ice cream",
                label="Sweet"),
            png("Friendship/10-bestie-squad.png", "👯 ✌️", "Bestie Squad", "bestie squad girls group",
                label="Bestie Squad"),
            png("Friendship/11-love-you-girls.png", "💕 👭", "Love You Bestie", "love you bestie girls",
                label="Love You"),
            png("Friendship/12-sweet-bestie.png", "💖 🎀", "Sweet Bestie", "sweet bestie text", label="Sweet Bestie"),
            png("Friendship/13-friendship-goals.png", "👑 💕", "Friendship Goals", "friendship goals crown text",
                label="Friendship Goals"),
            png("Friendship/14-always-together.png", "💞 ✨", "Always Together", "always together text",
                label="Always Together"),
            png("Friendship/15-bestie-love.png", "💗 🎀", "Bestie Love", "bestie love text", label="Bestie Love"),
            png("Friendship/16-best-friend.png", "💕 🌸", "Best Friend", "best friend text", label="Best Friend"),
            png("Friendship/17-bff-forever.png", "💖 ⭐", "BFF Forever", "bff forever text", label="BFF Forever"),
            png("Friendship/18-soul-sisters-lettering.png", "💜 🌼", "Soul Sisters Lettering", "soul sisters text",
                label="Soul Sisters"),
            png("Friendship/19-bestie-vibes.png", "🎀 ✨", "Bestie Vibes", "bestie vibes text", label="Bestie Vibes"),
            png("Friendship/20-forever-besties.png", "💕 🎀", "Forever Besties", "forever besties text",
                label="Forever Besties"),
            png("Friendship/21-my-girl.png", "💖 🌸", "My Girl", "my girl text", label="My Girl"),
        ],
    },
    {
        "id": "sisters", "title": "Sisters", "subtitle": "Sister love, forever",
        "tint": "#F2805E", "top": "#FFE7DA", "bottom": "#FFF5EE", "ink": ["#FFA07A", "#EE5D7A"],
        "tray": "Crown",
        "stickers": [
            png("Sisters/01-love-you-my-sisi.png", "💖 👭", "Love You My Sisi", "love you my sisi sis sister hug",
                label="Love you my Sisi"),
            grid(SIS_A, SIS_A_ROWS, 0, "💕 🤗", "Love You Sis Cuddle", "love you sis sister cuddle hug",
                 label="I Love You Sis"),
            grid(SIS_A, SIS_A_ROWS, 1, "💗 👭", "My Best Sis Heart", "my best sis sister heart", label="My Best Sis"),
            grid(SIS_A, SIS_A_ROWS, 3, "😘 👭", "Just Sisters Kiss", "just sisters kiss", label="Just Sisters"),
            grid(SIS_A, SIS_A_ROWS, 4, "💞 👭", "Sisters Forever", "sisters forever", label="Sisters Forever"),
            grid(SIS_A, SIS_A_ROWS, 5, "🎀 👭", "Sisterhood Forever", "sisterhood forever sisters",
                 label="Sisterhood forever"),
            grid(SIS_A, SIS_A_ROWS, 6, "🥳 👭", "You're My Sis", "you're my sis sister happy", label="You're My Sis"),
            grid(SIS_A, SIS_A_ROWS, 7, "🤳 👭", "Besties Sisters", "besties sisters selfie", label="Besties Sisters"),
            grid(SIS_A, SIS_A_ROWS, 8, "👑 💖", "Sister Love Heart", "sister love heart crown", label="Sister Love"),
            grid(SIS_A, SIS_A_ROWS, 9, "🐰 🤗", "Always Together Sis", "always together sisters bunny",
                 label="Always Together"),
            grid(SIS_B, SIS_B_ROWS, 1, "💕 👭", "My Best Sis", "my best sis sister", label="My Best Sis"),
            grid(SIS_B, SIS_B_ROWS, 2, "👑 💜", "Best Sis in the World", "best sis in the world crown",
                 label="Best Sis in the World"),
            grid(SIS_B, SIS_B_ROWS, 3, "🤗 👭", "Just Sisters", "just sisters hug", label="Just Sisters"),
            grid(SIS_B, SIS_B_ROWS, 4, "😘 💕", "Sisters Forever Kiss", "sisters forever kiss", label="Sisters Forever"),
            grid(SIS_B, SIS_B_ROWS, 5, "😎 ✌️", "Sisters by Heart", "sisters by heart sunglasses",
                 label="Sisters by heart"),
            grid(SIS_B, SIS_B_ROWS, 7, "☕ 👭", "Better Together", "better together sisters cocoa",
                 label="Better Together"),
            grid(SIS_B, SIS_B_ROWS, 8, "👑 💖", "You're My Sister", "you're my sister heart crown",
                 label="You're My Sister"),
            grid(SIS_B, SIS_B_ROWS, 9, "🐰 💕", "Sisters Make Life Sweeter", "sisters make life sweeter bunny",
                 label="Sisters Make Life Sweeter"),
            png("Sisters/02-partners-in-crime.png", "😎 💕", "Partners in Crime", "partners in crime sisters fun",
                label="Partners in Crime"),
            png("Sisters/03-love-you-forever-and-ever.png", "💖 💜", "Love You Forever and Ever",
                "love you forever and ever sister", label="Love you Forever and Ever"),
            png("Sisters/04-sisters-are-forever-friends.png", "👭 💕", "Sisters Are Forever Friends",
                "sisters are forever friends", label="Sisters are Forever Friends"),
        ],
    },
    {
        "id": "family", "title": "Family", "subtitle": "Home is where the heart is",
        "tint": "#4C97E8", "top": "#E0EEFF", "bottom": "#F2F8FF", "ink": ["#7CB8FF", "#3D7FE0"],
        "tray": "House with garden",
        "stickers": [
            png("Family/sheet-1.png", "👩 ❤️", "Love You Mom", "love you mom mother mum", label="Love you Mom", index=0),
            png("Family/sheet-1.png", "👨‍👩‍👧 ❤️", "Family", "family love heart", label="Family", index=1),
            png("Family/sheet-1.png", "👨 💙", "Love You Dad", "love you dad father", label="Love you Dad", index=2),
            png("Family/sheet-1.png", "👨‍👩‍👧 🤗", "Family Hug", "family hug mom dad",
                description="Mom, dad and their little girl hugging with smiles and hearts", index=3),
            png("Family/sheet-1.png", "🏡 💕", "Home Sweet Home", "home sweet home house",
                label="Home Sweet Home", index=4),
            png("Family/sheet-2.png", "📸 💕", "Memories With Family", "memories family quote", count=8, index=0,
                label="The best thing about memories is making them with family"),
            png("Family/sheet-2.png", "❤️ 👨‍👩‍👧", "I Love My Family", "i love my family", count=8, index=1,
                label="I love my Family"),
            png("Family/sheet-2.png", "😊 👨‍👩‍👧‍👦", "One Big Happy Family", "one big happy family", count=8, index=2,
                label="One Big happy Family"),
            png("Family/sheet-2.png", "💞 👨‍👩‍👧", "We Are Family", "we are family", count=8, index=3,
                label="We are Family"),
            png("Family/sheet-2.png", "📸 😁", "Say Cheese", "say cheese photo camera", count=8, index=4,
                label="Say Cheese!"),
            png("Family/sheet-2.png", "📷 🌼", "Camera", "camera photo flowers", count=8, index=5,
                description="A light blue camera surrounded by white daisies and a pink heart"),
            png("Family/sheet-2.png", "💖 👨‍👩‍👧", "Family Is Everything", "family is everything", count=8, index=6,
                label="Family is Everything"),
            png("Family/sheet-2.png", "🌸 💕", "Every Family Is Beautiful", "every family is beautiful favorite quote",
                count=8, index=7, label="Every family is beautiful but ours is my favorite"),
            png("Family/sheet-3.png", "🏡 💕", "No Place Like Home", "there is no place like home house",
                count=5, index=0, label="There is no place like home"),
            png("Family/sheet-3.png", "💗 🎀", "Family Is Forever", "family is forever heart", count=5, index=1,
                label="Family is Forever"),
            png("Family/sheet-3.png", "☀️ 🎈", "Plays Together Stays Together", "family plays together stays together",
                count=5, index=2, label="A Family that plays together stays together"),
            png("Family/sheet-3.png", "🧵 💗", "Work of the Heart", "families are a work of the heart",
                count=5, index=3, label="Families are a work of the Heart"),
            png("Family/sheet-3.png", "🌳 💕", "Starts and Ends With Family", "it all starts and ends with family tree",
                count=5, index=4, label="It all starts and ends with Family"),
            emoji("House with garden", "🏡", "Home", "home house family"),
            emoji("Bouquet", "💐", "Bouquet", "flowers bouquet mom"),
            emoji("Light blue heart", "🩵", "Blue Heart", "love heart blue"),
            emoji("Sunflower", "🌻", "Sunflower", "flower sunshine"),
            emoji("Birthday cake", "🎂", "Birthday Cake", "birthday cake party"),
            emoji("Dove", "🕊️", "Peace Dove", "peace dove bird"),
            emoji("Folded hands", "🙏", "Blessed", "thank you pray blessed", skin=True),
            emoji("Baby angel", "👼", "Little Angel", "baby angel cute", skin=True),
            emoji("Teapot", "🫖", "Tea Time", "tea family time"),
            emoji("Hibiscus", "🌺", "Hibiscus", "flower"),
        ],
    },
    {
        "id": "feelings", "title": "Emotions", "subtitle": "Say how you feel",
        "tint": "#34B57E", "top": "#E0F7EA", "bottom": "#F3FCF6", "ink": ["#5AD39A", "#22A06B"],
        "tray": "Smiling face with smiling eyes",
        "stickers": [
            png("Emotions/sheet-1.png", "😉 💕", "Winking Star", "wink happy star cute", count=10, index=0,
                description="A pink star with a bow winking happily among hearts"),
            png("Emotions/sheet-1.png", "😊 ⭐", "Happy Star", "happy smile joy star", count=10, index=1,
                description="A yellow star smiling with closed happy eyes"),
            png("Emotions/sheet-1.png", "😢 💧", "Crying Star", "sad cry tears star", count=10, index=2,
                description="A blue star crying with big teary eyes"),
            png("Emotions/sheet-1.png", "😠 💢", "Angry Star", "angry mad grumpy star", count=10, index=3,
                description="A purple star frowning with an angry mark"),
            png("Emotions/sheet-1.png", "😴 💤", "Sleepy Star", "sleepy sleep tired night star", count=10, index=4,
                description="A green star asleep in a striped night cap"),
            png("Emotions/sheet-1.png", "😜 ✨", "Playful Star", "playful wink fun star", count=10, index=5,
                description="An orange star winking playfully with little stars"),
            png("Emotions/sheet-1.png", "😍 💕", "Love Struck Star", "love heart eyes crush star", count=10, index=6,
                description="A pink star with heart eyes surrounded by hearts"),
            png("Emotions/sheet-1.png", "😮 ⭐", "Surprised Star", "surprised shocked wow star", count=10, index=7,
                description="A purple star with wide surprised eyes"),
            png("Emotions/sheet-1.png", "😂 💦", "Laughing Star", "laughing lol haha funny star", count=10, index=8,
                description="A blue star laughing so hard it cries"),
            png("Emotions/sheet-1.png", "💔 😢", "Heartbroken Star", "heartbroken sad broken heart star", count=10,
                index=9, description="A yellow star crying next to a broken heart"),
            png("Emotions/sheet-2.png", "❤️ 😊", "I Love You", "i love you love", count=6, index=0, label="I Love You"),
            png("Emotions/sheet-2.png", "🥺 💭", "I Miss You", "i miss you miss", count=6, index=1, label="I Miss You"),
            png("Emotions/sheet-2.png", "🙏 💐", "Thank You", "thank you thanks", count=6, index=2, label="Thank You"),
            png("Emotions/sheet-2.png", "☀️ 😊", "Good Morning", "good morning morning sun", count=6, index=3,
                label="Good Morning"),
            png("Emotions/sheet-2.png", "🌙 😴", "Good Night", "good night night sleep moon", count=6, index=4,
                label="Good Night"),
            png("Emotions/sheet-2.png", "😄 ✌️", "Be Happy", "be happy smile", count=6, index=5, label="Be Happy"),
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
            text("Sorry", "🥺", "Sorry", "sorry apology"),
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


def die_cut(content: Image.Image, margin: int = MARGIN) -> Image.Image:
    """Centers artwork on a 512 canvas with a white sticker border and a soft shadow."""
    inner = STICKER_SIZE - 2 * (margin + OUTLINE)
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


def painted_checkerboard_alpha(rgb: np.ndarray) -> np.ndarray:
    """Some exports paint the grey "transparency" checkerboard into the picture. Grey pixels
    connected to the image edge are that background; the sticker's white border stops it."""
    rgb = rgb.astype(int)
    low, high = rgb.min(2), rgb.max(2)
    grey = (high - low < 14) & (high < 243)
    labels, _ = ndimage.label(grey)
    edge = np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))
    background = np.isin(labels, edge[edge > 0])
    sticker = ndimage.binary_fill_holes(~background)
    return np.where(sticker, 255, 0).astype(np.uint8)


def reading_order(boxes) -> list[int]:
    """Indices of (left, top, right, bottom) boxes, top row first, left to right in a row."""
    heights = sorted(b[3] - b[1] for b in boxes)
    row_gap = heights[len(heights) // 2] / 2
    by_y = sorted(range(len(boxes)), key=lambda i: (boxes[i][1] + boxes[i][3]) / 2)
    rows, current, row_y = [], [], None
    for i in by_y:
        y = (boxes[i][1] + boxes[i][3]) / 2
        if current and y - row_y > row_gap:
            rows.append(current)
            current = []
        if not current:
            row_y = y
        current.append(i)
    rows.append(current)
    return [i for row in rows for i in sorted(row, key=lambda i: boxes[i][0])]


def cut_png(file: str, index: int | None = None, count: int | None = None) -> Image.Image:
    """Cleans a transparent sticker PNG: drops specks and the faint halo that background
    removal leaves around the edge, then crops to the sticker. With `index`, the file is a
    transparent sheet and only that sticker (reading order) is returned."""
    img = Image.open(DESIGN / file).convert("RGBA")
    pixels = np.asarray(img).copy()
    if pixels[..., 3].min() == 255:
        pixels[..., 3] = painted_checkerboard_alpha(pixels[..., :3])
    alpha = pixels[..., 3]
    solid = alpha > 128
    labels, pieces = ndimage.label(solid)
    sizes = ndimage.sum(solid, labels, range(1, pieces + 1))
    keep = [i + 1 for i in range(pieces) if sizes[i] >= 0.002 * sizes.max()]
    body = np.isin(labels, keep)
    if index is not None:
        # Shrink the stickers until there are `count` separate bodies (stickers whose
        # borders touch split apart), then give every pixel to the nearest body.
        shrink, seeds = 0, body
        while True:
            seed_labels, seed_count = ndimage.label(seeds)
            seed_sizes = ndimage.sum(seeds, seed_labels, range(1, seed_count + 1))
            bodies = [i + 1 for i in range(seed_count) if seed_sizes[i] >= 0.05 * seed_sizes.max()]
            if count is None or len(bodies) >= count or shrink >= 60:
                break
            shrink += 2
            seeds = ndimage.binary_erosion(body, iterations=shrink)
        assert count is None or len(bodies) == count, f"{file}: found {len(bodies)} stickers, expected {count}"
        slices = ndimage.find_objects(seed_labels)
        boxes = [(slices[i - 1][1].start, slices[i - 1][0].start, slices[i - 1][1].stop, slices[i - 1][0].stop)
                 for i in bodies]
        target = bodies[reading_order(boxes)[index]]
        _, (iy, ix) = ndimage.distance_transform_edt(~np.isin(seed_labels, bodies), return_indices=True)
        mine = body & (seed_labels[iy, ix] == target)
        parts, part_count = ndimage.label(mine)
        part_sizes = ndimage.sum(mine, parts, range(1, part_count + 1))
        main = parts == int(np.argmax(part_sizes)) + 1
        near = ndimage.distance_transform_edt(~main) <= 20
        body = np.isin(parts, np.unique(parts[near & mine]))
    pixels[..., 3] = np.where(ndimage.binary_dilation(body, iterations=3), alpha, 0)
    out = Image.fromarray(pixels)
    return out.crop(out.getbbox())


_grid_cache: dict[str, list[Image.Image]] = {}


def cut_grid(file: str, rows) -> list[Image.Image]:
    """Splits a tightly packed sticker sheet using its known row/column layout.
    Every piece of artwork belongs to the grid cell that holds its centre; specks far
    from a sticker's main body are dropped. Returns the stickers in reading order."""
    if file in _grid_cache:
        return _grid_cache[file]
    rgb = np.asarray(Image.open(DESIGN / file).convert("RGB")).astype(int)
    height, width = rgb.shape[:2]
    low, high = rgb.min(2), rgb.max(2)
    art = ~((low > 200) & (high - low < 16))                    # not paper white or its grey shadow
    art = ndimage.binary_opening(art, iterations=1)
    labels, count = ndimage.label(ndimage.binary_dilation(art, iterations=2))
    ids = range(1, count + 1)
    sizes = ndimage.sum(art, labels, ids)
    centres = ndimage.center_of_mass(art, labels, ids)

    cells = [(top, bottom, width * c / cols, width * (c + 1) / cols)
             for top, bottom, cols in rows for c in range(cols)]

    def cell_of(centre):
        y, x = centre
        return next((n for n, (t, b, l, r) in enumerate(cells) if t <= y < b and l <= x < r), None)

    stickers = []
    for n in range(len(cells)):
        pieces = [i + 1 for i in range(count) if sizes[i] >= 30 and cell_of(centres[i]) == n]
        body = np.isin(labels, [i for i in pieces if sizes[i - 1] > 6000])
        assert body.any(), f"{file}: no sticker found in cell {n}"
        near = ndimage.distance_transform_edt(~body) <= 20
        keep = [i for i in pieces if (near & (labels == i)).any()]
        mine = art & np.isin(labels, keep)
        base = ndimage.binary_fill_holes(ndimage.distance_transform_edt(~mine) <= 6)
        alpha = Image.fromarray((base * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1))
        color = rgb.copy()
        paper = (low > 238) & (high - low < 12) & ~ndimage.binary_dilation(mine, iterations=2)
        color[paper] = 255
        out = Image.fromarray(color.astype(np.uint8)).convert("RGBA")
        out.putalpha(alpha)
        stickers.append(out.crop(alpha.getbbox()))
    _grid_cache[file] = stickers
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
        aspects = []
        for spec in pack["stickers"]:
            slug = spec["name"].lower().replace("!", "").replace("'", "").replace("-", " ").replace("  ", " ").replace(" ", "-")
            sticker_id = f"{pack['id']}-{slug}"
            assert sticker_id not in seen, sticker_id
            seen.add(sticker_id)

            if spec["kind"] == "fluent":
                img = die_cut(fluent_image(spec["folder"], spec["skin"]))
                source = "Microsoft Fluent Emoji (MIT)"
            elif spec["kind"] == "text":
                img = text_sticker(spec, pack)
                source = "Text sticker, Fredoka font (OFL)"
            elif spec["kind"] == "png":
                img = die_cut(cut_png(spec["file"], spec.get("index"), spec.get("count")), margin=SHEET_MARGIN)
                source = f"Owner artwork ({spec['file']})"
            elif spec["kind"] == "grid":
                img = die_cut(cut_grid(spec["file"], spec["rows"])[spec["index"]], margin=SHEET_MARGIN)
                source = f"Owner sticker sheet ({spec['file']})"
            elif spec["kind"] == "sheet":
                img = die_cut(cut_sheet(spec["file"])[spec["index"]], margin=SHEET_MARGIN)
                source = f"Love sticker sheet ({spec['file']})"
            else:
                img = art_sticker(spec, reference)
                source = "Stickers landing page illustration"

            box = img.getchannel("A").point(lambda v: 255 if v > 128 else 0).getbbox()
            aspects.append((box[2] - box[0]) / (box[3] - box[1]))
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
            "wideStickers": sum(aspects) / len(aspects) > 1.3,   # the app shows these 2 per row
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
