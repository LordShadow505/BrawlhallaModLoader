"""
Automatic Tag Generator & Fun Dark-Mode Badge Formatter for Brawlhalla Mod Loader
"""

import os
import json
import re
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any


def _get_mod_cache_file(mod_hash: str) -> Optional[str]:
    """Return the loader cache path used by the core (Roaming AppData)."""
    if not mod_hash:
        return None
    for env_name in ("APPDATA", "LOCALAPPDATA"):
        base = os.getenv(env_name, "")
        if not base:
            continue
        cache_file = os.path.join(base, "BModloader", "Mods", mod_hash, "mod.json")
        if os.path.exists(cache_file):
            return cache_file
    return None

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
# - Hand Mod                   -> Red (#4d103b)
# - Color Mod                  -> Slightly Purplish Blue (#102a4d)
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
    "hand mod":     "#4d103b", # Red
    "hand mods":    "#4d103b",
    "color mod":    "#102a4d", # Slightly purplish blue
    "color mods":   "#102a4d",
    "bmt certified":     "#07c9d7", # Cyan
    "custom ui":         "#475569", # Slate
    "security warning":  "#ef4444", # Red
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
    "hand mods":    "Hand Mod",
    "hand mod":     "Hand Mod",
    "color mods":   "Color Mod",
    "color mod":    "Color Mod",
    "bmt certified":     "BMT Certified",
    "custom ui":         "Custom UI",
    "security warning":  "Security Warning",
}


# =========================================================================
# COLOR SCHEMES VALIDATION CATALOG (Battle Pass & Paid Store Mammoth Coins)
# =========================================================================

ALLOWED_MODIFIABLE_SCHEMES: Dict[str, str] = {
    # Battle Pass Color Schemes (Guaranteed Offline Fallback)
    "26": "Soul Fire (Battle Pass S1)",
    "27": "Synthwave (Battle Pass S2)",
    "28": "Frozen Forest (Battle Pass S3)",
    "29": "Coat of Lions (Battle Pass S4)",
    "30": "Starlight (Battle Pass S5)",
    "31": "Willow Leaves (Battle Pass S6)",
    "32": "Pact of Poison (Battle Pass S7)",
    "33": "Darkheart (Battle Pass S8)",
    "34": "Armageddon (Battle Pass S9)",
    "35": "Kira-kira (Battle Pass S10)",
    "36": "Ancient Curse (Battle Pass S11)",
    "37": "Neon Hanafuda (Battle Pass S12)",
    "38": "Dragonfire (Battle Pass S13)",

    # Match by Name (case-insensitive)
    "soul fire": "Soul Fire (Battle Pass S1)",
    "synthwave": "Synthwave (Battle Pass S2)",
    "frozen forest": "Frozen Forest (Battle Pass S3)",
    "coat of lions": "Coat of Lions (Battle Pass S4)",
    "starlight": "Starlight (Battle Pass S5)",
    "willow leaves": "Willow Leaves (Battle Pass S6)",
    "pact of poison": "Pact of Poison (Battle Pass S7)",
    "darkheart": "Darkheart (Battle Pass S8)",
    "armageddon": "Armageddon (Battle Pass S9)",
    "kira-kira": "Kira-kira (Battle Pass S10)",
    "kirakira": "Kira-kira (Battle Pass S10)",
    "ancient curse": "Ancient Curse (Battle Pass S11)",
    "neon hanafuda": "Neon Hanafuda (Battle Pass S12)",
    "dragonfire": "Dragonfire (Battle Pass S13)",

    # Paid / Store Color Schemes (Purchased with Mammoth Coins)
    "48": "RGB (Store Color)",
    "rgb": "RGB (Store Color)",
}

WIKI_COLORS_API_URL = "https://brawlhalla.wiki.gg/api.php?action=parse&page=Colors&prop=text&format=json"
WIKI_COLORS_CACHE_FILE = os.path.join(os.getenv("LOCALAPPDATA", ""), "BModloader", "wiki_colors_cache.json")

def load_cached_wiki_schemes() -> None:
    """Loads previously fetched wiki colors from local cache if present."""
    if os.path.exists(WIKI_COLORS_CACHE_FILE):
        try:
            with open(WIKI_COLORS_CACHE_FILE, "r", encoding="utf-8") as f:
                cached = json.load(f)
                if isinstance(cached, dict):
                    for k, v in cached.items():
                        ALLOWED_MODIFIABLE_SCHEMES[k] = v
                        ALLOWED_MODIFIABLE_SCHEMES[k.lower()] = v
        except Exception:
            pass

def fetch_wiki_modifiable_schemes_async() -> None:
    """Spawns background thread to fetch latest Battle Pass & Store colors from wiki.gg with fallback."""
    def _fetch_worker():
        try:
            import urllib.request
            headers = {
                'User-Agent': 'BrawlhallaModLoader/1.0 (contact: support@example.com) Python-urllib/3.10',
                'Accept': 'application/json'
            }
            req = urllib.request.Request(WIKI_COLORS_API_URL, headers=headers)
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                html = data.get('parse', {}).get('text', {}).get('*', '')

            new_schemes = {}
            # Battle Pass Colors section
            pos = html.rfind('id="Battle_Pass_Colors"')
            if pos != -1:
                section_html = html[pos:pos+15000]
                matches = re.findall(r'<a\s+href="[^"]*"\s+title="([^"]+)">([^<]+)</a>', section_html)
                for title, text in matches:
                    clean = text.strip()
                    if clean and not clean.startswith("Season") and not clean.startswith("File:") and not clean.startswith("Anniversary") and "edit" not in clean.lower() and "esports" not in clean.lower() and "twitch" not in clean.lower() and "rewards" not in clean.lower():
                        new_schemes[clean.lower()] = f"{clean} (Battle Pass)"
                        new_schemes[clean] = f"{clean} (Battle Pass)"

            # Paid Store Colors (RGB)
            new_schemes["rgb"] = "RGB (Store Color)"
            new_schemes["48"] = "RGB (Store Color)"

            if new_schemes:
                for k, v in new_schemes.items():
                    ALLOWED_MODIFIABLE_SCHEMES[k] = v
                os.makedirs(os.path.dirname(WIKI_COLORS_CACHE_FILE), exist_ok=True)
                with open(WIKI_COLORS_CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump(new_schemes, f, indent=2)
        except Exception:
            pass

    import threading
    t = threading.Thread(target=_fetch_worker, daemon=True)
    t.start()

load_cached_wiki_schemes()
fetch_wiki_modifiable_schemes_async()


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


def detect_special_mod_types(mod_class: Any) -> Tuple[bool, bool, List[str], List[str]]:
    """
    Detects if a mod is a Hand Mod or a Color Mod, and extracts target replacements.
    Returns: (is_hand_mod, is_color_mod, hand_replacements, color_replacements)
    """
    is_hand_mod = False
    is_color_mod = False
    hand_replacements: List[str] = []
    color_replacements: List[str] = []

    # Inspect SWFs and scripts
    swfs = getattr(mod_class, 'swfs', {}) or {}
    files = getattr(mod_class, 'files', {}) or {}
    file_names = getattr(mod_class, 'fileNames', []) or []

    # Fallback to reading cached mod.json if swfs is empty
    if not swfs and hasattr(mod_class, 'hash') and mod_class.hash:
        try:
            cache_file = _get_mod_cache_file(mod_class.hash)
            if cache_file:
                with open(cache_file, "r", encoding="utf-8") as cf:
                    cached_data = json.load(cf)
                    swfs = cached_data.get("swfs", {}) or {}
        except Exception:
            pass

    # Fallback to reading .bmod file or mod folder directly if swfs is still empty
    if not swfs and hasattr(mod_class, 'modPath') and mod_class.modPath and os.path.exists(mod_class.modPath):
        if os.path.isdir(mod_class.modPath):
            for root, _, files_list in os.walk(mod_class.modPath):
                for fn in files_list:
                    if "gfx_hands" in fn.lower():
                        is_hand_mod = True
                    if fn.lower() == "obf.as" or fn.endswith(".as") or fn.endswith(".pcode"):
                        try:
                            with open(os.path.join(root, fn), "r", encoding="utf-8", errors="ignore") as f:
                                code_txt = f.read()
                            if "paletteMap" in code_txt:
                                is_color_mod = True
                            if "handMap" in code_txt:
                                is_hand_mod = True
                        except Exception:
                            pass
        else:
            try:
                from core.swf.swf import Swf
                s = Swf(mod_class.modPath, autoload=False)
                if s.metaData:
                    meta = s.metaData.get()
                    if isinstance(meta, dict):
                        swfs = meta.get("swfs", {}) or {}
            except Exception:
                pass

    # Check for Gfx_Hands.swf
    for f in list(files.values()) + file_names + list(swfs.keys()):
        if "gfx_hands" in str(f).lower():
            is_hand_mod = True

    for swf_name, swf_map in swfs.items():
        if "ui_mainmenu" in str(swf_name).lower():
            obf_map = swf_map.get("obfMappings", {}) if isinstance(swf_map, dict) else getattr(swf_map, "obfMappings", {})
            scripts = swf_map.get("scripts", {}) if isinstance(swf_map, dict) else getattr(swf_map, "scripts", {})
            
            all_text_chunks = []
            if isinstance(obf_map, dict):
                all_text_chunks.extend([str(v) for v in obf_map.values()])
            if isinstance(scripts, dict):
                all_text_chunks.extend([str(v) for v in scripts.values()])
            combined_code = "\n".join(all_text_chunks)

            # Palette detection: MUST have actual assignments (paletteMap["..."] =)
            pal_targets = re.findall(r'paletteMap\s*\[\s*["\']?([^"\'\]]+)["\']?\s*\]\s*=', combined_code)
            if pal_targets:
                is_color_mod = True
                cleaned_targets = [p.strip().strip("'\"") for p in pal_targets if p.strip()]
                named_targets = [p for p in cleaned_targets if not p.isdigit()]
                numeric_targets = [p for p in cleaned_targets if p.isdigit()]

                # Use named targets if present to avoid showing numeric IDs like #62
                targets_to_use = named_targets if named_targets else numeric_targets

                for pt_clean in targets_to_use:
                    pt_low = pt_clean.lower()
                    if pt_clean in ALLOWED_MODIFIABLE_SCHEMES:
                        resolved = ALLOWED_MODIFIABLE_SCHEMES[pt_clean]
                    elif pt_low in ALLOWED_MODIFIABLE_SCHEMES:
                        resolved = ALLOWED_MODIFIABLE_SCHEMES[pt_low]
                    elif pt_clean.isdigit():
                        resolved = ALLOWED_MODIFIABLE_SCHEMES.get(pt_clean, f"Color Scheme {pt_clean}")
                    else:
                        resolved = pt_clean.upper() if len(pt_clean) <= 4 else pt_clean.title()
                    if resolved not in color_replacements:
                        color_replacements.append(resolved)

            # Hand detection: MUST have actual assignments (handMap["..."] =)
            hand_targets = re.findall(r'handMap\s*\[\s*["\']?([^"\'\]]+)["\']?\s*\]\s*=\s*["\']?([^"\';]+)["\']?', combined_code)
            if hand_targets:
                is_hand_mod = True
                for cos, hand in hand_targets:
                    entry = f"{cos.strip()} [Hand: {hand.strip()}]"
                    if entry not in hand_replacements:
                        hand_replacements.append(entry)

    # Fallback to name/tags ONLY if not detected from code and UI_MainMenu is not present
    if not is_hand_mod and not is_color_mod and not any("ui_mainmenu" in str(k).lower() for k in swfs.keys()):
        raw_tags = [str(t).lower() for t in getattr(mod_class, 'tags', []) or []]
        mod_name = str(getattr(mod_class, 'name', '') or '').lower()
        if any(t in ('hand mod', 'hand mods', 'hands') for t in raw_tags) or 'hand mod' in mod_name:
            is_hand_mod = True
        elif any(t in ('color mod', 'color mods', 'colors') for t in raw_tags) or 'color mod' in mod_name:
            is_color_mod = True

    return is_hand_mod, is_color_mod, hand_replacements, color_replacements


def check_ui_mainmenu_security(mod_class: Any) -> Dict[str, Any]:
    """
    Scans UI_MainMenu exclusively in mod_class for security threats and BMT certification.
    Returns:
        {
            'has_ui_mainmenu': bool,
            'is_certified': bool,
            'is_clean': bool,
            'status': 'NO_UI' | 'BMT_CERTIFIED' | 'CUSTOM_CLEAN' | 'SUSPICIOUS',
            'threats': list,
            'cert_info': dict,
            'warning_msg': str
        }
    """
    from .security_scanner import scan_ui_mainmenu_code, verify_bmt_certificate

    res = {
        "has_ui_mainmenu": False,
        "is_certified": False,
        "is_clean": True,
        "status": "NO_UI",
        "threats": [],
        "cert_info": {},
        "warning_msg": ""
    }

    swfs = getattr(mod_class, 'swfs', {}) or {}
    files = getattr(mod_class, 'files', {}) or {}
    file_names = getattr(mod_class, 'fileNames', []) or []
    all_names = list(swfs.keys()) + list(files.values()) + file_names

    # Check if UI_MainMenu is involved in this mod
    has_ui = any("ui_mainmenu" in str(f).lower() for f in all_names)
    if not has_ui:
        mod_p = getattr(mod_class, 'modPath', '') or ''
        if mod_p and os.path.exists(mod_p) and "ui_mainmenu" in str(mod_p).lower():
            has_ui = True

    if not has_ui:
        is_hand, is_color, _, _ = detect_special_mod_types(mod_class)
        if is_hand or is_color or getattr(mod_class, 'bmtCertified', False):
            has_ui = True

    if not has_ui:
        return res

    res["has_ui_mainmenu"] = True

    # 1. Check for BMT certificate in modClass metadata or cache or modSwf
    cert_data = getattr(mod_class, 'bmtCert', None) or getattr(mod_class, 'bmt_cert', None)
    if not cert_data and hasattr(mod_class, 'hash') and mod_class.hash:
        try:
            cache_file = _get_mod_cache_file(mod_class.hash)
            if cache_file:
                with open(cache_file, "r", encoding="utf-8") as cf:
                    cdata = json.load(cf)
                    cert_data = cdata.get("bmtCert") or cdata.get("bmt_cert")
                    if cdata.get("creatorCertified"):
                        mod_class.creatorCertified = True
        except Exception:
            pass

    # When the core supplied a SWF inventory it also supplied every certificate
    # field known to that cache.  Reopening the complete .bmod through FFDec here
    # would block Qt merely to rediscover that an old mod has no certificate.
    has_core_metadata = bool(swfs) or bool(files) or bool(file_names)
    if (not cert_data and not has_core_metadata and
            hasattr(mod_class, 'modPath') and mod_class.modPath and os.path.exists(mod_class.modPath)):
        try:
            from core.swf.swf import Swf
            s = Swf(mod_class.modPath, autoload=False)
            s.open()
            if s.metaData:
                mdict = s.metaData.get()
                if isinstance(mdict, dict):
                    cert_data = mdict.get("bmtCert") or mdict.get("bmt_cert")
                    if mdict.get("creatorCertified"):
                        mod_class.creatorCertified = True
            s.close()
        except Exception:
            pass

    if cert_data:
        mod_p = getattr(mod_class, 'modPath', '') or ''
        p_obj = Path(mod_p) if mod_p and os.path.exists(mod_p) else None
        is_v, cert_msg = verify_bmt_certificate(cert_data, p_obj)
        if is_v:
            res["is_certified"] = True
            res["cert_info"] = cert_data
        else:
            res["threats"].append({"snippet": "Forged/Invalid BMT Certificate", "description": cert_msg})

    # 2. Extract and scan all UI_MainMenu code and scripts
    all_code_chunks = []
    for swf_name, swf_map in swfs.items():
        if "ui_mainmenu" in str(swf_name).lower():
            obf_map = swf_map.get("obfMappings", {}) if isinstance(swf_map, dict) else getattr(swf_map, "obfMappings", {})
            scripts = swf_map.get("scripts", {}) if isinstance(swf_map, dict) else getattr(swf_map, "scripts", {})
            if isinstance(obf_map, dict):
                all_code_chunks.extend([str(v) for v in obf_map.values()])
            if isinstance(scripts, dict):
                all_code_chunks.extend([str(v) for v in scripts.values()])

    combined_code = "\n".join(all_code_chunks)
    if combined_code:
        founds = scan_ui_mainmenu_code(combined_code)
        for snip, desc in founds:
            res["threats"].append({"snippet": snip, "description": desc})

    # Direct fallback scan on raw SWF if available and code chunks were empty
    if not combined_code and hasattr(mod_class, 'modPath') and mod_class.modPath and os.path.exists(mod_class.modPath):
        try:
            raw_bytes = Path(mod_class.modPath).read_bytes()
            founds = scan_ui_mainmenu_code(raw_bytes)
            for snip, desc in founds:
                res["threats"].append({"snippet": snip, "description": desc})
        except Exception:
            pass

    # Determine final security status
    if res["threats"]:
        res["is_clean"] = False
        res["status"] = "SUSPICIOUS"
        res["warning_msg"] = f"CRITICAL SECURITY WARNING: {len(res['threats'])} suspicious executable script(s) or network connection(s) detected in UI_MainMenu.swf. This mod may attempt to launch external programs or send data to remote servers."
    elif res["is_certified"]:
        res["status"] = "BMT_CERTIFIED"
        res["warning_msg"] = ""
    else:
        res["status"] = "CUSTOM_CLEAN"
        res["warning_msg"] = "NOTICE: This mod replaces UI_MainMenu.swf without official BMT certification. No suspicious executable scripts were detected."

    return res


def validate_color_mod_schemes(mod_class: Any) -> Tuple[bool, List[str], str]:
    """
    Validates if a Color Mod replaces only approved Battle Pass or Paid color schemes.
    [TEMPORARILY DISABLED BY USER REQUEST - Always allows color mod installation]
    Returns: (is_valid, target_schemes_found, error_reason)
    """
    is_hand, is_color, _, color_targets = detect_special_mod_types(mod_class)
    if not is_color:
        return True, [], ""

    swfs = getattr(mod_class, 'swfs', {}) or {}
    raw_targets = []

    for swf_name, swf_map in swfs.items():
        if "ui_mainmenu" in str(swf_name).lower():
            obf_map = swf_map.get("obfMappings", {}) if isinstance(swf_map, dict) else getattr(swf_map, "obfMappings", {})
            scripts = swf_map.get("scripts", {}) if isinstance(swf_map, dict) else getattr(swf_map, "scripts", {})
            
            all_text_chunks = []
            if isinstance(obf_map, dict):
                all_text_chunks.extend([str(v) for v in obf_map.values()])
            if isinstance(scripts, dict):
                all_text_chunks.extend([str(v) for v in scripts.values()])
            combined_code = "\n".join(all_text_chunks)

            found = re.findall(r'paletteMap\s*\[\s*["\']?([^"\'\]]+)["\']?\s*\]\s*=', combined_code)
            for f in found:
                raw_targets.append(f.strip())

    if not raw_targets and color_targets:
        raw_targets = color_targets

    # Validation temporarily bypassed to allow all color mods
    return True, raw_targets, ""


def auto_detect_tags(mod_class, replacements: List[str] = None, lang_reader=None) -> List[str]:
    raw_tags = list(getattr(mod_class, 'tags', []) or [])
    # Strip any prior stale badges
    raw_tags = [t for t in raw_tags if normalize_tag(t).lower() not in ('hand mod', 'color mod', 'bmt certified', 'custom ui', 'security warning')]
    tags = []
    seen = set()

    for t in raw_tags:
        nt = normalize_tag(t)
        if nt.lower() not in seen:
            tags.append(nt)
            seen.add(nt.lower())

    swf_names = getattr(mod_class, 'swfNames', []) or []
    file_names = getattr(mod_class, 'fileNames', []) or []
    sprite_names = getattr(mod_class, 'spriteNames', []) or []
    replacements = replacements or []

    all_files = [f.lower() for f in swf_names + file_names + sprite_names]

    # Special Mod Types Detection (Hand Mod & Color Mod)
    is_hand_mod, is_color_mod, _, _ = detect_special_mod_types(mod_class)
    sec_info = check_ui_mainmenu_security(mod_class)

    # Check if this mod is an Avatar mod
    is_avatar = (
        any(any(p in f for p in ['ui_avatars', 'sprites_avatars', 'avatar', 'cppscaler', 'flag1a', 'flag1b', 'flag1blong']) for f in all_files) or
        any('(avatar)' in r.lower() or 'avatar' in r.lower() for r in replacements)
    )

    if is_avatar:
        if 'ui' not in seen:
            tags.append('UI')
            seen.add('ui')
        if 'avatars' not in seen and 'avatar' not in seen:
            tags.append('Avatars')
            seen.add('avatars')

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
        r_low = rep.lower()
        if '(avatar)' in r_low or '(color scheme)' in r_low or '(hand mod)' in r_low:
            continue
        if '(legend skin)' in r_low or not ('(' in r_low and ')' in r_low):
            if not is_avatar:
                has_costume = True
        else:
            has_weapon = True

        if not is_avatar:
            for leg in legends:
                if leg.lower() in r_low and leg.lower() not in seen:
                    tags.append(leg)
                    seen.add(leg.lower())

    if not is_avatar:
        for f in all_files:
            for leg in legends:
                if leg.lower() in f and leg.lower() not in seen:
                    tags.append(leg)
                    seen.add(leg.lower())

    if has_costume and not is_avatar and 'legend skin' not in seen:
        tags.insert(0, 'Legend Skin')
        seen.add('legend skin')
    if has_weapon and 'weapon skin' not in seen:
        idx = 0 if ('legend skin' not in seen and 'ui' not in seen) else 1
        tags.insert(idx, 'Weapon Skin')
        seen.add('weapon skin')

    # Ensure Special Badges (Hand Mod, Color Mod) appear at top priority
    if is_color_mod and 'color mod' not in seen:
        tags.insert(0, 'Color Mod')
        seen.add('color mod')
    if is_hand_mod and 'hand mod' not in seen:
        tags.insert(0, 'Hand Mod')
        seen.add('hand mod')

    # Security Badges for UI_MainMenu
    if sec_info.get("has_ui_mainmenu"):
        status = sec_info.get("status")
        if status == "SUSPICIOUS" and 'security warning' not in seen:
            tags.insert(0, 'Security Warning')
            seen.add('security warning')
        elif status == "BMT_CERTIFIED" and 'bmt certified' not in seen:
            tags.insert(0, 'BMT Certified')
            seen.add('bmt certified')
        elif status == "CUSTOM_CLEAN" and 'custom ui' not in seen:
            tags.insert(0, 'Custom UI')
            seen.add('custom ui')

    return tags
