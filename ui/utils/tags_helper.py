"""
Automatic Tag Generator & Fun Dark-Mode Badge Formatter for Brawlhalla Mod Loader
"""

from typing import List, Tuple, Optional

# Rich, vibrant, diverse 32-color dark-mode palette
CATEGORY_PALETTE = [
    "#1b2a4a", # Deep Royal Blue
    "#2b1b4d", # Dark Neon Violet
    "#103b2b", # Cyber Emerald
    "#4d1b28", # Crimson Ruby
    "#1a1c4d", # Midnight Indigo
    "#4a1b47", # Dark Magenta
    "#1b3b4d", # Electric Dark Teal
    "#4d1b38", # Dark Cyber Pink
    "#103d3d", # Dark Turquoise
    "#361b4d", # Dark Plum
    "#282f76", # Dark Sapphire
    "#323f99", # Dark Electric Blue
    "#14384a", # Steel Blue
    "#38144a", # Orchid
    "#4a1428", # Rose
    "#144a38", # Dark Mint
    "#4d3810", # Dark Golden Amber
    "#4d2a10", # Dark Burnt Orange
    "#3d4d10", # Dark Lime / Neon Olive
    "#4d4510", # Dark Vivid Yellow / Gold
    "#104d45", # Dark Aquamarine
    "#45104d", # Dark Fuchsia
    "#4d102a", # Dark Coral Pink
    "#2a4d10", # Dark Forest Lime
    "#384d10", # Dark Citron Green
    "#4d3310", # Dark Bright Orange
    "#104d33", # Dark Spring Green
    "#102a4d", # Deep Ocean Blue
    "#4d103b", # Dark Hot Pink
    "#33104d", # Deep Purple Cyan
    "#4d4010", # Dark Brass Yellow
    "#104d20", # Vivid Deep Green
]

# Exact user-specified color mappings:
# - Legend Skin / Legend Skins -> Dark Blue (#1b2a4a)
# - Weapon Skin / Weapon Skins -> Green (#103b2b)
# - UI                         -> Dark Yellow (#5c4a10)
# - Effects                    -> Dark Crimson (#4d1b28)
# - Maps / Realms              -> Dark Green (#164e37)
CATEGORY_COLOR_MAP = {
    "legend skin":  "#1b2a4a",
    "legend skins": "#1b2a4a",
    "weapon skin":  "#103b2b",
    "weapon skins": "#103b2b",
    "weapons":      "#103b2b",
    "ui":           "#5c4a10",
    "effects":      "#4d1b28",
    "map":          "#164e37",
    "maps":         "#164e37",
    "realms":       "#164e37",
}

# Tag Normalization Map (Collapse Plurals & Singulars into single category)
TAG_NORMALIZATION = {
    "legend skins": "Legend Skin",
    "legend skin":  "Legend Skin",
    "weapon skins": "Weapon Skin",
    "weapon skin":  "Weapon Skin",
    "weapons":      "Weapon Skin",
    "realms":       "Map",
    "maps":         "Map",
    "map":          "Map",
}


def normalize_tag(tag: str) -> str:
    key = str(tag).strip().lower()
    return TAG_NORMALIZATION.get(key, str(tag).strip())


OFFICIAL_USER_LEGENDS = [
    'Ada', 'Arcadia', 'Artemis', 'Asuri', 'Aurus', 'Azoth', 'Barraza', 'Bödvar',
    'Bodvar', 'Brynn', 'Caspian', 'Cassidy', 'Cross', 'Diana', 'Dusk', 'Ember',
    'Ezio', 'Fait', 'Gnash', 'Hattori', 'Imugi', 'Isaiah', 'Jaeyun', 'Jhala',
    'Jiro', 'Kaya', 'Koji', 'Kor', 'Lin Fei', 'Loki', 'Lucien', 'Magyar', 'Mako',
    'Mirage', 'Mordex', 'Munin', 'Queen Nai', 'Nix', 'Onyx', 'Orion', 'Petra',
    'Priya', 'Ragnir', 'Ransom', 'Rayman', 'Red Raptor', 'Reno', 'Sir Roland',
    'Roland', 'Rupture', 'Scarlet', 'Sentinel', 'Seven', 'Sidra', 'Teros',
    'Tezca', 'Thatch', 'Thea', 'Thor', 'Ulgrim', 'Val', 'Vector', 'Lady Vera',
    'Vivi', 'Volkov', 'Lord Vraxx', 'Vraxx', 'Wu Shang', 'Xull', 'Yumiko',
    'Zariel', 'King Zuva'
]


def get_all_legends(lang_reader=None) -> List[str]:
    legends = list(OFFICIAL_USER_LEGENDS)
    seen = {l.lower() for l in legends}

    if lang_reader and hasattr(lang_reader, 'translations'):
        trans = lang_reader.translations.get('en', {})
        for k, v in trans.items():
            if k.startswith('HeroType_') and ('_BioQuoteFromAttrib' in k or '_BioName' in k):
                val = v.strip().lstrip('-').strip()
                if val and len(val) < 25 and ' ' not in val and val.lower() not in seen:
                    legends.append(val)
                    seen.add(val.lower())

    return legends


def get_category_color(name: str) -> str:
    if not name:
        return "#1b2a4a"
    key = str(name).strip().lower()
    if key in CATEGORY_COLOR_MAP:
        return CATEGORY_COLOR_MAP[key]
    h = sum(ord(c) for c in str(name))
    return CATEGORY_PALETTE[h % len(CATEGORY_PALETTE)]


def auto_detect_tags(mod_class, replacements: List[str] = None, lang_reader=None) -> List[str]:
    raw_tags = list(mod_class.tags or [])
    tags = []
    seen = set()

    for t in raw_tags:
        nt = normalize_tag(t)
        if nt.lower() not in seen:
            tags.append(nt)
            seen.add(nt.lower())

    swf_names = getattr(mod_class, 'swfNames', []) or []
    file_names = getattr(mod_class, 'fileNames', []) or []
    replacements = replacements or []

    all_files = [f.lower() for f in swf_names + file_names]

    has_effects = any(any(p in f for p in ['bones', 'sfx']) for f in all_files)
    has_ui = any('ui' in f or 'menu' in f or 'hud' in f for f in all_files)
    has_map = any('map' in f or 'background' in f or 'stage' in f for f in all_files)

    if has_map and 'map' not in seen:
        tags.append('Map')
        seen.add('map')
    if has_ui and 'ui' not in seen:
        tags.append('UI')
        seen.add('ui')
    if has_effects and 'effects' not in seen:
        tags.append('Effects')
        seen.add('effects')

    has_costume = False
    has_weapon = False

    legends = get_all_legends(lang_reader)

    for rep in replacements:
        if '(' in rep and ')' in rep:
            has_weapon = True
        else:
            has_costume = True

        for leg in legends:
            if leg.lower() in rep.lower() and leg.lower() not in seen:
                tags.append(leg)
                seen.add(leg.lower())

    for f in all_files:
        for leg in legends:
            if leg.lower() in f and leg.lower() not in seen:
                tags.append(leg)
                seen.add(leg.lower())

    if has_costume and 'legend skin' not in seen:
        tags.insert(0, 'Legend Skin')
        seen.add('legend skin')
    if has_weapon and 'weapon skin' not in seen:
        idx = 0 if 'legend skin' not in seen else 1
        tags.insert(idx, 'Weapon Skin')
        seen.add('weapon skin')

    return tags
