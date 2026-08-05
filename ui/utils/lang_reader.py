"""
Brawlhalla Language Reader
Based on: https://github.com/eyalzus12/BrawlhallaLangReader
Reads Brawlhalla language.X.bin files to extract skin names and translations
"""

import struct
import os
import zlib
from typing import Dict, List, Optional

class BrawlhallaLangReader:
    """Lee archivos de idioma binarios de Brawlhalla"""
    
    LANGUAGE_IDS = {
        1: "en",      # English
        2: "de",      # German
        3: "fr",      # French
        4: "pt_BR",   # Portuguese (Brazil)
        5: "es",      # Spanish
        6: "it",      # Italian
        7: "ru",      # Russian
        8: "pl",      # Polish
        9: "tr",      # Turkish
        10: "ja",     # Japanese
        11: "ko",     # Korean
        12: "zh_CN",  # Chinese (Simplified)
        13: "zh_TW"   # Chinese (Traditional)
    }
    
    def __init__(self, languages_folder: str):
        self.languages_folder = languages_folder
        self.translations: Dict[str, Dict[str, str]] = {}
        self.costume_map: Dict[str, str] = {}
        self.weapon_map: Dict[str, str] = {}
        self.avatar_map: Dict[str, str] = {}
        # Suffix index: maps suffix -> [full_code, ...]
        self.costume_suffix_index: Dict[str, List[str]] = {}

    def read_language_file(self, language_id: int) -> Dict[str, str]:
        file_path = os.path.join(self.languages_folder, f"language.{language_id}.bin")
        if not os.path.exists(file_path):
            return {}
        
        translations = {}
        try:
            with open(file_path, 'rb') as f:
                header_bytes = f.read(4)
                if len(header_bytes) < 4:
                    return {}
                
                header = struct.unpack('<I', header_bytes)[0]
                compressed_data = f.read()
                decompressed_data = zlib.decompress(compressed_data)
                
                offset = 0
                entry_count = struct.unpack('>I', decompressed_data[offset:offset+4])[0]
                offset += 4
                
                for _ in range(entry_count):
                    if offset + 2 > len(decompressed_data):
                        break
                    key_length = struct.unpack('>H', decompressed_data[offset:offset+2])[0]
                    offset += 2
                    
                    if offset + key_length > len(decompressed_data):
                        break
                    key = decompressed_data[offset:offset+key_length].decode('utf-8', errors='ignore')
                    offset += key_length
                    
                    if offset + 2 > len(decompressed_data):
                        break
                    value_length = struct.unpack('>H', decompressed_data[offset:offset+2])[0]
                    offset += 2
                    
                    if offset + value_length > len(decompressed_data):
                        break
                    value = decompressed_data[offset:offset+value_length].decode('utf-8', errors='ignore')
                    offset += value_length
                    
                    translations[key] = value
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return {}
        
        return translations
    
    def load_language(self, language_id: int = 1) -> bool:
        lang_code = self.LANGUAGE_IDS.get(language_id, "en")
        trans = self.read_language_file(language_id)
        self.translations[lang_code] = trans

        if trans:
            for k, v in trans.items():
                if k.startswith("CostumeType_") and k.endswith("_DisplayName"):
                    code = k[len("CostumeType_"):-len("_DisplayName")]
                    self.costume_map[code.lower()] = v
                elif k.startswith("Generated|CostumeType_") and k.endswith("_DisplayNameWRTCrossover"):
                    code = k[len("Generated|CostumeType_"):-len("_DisplayNameWRTCrossover")]
                    self.costume_map[code.lower()] = v
                elif k.startswith("WeaponSkinType_") and k.endswith("_DisplayName"):
                    middle = k[len("WeaponSkinType_"):-len("_DisplayName")]
                    self.weapon_map[middle.lower()] = v
                elif k.startswith("EquipmentType_") and k.endswith("_DisplayName"):
                    middle = k[len("EquipmentType_"):-len("_DisplayName")]
                    self.weapon_map[middle.lower()] = v
                elif k.startswith("AvatarType_") and k.endswith("_DisplayName"):
                    code = k[len("AvatarType_"):-len("_DisplayName")]
                    self.avatar_map[code.lower()] = v
                elif k.startswith("AvatarType_") and k.endswith("_Name"):
                    code = k[len("AvatarType_"):-len("_Name")]
                    self.avatar_map[code.lower()] = v
                elif k.startswith("ItemType_Avatar_") and k.endswith("_DisplayName"):
                    code = k[len("ItemType_Avatar_"):-len("_DisplayName")]
                    self.avatar_map[code.lower()] = v
            # Build suffix index for costume_map
            for full_code in list(self.costume_map.keys()):
                # index every suffix of length >= 3
                for i in range(len(full_code)):
                    suffix = full_code[i:]
                    if len(suffix) >= 3:
                        if suffix not in self.costume_suffix_index:
                            self.costume_suffix_index[suffix] = []
                        self.costume_suffix_index[suffix].append(full_code)
            return True
        return False
    
    def get_translation(self, key: str, language_id: int = 1) -> Optional[str]:
        lang_code = self.LANGUAGE_IDS.get(language_id, "en")
        if lang_code not in self.translations:
            self.load_language(language_id)
        return self.translations.get(lang_code, {}).get(key)
    
    def _suffix_costume(self, code_low: str) -> Optional[str]:
        """Resolve a partial costume code via suffix index (e.g. MonsterBat -> DarkheartMonsterBat)."""
        matches = self.costume_suffix_index.get(code_low)
        if matches:
            # Prefer the shortest full_code that ends with this suffix (most specific)
            best = min(matches, key=len)
            return self.costume_map.get(best)
        return None

    def resolve_costume(self, code: str) -> Optional[str]:
        if not self.costume_map:
            self.load_language(1)
        c_low = code.lower()
        # 1. Exact match
        res = self.costume_map.get(c_low)
        if res:
            return res
        # 2. Suffix search (handles partial codes like MonsterBat -> DarkheartMonsterBat)
        res = self._suffix_costume(c_low)
        if res:
            return res
        # 3. Try splitting on _ and resolving each part
        if "_" in code:
            for sub in code.split("_"):
                res = self.costume_map.get(sub.lower()) or self._suffix_costume(sub.lower())
                if res:
                    return res
        return None

    def resolve_weapon(self, code: str, weapon_type: str) -> Optional[str]:
        if not self.weapon_map:
            self.load_language(1)
        c_low = code.lower()
        # Weapon type -> list of prefixes used in WeaponSkinType_ keys
        WEAPON_VARIANTS = {
            'Hammer': ['hammer'],
            'Rocket Lance': ['rocketlance', 'lance'],
            'Sword': ['sword'],
            'Spear': ['spear'],
            'Blasters': ['pistol', 'blasters'],
            'Katars': ['katar', 'katars'],
            'Axe': ['axe'],
            'Bow': ['bow'],
            'Gauntlets': ['fists','gauntlets'],
            'Scythe': ['scythe'],
            'Cannon': ['cannon'],
            'Orb': ['orb'],
            'Greatsword': ['greatsword'],
            'Battle Boots': ['boots', 'skyboots', 'battleboots'],
            'Chakram': ['chakram'],
        }
        variants = WEAPON_VARIANTS.get(weapon_type, [weapon_type.lower().replace(' ', '')])

        def _try_variants(key: str) -> Optional[str]:
            for var in variants:
                res = self.weapon_map.get(f"{var}{key}")
                if res:
                    return res
            return None

        # 1. Exact weapon type + code
        res = _try_variants(c_low)
        if res:
            return f"{res} ({weapon_type})"
        # 2. Plain code (handles keys that have no type prefix)
        res = self.weapon_map.get(c_low)
        if res:
            return f"{res} ({weapon_type})"
        # 3. Suffix fallback: find weapon_map key ending with code
        for wk, wv in self.weapon_map.items():
            for var in variants:
                if wk == f"{var}{c_low}" or wk.endswith(c_low) and any(wk.startswith(v) for v in variants):
                    return f"{wv} ({weapon_type})"
        # 4. Split underscore and retry
        if "_" in code:
            for sub in code.split("_"):
                sub_low = sub.lower()
                res = _try_variants(sub_low)
                if res:
                    return f"{res} ({weapon_type})"
                res = self.weapon_map.get(sub_low)
                if res:
                    return f"{res} ({weapon_type})"
        return None

    def resolve_avatar(self, code: str) -> Optional[str]:
        if not hasattr(self, 'avatar_map') or not self.avatar_map:
            self.load_language(1)
        c_low = code.lower()
        res = self.avatar_map.get(c_low)
        if res:
            return res
        if "_" in code:
            for sub in code.split("_"):
                res = self.avatar_map.get(sub.lower())
                if res:
                    return res
        return None


def format_avatar_name(raw_name: str, lang_reader=None) -> str:
    name = os.path.splitext(os.path.basename(raw_name))[0]
    n_low = name.lower()

    is_flag = any(p in n_low for p in ['flag1a', 'flag1b', 'flag1blong', 'flag_'])

    clean = name
    prefixes = [
        'a_CPPScaler_', 'CPPScaler_', 'a_AvatarIcon_', 'a_Flag1bLong_', 'a_Flag1a_', 'a_Flag1b_',
        'a_Flag_', 'a_Avatar_', 'Flag1bLong_', 'Flag1a_', 'Flag1b_', 'AvatarIcon_', 'UI_Avatars',
        'Sprites_Avatars_128', 'Sprites_Avatars'
    ]
    for p in prefixes:
        if clean.lower().startswith(p.lower()):
            clean = clean[len(p):]
            break

    if clean.lower().startswith("flag") and len(clean) > 4:
        is_flag = True
        clean = clean[4:]
    elif clean.lower().endswith("flag") and len(clean) > 4:
        is_flag = True
        clean = clean[:-4]

    # Exclude default avatar / empty / icon
    if clean.lower() in ['', 'avatar', 'default', 'none', 'icon']:
        return ""

    if lang_reader and hasattr(lang_reader, 'resolve_avatar'):
        resolved = lang_reader.resolve_avatar(clean)
        if resolved:
            if resolved.lower().endswith(" avatar"):
                resolved = resolved[:-7].strip()
            return resolved

    import re
    words = re.findall(r'[A-Z][a-z0-9]*|[a-z0-9]+', clean)
    if not words:
        words = [clean]

    formatted_words = []
    for w in words:
        w_cap = w.capitalize()
        if w_cap.lower() in ['icon', 'avataricon', 'avatar', 'cppscaler']:
            continue
        formatted_words.append(w_cap)

    if not formatted_words:
        return ""

    formatted = " ".join(formatted_words)

    known_flags = {'mexico', 'pride', 'trans', 'coffee', 'bombhalla', 'knotwork', 'ramen', 'swiftpottery', 'swiftsports', 'wepdrop', 'wolfmoon', 'yarnasuri', 'yumikoflames', 'canada', 'usa', 'uk', 'brazil', 'france', 'germany', 'spain', 'italy', 'japan', 'korea', 'china', 'australia', 'guam'}
    if any(kf in clean.lower() for kf in known_flags) or is_flag:
        if "flag" not in formatted.lower():
            formatted = f"{formatted} Flag"

    if formatted.lower() in ['', 'avatar', 'default', 'none', 'flag']:
        return ""

    return formatted


GLOBAL_LANG_READER_INSTANCE = None
MOD_REPLACEMENTS_CACHE: Dict[str, List[str]] = {}

def get_global_lang_reader(languages_folder: str) -> Optional[BrawlhallaLangReader]:
    global GLOBAL_LANG_READER_INSTANCE
    if GLOBAL_LANG_READER_INSTANCE is not None:
        return GLOBAL_LANG_READER_INSTANCE
    if os.path.exists(languages_folder):
        try:
            reader = BrawlhallaLangReader(languages_folder)
            reader.load_language(1)
            GLOBAL_LANG_READER_INSTANCE = reader
            return reader
        except Exception as e:
            print(f"[LANG READER ERROR] {e}")
    return None

def get_cached_replacements(mod_hash: str) -> Optional[List[str]]:
    return MOD_REPLACEMENTS_CACHE.get(mod_hash)

def set_cached_replacements(mod_hash: str, replacements: List[str]) -> None:
    MOD_REPLACEMENTS_CACHE[mod_hash] = replacements
