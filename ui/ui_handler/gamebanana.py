import os
import re
import json
import time
import threading
import webbrowser
import requests
import shiboken6

from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
    QScrollArea, QWidget, QGridLayout, QComboBox, QStackedWidget, QProgressBar
)
from PySide6.QtCore import Qt, Signal, QObject, QTimer, QPropertyAnimation, QEasingCurve, QRectF, QSize
from PySide6.QtGui import QPixmap, QIcon, QFont, QPainter, QPainterPath, QColor

# --- STYLES ---
BG_MAIN = "#141414"
BG_CARD = "#222226"
BG_HOVER = "#2a2a30"
ACCENT = "#3584e4"
ACCENT_GREEN = "#2e7d32"

SCROLLBAR = """
    QScrollArea { border: none; background: transparent; }
    QScrollBar:vertical { border: none; background: #111; width: 8px; margin: 0; }
    QScrollBar::handle:vertical { background: #444; min-height: 20px; border-radius: 4px; }
    QScrollBar::handle:vertical:hover { background: #666; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
    
    QScrollBar:horizontal { border: none; background: #111; height: 8px; margin: 0; }
    QScrollBar::handle:horizontal { background: #444; min-width: 20px; border-radius: 4px; }
    QScrollBar::handle:horizontal:hover { background: #666; }
"""

BTN_PRIMARY = f"""
    QPushButton {{ background: {ACCENT}; color: #fff; border: none; border-radius: 6px; padding: 6px 14px; font-weight: bold; font-size: 12px; }}
    QPushButton:hover {{ background: #4a90e2; }}
"""

BTN_SECONDARY = """
    QPushButton { background: rgba(255, 255, 255, 0.1); color: #fff; border: none; border-radius: 6px; padding: 6px 12px; font-weight: bold; font-size: 12px; }
    QPushButton:hover { background: rgba(255, 255, 255, 0.2); }
"""

ICONS_PATH = os.path.join(os.path.dirname(__file__), "..", "ui_sources", "resources", "icons")

def get_icon_pixmap(name, size=14):
    p = os.path.join(ICONS_PATH, f"{name}.svg")
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    if os.path.exists(p):
        pix.load(p)
        pix = pix.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return pix

def get_rounded_pixmap(pix, width, height, radius=8):
    if not pix or pix.isNull():
        out = QPixmap(width, height)
        out.fill(QColor("#111"))
        return out
    scaled = pix.scaled(width, height, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    out = QPixmap(width, height)
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, width, height), radius, radius)
    p.setClipPath(path)
    p.drawPixmap(0, 0, scaled)
    p.end()
    return out

def fmt_num(n):
    try:
        if n is None: return "0"
        n = int(n)
    except: return "0"
    if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
    elif n >= 1_000: return f"{n/1_000:.1f}k"
    return str(n)


CATEGORY_PALETTE = [
    "#000000", "#32c12c", "#009888", "#3e49bb", "#526eff", "#7f4fc9", "#87c735", 
    "#00a5f9", "#00bcd9", "#682cbf", "#ff9a00", "#e34c22", "#7c5547", 
    "#5f7d8e", "#ff5500", "#d40c00", "#50342c"
]

CATEGORY_COLOR_MAP = {
    "legend skins": "#3e49bb",
    "ui": "#ff9a00",
    "realms": "#682cbf",
    "effects": "#e34c22",
    "weapons": "#009888",
}

def get_category_color(name):
    if not name: return "#3584e4"
    key = str(name).strip().lower()
    if key in CATEGORY_COLOR_MAP:
        return CATEGORY_COLOR_MAP[key]
    h = sum(ord(c) for c in str(name))
    return CATEGORY_PALETTE[h % len(CATEGORY_PALETTE)]


def extract_requirement_name(req):
    if not req: return ""
    if isinstance(req, str):
        s = req.strip()
        if s.startswith(("http://", "https://", "www.")) or "wiki.gg" in s or ".wiki." in s or "http" in s:
            return ""
        return s
    if isinstance(req, list):
        items = [extract_requirement_name(x) for x in req if x]
        clean = [i for i in items if i]
        return ", ".join(clean)
    if isinstance(req, dict):
        val = req.get("_sName") or req.get("_sText") or req.get("name") or req.get("_sTitle")
        return extract_requirement_name(val)
    return ""


def extract_requirements_from_text(text):
    if not text: return []
    lines = text.split("\n")
    found = []
    keywords = [r"\bover\b", r"\breplaces\b", r"\breplace\b"]
    kw_regex = re.compile("|".join(keywords), re.IGNORECASE)
    
    for line in lines:
        line_str = line.strip()
        if not line_str: continue
        sentences = [s.strip() for s in line_str.split(".") if s.strip()]
        for stmt in sentences:
            if kw_regex.search(stmt):
                clean_stmt = re.sub(r"^[-\*•\s]+", "", stmt).strip()
                if clean_stmt and clean_stmt not in found and len(clean_stmt) < 150:
                    found.append(clean_stmt)
    return found


def extract_cat_id_and_name(info):
    if not isinstance(info, dict) or not info: return None, None
    cname = info.get("_sName") or info.get("name")
    cid = info.get("_idRow") or info.get("id")
    if not cid:
        url = info.get("_sProfileUrl") or ""
        m = re.search(r"/cats/(\d+)", url)
        if m: cid = int(m.group(1))
    return cid, cname


def extract_mod_categories(data):
    if not isinstance(data, dict): return []
    cats = []
    
    # 1. Main Parent / Root Category
    root_info = data.get("_aRootCategory") or data.get("_aParentCategory") or {}
    r_id, r_name = extract_cat_id_and_name(root_info)
    if not r_name:
        cat_info = data.get("_aCategory") or {}
        parent_info = cat_info.get("_aParentCategory") if isinstance(cat_info, dict) else {}
        r_id, r_name = extract_cat_id_and_name(parent_info)
        if not r_name and isinstance(cat_info, dict):
            r_name = cat_info.get("_sParentCategoryName")
            r_id = cat_info.get("_idParentCategoryRow")
            
    if r_name and r_id:
        cats.append((r_id, r_name))
        
    # 2. Subcategory
    sub_info = data.get("_aSubCategory") or data.get("_aCategory") or data.get("category") or {}
    s_id, s_name = extract_cat_id_and_name(sub_info)
    if s_name and s_id and (not cats or cats[0][1] != s_name):
        cats.append((s_id, s_name))

    if not cats:
        # Fallback if properties are flattened at root level
        cname = data.get("_sCategoryName") or data.get("category_name")
        cid = data.get("_idCategoryRow") or data.get("cat_id")
        if cname and cid:
            cats.append((cid, cname))
            
    return cats


class NoticeMarqueeBanner(QFrame):
    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.setFixedHeight(26)
        self.setStyleSheet("background: rgba(227, 76, 34, 0.14); border: none;")
        
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 10, 0)
        lay.setSpacing(8)
        
        ic = QLabel()
        ic.setPixmap(get_icon_pixmap("dialog-warning-symbolic", 12))
        ic.setStyleSheet("background: transparent; border: none;")
        lay.addWidget(ic)
        
        self.lbl = MarqueeLabel(text, always_scroll=True)
        self.lbl.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.lbl.setStyleSheet("color: #ff8a65; background: transparent; border: none;")
        lay.addWidget(self.lbl, 1)


class CategoryBadgePill(QPushButton):
    badge_clicked = Signal(int)

    def __init__(self, cat_id, cat_name, parent=None):
        super().__init__(cat_name, parent)
        self.cat_id = int(cat_id) if cat_id else None
        self.cat_name = cat_name
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(18)
        
        bg_color = get_category_color(cat_name)
        
        self.setStyleSheet(f"""
            QPushButton {{
                background: {bg_color};
                color: #ffffff;
                font-size: 8px;
                font-weight: bold;
                padding: 0px 7px;
                border-radius: 9px;
                border: none;
            }}
            QPushButton:hover {{
                opacity: 0.85;
            }}
        """)
        if self.cat_id:
            self.clicked.connect(lambda: self.badge_clicked.emit(self.cat_id))


class ImageCache(QObject):
    image_ready = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cache_dir = os.path.join(os.environ.get("APPDATA", ""), "BModLoader", "gb_cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        self._fetching = set()

    def get_image(self, url):
        if not url: return
        filename = "".join(c for c in url.split("/")[-1].split("?")[0] if c.isalnum() or c in ".-_")
        path = os.path.join(self.cache_dir, filename)

        if os.path.exists(path):
            self.image_ready.emit(url, path)
            return

        if url in self._fetching: return
        self._fetching.add(url)

        def fetch():
            try:
                r = requests.get(url, timeout=10, headers={"User-Agent": "BModLoader/1.0"})
                if r.status_code == 200:
                    with open(path, "wb") as f: f.write(r.content)
                    self.image_ready.emit(url, path)
            except: pass
            finally:
                if url in self._fetching: self._fetching.remove(url)

        threading.Thread(target=fetch, daemon=True).start()


class GBApiWorker(QObject):
    mods_loaded = Signal(object, int) 
    mod_detail_loaded = Signal(object)
    categories_loaded = Signal(object)
    featured_loaded = Signal(object)
    quick_file_ready = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.base = "https://gamebanana.com/apiv11"
        self.game_id = 5704 
        self.headers = {"User-Agent": "BModLoader/1.0"}

    def _get(self, endpoint, params=None):
        try:
            url = f"{self.base}{endpoint}"
            print(f"[GBApiWorker Request] GET {url} params={params}")
            r = requests.get(url, params=params, headers=self.headers, timeout=15)
            r.raise_for_status()
            res = r.json()
            return res
        except Exception as e:
            print(f"[GBApiWorker ERROR] Endpoint '{endpoint}' failed: {e}")
            import traceback
            traceback.print_exc()
            return None

    def fetch_categories(self, parent_id=None):
        def task():
            if parent_id:
                p = {"_idCategoryRow": parent_id, "_sSort": "a_to_z", "_bShowEmpty": "true"}
            else:
                p = {"_idGameRow": self.game_id, "_sSort": "a_to_z", "_bShowEmpty": "true"}
            print(f"[GBApiWorker] Fetching categories (parent_id={parent_id})...")
            data = self._get("/Mod/Categories", p)
            self.categories_loaded.emit(data)
        threading.Thread(target=task, daemon=True).start()

    def fetch_featured(self):
        def task():
            print(f"[GBApiWorker] Fetching top featured submissions from TopSubs...")
            data = self._get(f"/Game/{self.game_id}/TopSubs")
            if data and isinstance(data, list) and len(data) > 0:
                self.featured_loaded.emit(data)
            else:
                print(f"[GBApiWorker] TopSubs empty, falling back to Featured list...")
                res = self._get("/Util/List/Featured", {"_nPage": 1, "_idGameRow": self.game_id})
                recs = res.get("_aRecords", []) if isinstance(res, dict) else []
                self.featured_loaded.emit(recs)
        threading.Thread(target=task, daemon=True).start()

    def fetch_mods(self, page=1, cat_id=None, query="", sort="Generic_Newest"):
        def task():
            print(f"[GBApiWorker] Fetching mods (page={page}, cat_id={cat_id}, query='{query}', sort='{sort}')...")
            if query and len(query) >= 2:
                p = {"_sModelName": "Mod", "_idGameRow": self.game_id, "_nPage": page, "_nPerpage": 30, "_sSearchString": query}
                data = self._get("/Util/Search/Results", p)
            else:
                p = {"_nPage": page, "_nPerpage": 30, "_sSort": sort, "_aFilters[Generic_Game]": self.game_id}
                if cat_id: p["_aFilters[Generic_Category]"] = cat_id
                data = self._get("/Mod/Index", p)
            recs = data.get("_aRecords", data) if isinstance(data, dict) else data
            self.mods_loaded.emit(recs, page)
        threading.Thread(target=task, daemon=True).start()

    def fetch_mod_detail(self, mid):
        def task():
            print(f"[GBApiWorker] Fetching detail for mod ID {mid}...")
            props = "_sName,_aSubmitter,_aPreviewMedia,_nViewCount,_nLikeCount,_nDownloadCount,_tsDateAdded,_tsDateUpdated,_sText,_aFiles,_aCategory,_aRequirements"
            data = self._get(f"/Mod/{mid}", {"_csvProperties": props})
            if data and isinstance(data, dict): data["_idRow"] = mid
            self.mod_detail_loaded.emit(data)
        threading.Thread(target=task, daemon=True).start()

    def fetch_mod_stats(self, mids, callback):
        def task():
            for mid in mids:
                try:
                    r = requests.get(f"{self.base}/Mod/{mid}", params={"_csvProperties": "_nDownloadCount,_nViewCount,_nLikeCount"}, headers=self.headers, timeout=6)
                    if r.status_code == 200:
                        d = r.json()
                        if d and isinstance(d, dict):
                            d["_idRow"] = mid
                            callback(d)
                except: pass
        threading.Thread(target=task, daemon=True).start()

    def fetch_quick_download(self, mid):
        def task():
            print(f"[GBApiWorker] Fetching quick download info for mod ID {mid}...")
            data = self._get(f"/Mod/{mid}", {"_csvProperties": "_aFiles"})
            if data and "_aFiles" in data and data["_aFiles"]:
                f = list(data["_aFiles"].values())[0] if isinstance(data["_aFiles"], dict) else data["_aFiles"][0]
                url = f"bmod://Mod,{mid},{f.get('_idRow')}"
                print(f"[GBApiWorker] Quick file ready: {url} -> {f.get('_sFile')}")
                self.quick_file_ready.emit(url, f.get("_sFile", "Unknown.zip"))
            else:
                print(f"[GBApiWorker ERROR] Quick download failed: No files found for mod {mid}")
        threading.Thread(target=task, daemon=True).start()


class CategorySidebarCompact(QFrame):
    category_selected = Signal(object) 

    def __init__(self, api, img_cache, parent=None):
        super().__init__(parent)
        self.api = api
        self.img_cache = img_cache
        self.setFixedWidth(176)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("""
            QFrame {
                background: #18181c;
                border: none;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(6)
        
        # Title Label (English)
        self.lbl_title = QLabel("CATEGORIES")
        self.lbl_title.setStyleSheet("color: #8a8a93; font-size: 11px; font-weight: bold; letter-spacing: 1px; background: transparent; border: none;")
        layout.addWidget(self.lbl_title)

        # Breadcrumb trail label (English)
        self.lbl_breadcrumb = QLabel("All Categories")
        self.lbl_breadcrumb.setStyleSheet("color: #3584e4; font-size: 11px; font-weight: bold; background: transparent; border: none;")
        self.lbl_breadcrumb.setWordWrap(True)
        layout.addWidget(self.lbl_breadcrumb)

        # Sorting ComboBox (English)
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Sort: Quantity", "Sort: A-Z", "Sort: Z-A"])
        self.sort_combo.setStyleSheet("""
            QComboBox {
                background: rgba(255, 255, 255, 0.06);
                color: #aaa;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 5px;
                padding: 2px 6px;
                font-size: 10px;
                font-weight: bold;
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView { background: #222; color: #fff; border: none; }
        """)
        self.sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        layout.addWidget(self.sort_combo)

        # Compact Back Button (English)
        self.btn_back = QPushButton("← Back")
        self.btn_back.setFixedHeight(26)
        self.btn_back.setCursor(Qt.PointingHandCursor)
        self.btn_back.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.07);
                color: #e0e0e0;
                border: none;
                border-radius: 5px;
                font-size: 11px;
                font-weight: bold;
                padding-left: 8px;
                text-align: left;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.14);
                color: #ffffff;
            }
        """)
        self.btn_back.clicked.connect(self._go_back)
        self.btn_back.hide()
        layout.addWidget(self.btn_back)

        # Category Scroll area (No borders / No vertical lines)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { background: transparent; border: none; } " + SCROLLBAR)
        
        self.content = QWidget()
        self.content.setStyleSheet("background: transparent; border: none;")
        self.vbox = QVBoxLayout(self.content)
        self.vbox.setContentsMargins(0, 2, 0, 6)
        self.vbox.setSpacing(3)
        self.vbox.setAlignment(Qt.AlignTop)
        self.scroll.setWidget(self.content)
        layout.addWidget(self.scroll)

        self.path = []
        self.active_cat_id = None
        self.last_categories_data = []

        self.api.categories_loaded.connect(self._on_categories)
        self.api.fetch_categories()
        
    def _clear(self):
        while self.vbox.count():
            w = self.vbox.takeAt(0).widget()
            if w: w.deleteLater()

    def _update_breadcrumbs(self):
        if not self.path:
            self.lbl_breadcrumb.setText("All Categories")
            self.btn_back.hide()
        else:
            trail = " > ".join([c.get("_sName", "") for c in self.path])
            self.lbl_breadcrumb.setText(trail)
            self.btn_back.show()

    def _on_sort_changed(self, idx):
        self._render_categories()

    def _on_categories(self, data):
        self.last_categories_data = data or []
        self._render_categories()

    def _render_categories(self):
        self._clear()
        self._update_breadcrumbs()

        # All Submissions button item (English)
        btn_all = QPushButton("All Submissions")
        btn_all.setFixedHeight(30)
        btn_all.setCursor(Qt.PointingHandCursor)
        is_all_active = (self.active_cat_id is None and not self.path)
        bg_style = "background: #3584e4; color: #ffffff;" if is_all_active else "background: transparent; color: #cccccc;"
        btn_all.setStyleSheet(f"""
            QPushButton {{
                {bg_style}
                border: none;
                border-radius: 5px;
                text-align: left;
                font-size: 11px;
                font-weight: bold;
                padding-left: 8px;
            }}
            QPushButton:hover {{
                background: {'#3584e4' if is_all_active else 'rgba(255, 255, 255, 0.08)'};
                color: #ffffff;
            }}
        """)
        btn_all.clicked.connect(self._select_all)
        self.vbox.addWidget(btn_all)

        data = list(self.last_categories_data)
        sort_mode = self.sort_combo.currentIndex()
        if sort_mode == 0:
            cats = sorted(data, key=lambda x: int(x.get("_nItemCount", 0)), reverse=True)
        elif sort_mode == 1:
            cats = sorted(data, key=lambda x: str(x.get("_sName", "")).lower())
        else:
            cats = sorted(data, key=lambda x: str(x.get("_sName", "")).lower(), reverse=True)

        for c in cats:
            cat_id = c.get("_idRow")
            name = c.get("_sName", "Unknown")
            ccount = c.get("_nCategoryCount", 0)
            icon_url = c.get("_sIconUrl", "")
            
            is_active = (self.active_cat_id == cat_id)

            btn = QPushButton()
            btn.setFixedHeight(32)
            btn.setCursor(Qt.PointingHandCursor)
            
            btn_bg = "background: #3584e4;" if is_active else "background: transparent;"
            btn.setStyleSheet(f"""
                QPushButton {{
                    {btn_bg}
                    border: none;
                    border-radius: 5px;
                }}
                QPushButton:hover {{
                    background: {'#3584e4' if is_active else 'rgba(255, 255, 255, 0.08)'};
                }}
            """)

            lay = QHBoxLayout(btn)
            lay.setContentsMargins(6, 0, 8, 0)
            lay.setSpacing(6)
            
            ico = QLabel()
            ico.setFixedSize(16, 16)
            ico.setStyleSheet("background: transparent; border: none;")
            lay.addWidget(ico)
            
            if icon_url:
                def set_icon(u, p, label=ico, e_url=icon_url):
                    if u == e_url and shiboken6.isValid(label):
                        px = QPixmap()
                        if px.load(p): label.setPixmap(px.scaled(16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                self.img_cache.image_ready.connect(set_icon)
                self.img_cache.get_image(icon_url)
            
            lbl_name = QLabel(name)
            name_color = "#ffffff" if is_active else "#dddddd"
            lbl_name.setStyleSheet(f"color: {name_color}; font-size: 11px; font-weight: bold; background: transparent; border: none;")
            lay.addWidget(lbl_name, 1)
                
            # Expand arrow indicator ONLY for subcategories (No item count numbers, no extra borders)
            if ccount > 0:
                lbl_arrow = QLabel("›")
                lbl_arrow.setStyleSheet("color: #4a90e2; font-size: 13px; font-weight: bold; background: transparent; border: none;")
                lay.addWidget(lbl_arrow)

            def make_handler(cat_item):
                has_subs = int(cat_item.get("_nCategoryCount") or 0) > 0
                return lambda: self._on_cat_clicked(cat_item, has_subs)

            btn.clicked.connect(make_handler(c))
            self.vbox.addWidget(btn)

    def _select_all(self):
        self.active_cat_id = None
        self.category_selected.emit(None)
        self._render_categories()

    def _on_cat_clicked(self, cat, has_subs):
        cat_id = cat.get("_idRow")
        self.active_cat_id = cat_id
        self.category_selected.emit(cat_id)
        if has_subs and cat not in self.path:
            self._go_deeper(cat)

    def _go_deeper(self, cat):
        self.path.append(cat)
        self.api.fetch_categories(cat.get("_idRow"))

    def _go_back(self):
        if self.path: self.path.pop()
        pid = self.path[-1].get("_idRow") if self.path else None
        self.active_cat_id = pid
        self.category_selected.emit(pid)
        self.api.fetch_categories(pid)


class TopCarouselWidget(QWidget):
    clicked = Signal(int)
    
    def __init__(self, api, img_cache, parent=None):
        super().__init__(parent)
        self.setFixedHeight(240)
        self.api = api
        self.img_cache = img_cache
        self.cards = []
        self.dots = []
        self.recs_data = []
        self.current_idx = 0
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)
        
        self.scroll = QScrollArea()
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("background: transparent; border: none;")
        self.scroll.setWidgetResizable(True)
        
        self.container = QWidget()
        self.container.setStyleSheet("background: transparent; border: none;")
        self.hlay = QHBoxLayout(self.container)
        self.hlay.setContentsMargins(160, 5, 160, 5)
        self.hlay.setSpacing(16)
        self.hlay.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        
        self.scroll.setWidget(self.container)
        main_layout.addWidget(self.scroll, 1)
        
        # Pagination Dots Row (Centered below carousel like in preview1.png)
        self.dots_widget = QWidget()
        self.dots_widget.setStyleSheet("background: transparent; border: none;")
        self.dots_lay = QHBoxLayout(self.dots_widget)
        self.dots_lay.setContentsMargins(0, 0, 0, 0)
        self.dots_lay.setSpacing(6)
        self.dots_lay.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.dots_widget)
        
        self.anim = QPropertyAnimation(self.scroll.horizontalScrollBar(), b"value")
        self.anim.setDuration(450)
        self.anim.setEasingCurve(QEasingCurve.InOutQuad)
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._scroll_next)
        
        self.api.featured_loaded.connect(self.load_featured)
        
    def get_featured_label(self, data):
        period = (data.get("_sPeriod") or "").lower()
        if period == "today": return "Best of today"
        elif period == "week": return "Best of this week"
        elif period == "month": return "Best of this month"
        elif period in ["3month", "6month", "6months"]: return "Best of this 6 months"
        elif period == "year": return "Best of this year"
        elif period in ["alltime", "all_time"]: return "Best of all time"
        
        feats = data.get("_aFeaturings") or []
        if feats and isinstance(feats, list) and len(feats) > 0:
            title = feats[0].get("_sTitle") or ""
            if title: return title
        return "Best of today"

    def load_featured(self, recs):
        while self.hlay.count():
            w = self.hlay.takeAt(0).widget()
            if w: w.deleteLater()
        while self.dots_lay.count():
            w = self.dots_lay.takeAt(0).widget()
            if w: w.deleteLater()
            
        self.cards.clear()
        self.dots.clear()
        self.recs_data = recs or []
        
        if not recs: return
        
        card_w, card_h = 480, 200
        
        for idx, data in enumerate(recs):
            w = QWidget()
            w.setFixedSize(card_w, card_h)
            w.setCursor(Qt.PointingHandCursor)
            mid = data.get("_idRow") or data.get("id")
            w.mousePressEvent = lambda e, m=mid: self.clicked.emit(m)
            
            is_nsfw = (
                data.get("_sInitialVisibility") in ["warn", "hide"] or
                data.get("_bIsNsfw") or
                "nsfw" in str(data.get("_sName", "")).lower() or
                "18+" in str(data.get("_sName", "")).lower()
            )

            wl = QVBoxLayout(w)
            wl.setContentsMargins(0, 0, 0, 0)
            
            thumb = QLabel(w)
            thumb.setFixedSize(card_w, card_h)
            thumb.setStyleSheet("background: #111; border-radius: 12px; border: none;")
            thumb.is_nsfw = is_nsfw
            wl.addWidget(thumb)
            
            overlay = QLabel(w)
            overlay.setFixedSize(card_w, card_h)
            overlay.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(0,0,0,0.5), stop:0.4 transparent, stop:1 rgba(0,0,0,0.88)); border-radius: 12px; border: none;")
            olay = QVBoxLayout(overlay)
            olay.setContentsMargins(14, 14, 14, 14)
            
            # Top Header Row in Overlay: Period Badge & Red NSFW Badge (left) & Submitter Avatar (right)
            top_row = QHBoxLayout()
            top_row.setContentsMargins(0, 0, 0, 0)
            top_row.setSpacing(6)
            
            period_str = self.get_featured_label(data)
            lbl_top = QLabel(period_str)
            lbl_top.setStyleSheet("color: #fff; font-size: 11px; font-weight: bold; background: rgba(0,0,0,0.65); padding: 4px 10px; border-radius: 6px; border: none;")
            top_row.addWidget(lbl_top, 0, Qt.AlignLeft)
            
            if is_nsfw:
                lbl_nsfw = QLabel("NSFW")
                lbl_nsfw.setStyleSheet("color: #ffffff; background: #dc2626; font-size: 10px; font-weight: bold; padding: 4px 8px; border-radius: 6px; border: none;")
                top_row.addWidget(lbl_nsfw, 0, Qt.AlignLeft)

            top_row.addStretch()
            
            # Submitter Avatar Icon at top right
            sub_avatar = QLabel()
            sub_avatar.setFixedSize(24, 24)
            sub_avatar.setStyleSheet("background: rgba(255,255,255,0.1); border-radius: 12px;")
            top_row.addWidget(sub_avatar, 0, Qt.AlignRight)
            
            submitter = data.get("_aSubmitter") or {}
            avatar_url = submitter.get("_sAvatarUrl", "") or submitter.get("_sHdAvatarUrl", "")
            if avatar_url:
                def set_av(u, p, label=sub_avatar, expected=avatar_url):
                    if u == expected and shiboken6.isValid(label):
                        px = QPixmap()
                        if px.load(p): label.setPixmap(get_rounded_pixmap(px, 24, 24, radius=12))
                self.img_cache.image_ready.connect(set_av)
                self.img_cache.get_image(avatar_url)
            
            olay.addLayout(top_row)
            olay.addStretch()
            
            # Bottom Info Row: Mod Title & Subtitle/Description
            lbl_bot = QLabel(data.get("_sName", "Unknown"))
            lbl_bot.setStyleSheet("color: #fff; font-size: 15px; font-weight: bold; background: transparent; border: none;")
            olay.addWidget(lbl_bot)
            
            desc_text = data.get("_sDescription", "")
            if desc_text:
                lbl_desc = QLabel(desc_text)
                lbl_desc.setStyleSheet("color: #cccccc; font-size: 11px; background: transparent; border: none;")
                olay.addWidget(lbl_desc)
            
            self.hlay.addWidget(w)
            self.cards.append(w)
            
            # Load High Quality Cover Image (_sImageUrl or preview image)
            img_url = data.get("_sImageUrl", "")
            if not img_url:
                imgs = (data.get("_aPreviewMedia") or {}).get("_aImages", [])
                if imgs and isinstance(imgs, list):
                    base = imgs[0].get("_sBaseUrl", "")
                    fn = imgs[0].get("_sFile", "")
                    if base and fn: img_url = f"{base}/{fn}"
                    
            if img_url:
                def set_img(u, p, t=thumb, expected=img_url):
                    if u == expected and shiboken6.isValid(t):
                        px = QPixmap()
                        if px.load(p) and not px.isNull():
                            t.pixmap_original = px
                            self.update_thumb_nsfw(t)

                self.img_cache.image_ready.connect(set_img)
                self.img_cache.get_image(img_url)
                
            # Dot indicator button
            dot = QPushButton()
            dot.setFixedSize(6, 6)
            dot.setCursor(Qt.PointingHandCursor)
            dot.setStyleSheet("QPushButton { background: rgba(255,255,255,0.25); border: none; border-radius: 3px; } QPushButton:hover { background: #ffffff; }")
            def make_dot_handler(i_idx):
                return lambda *args: self._scroll_to(i_idx)
            dot.clicked.connect(make_dot_handler(idx))
            self.dots_lay.addWidget(dot)
            self.dots.append(dot)

        self._update_dots(0)
        self._update_margins()
        self.timer.start(5000)

    def update_thumb_nsfw(self, t):
        if not shiboken6.isValid(t) or not hasattr(t, 'pixmap_original') or t.pixmap_original.isNull(): return
        if getattr(t, 'is_nsfw', False) and LoaderConfig().nsfwFilter:
            small = t.pixmap_original.scaled(20, 20, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            blurred = small.scaled(480, 200, Qt.IgnoreAspectRatio, Qt.FastTransformation)
            t.setPixmap(get_rounded_pixmap(blurred, 480, 200, radius=12))
        else:
            t.setPixmap(get_rounded_pixmap(t.pixmap_original, 480, 200, radius=12))

    def update_nsfw_display(self):
        for w in self.cards:
            for child in w.findChildren(QLabel):
                if hasattr(child, 'pixmap_original'):
                    self.update_thumb_nsfw(child)

    def _update_margins(self):
        vp_w = self.scroll.viewport().width()
        side_pad = max(20, (vp_w - 480) // 2)
        self.hlay.setContentsMargins(side_pad, 5, side_pad, 5)

    def resizeEvent(self, e):
        self._update_margins()
        super().resizeEvent(e)
        
    def _update_dots(self, active_idx):
        for idx, dot in enumerate(self.dots):
            if idx == active_idx:
                dot.setFixedSize(14, 6)
                dot.setStyleSheet("background: #ffffff; border: none; border-radius: 3px;")
            else:
                dot.setFixedSize(6, 6)
                dot.setStyleSheet("background: rgba(255,255,255,0.3); border: none; border-radius: 3px;")

    def _scroll_to(self, idx):
        if not self.cards or idx >= len(self.cards): return
        self.current_idx = idx
        self._update_dots(self.current_idx)
        card_w = 480
        spacing = 16
        target_x = self.current_idx * (card_w + spacing)
        sb = self.scroll.horizontalScrollBar()
        self.anim.setStartValue(sb.value())
        self.anim.setEndValue(target_x)
        self.anim.start()

    def _scroll_next(self):
        if not self.cards: return
        next_idx = (self.current_idx + 1) % len(self.cards)
        self._scroll_to(next_idx)


from ..utils.config import LoaderConfig


class ModCardWidget(QFrame):
    clicked = Signal(int)
    quick_download = Signal(int)
    category_clicked = Signal(int)
    
    def __init__(self, data, img_cache, is_downloaded=False, parent=None):
        super().__init__(parent)
        self.mid = int(data.get("_idRow") or data.get("id") or 0)
        self.data = data
        self.is_downloaded = is_downloaded
        self.is_nsfw = (
            data.get("_sInitialVisibility") in ["warn", "hide"] or
            data.get("_bIsNsfw") or
            "nsfw" in str(data.get("_sName", "")).lower() or
            "18+" in str(data.get("_sName", "")).lower()
        )
        
        self.setAttribute(Qt.WA_StyledBackground, True)
        
        w, h = 188, 252
        self.setFixedSize(w, h)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(f"QFrame {{ background: {BG_CARD}; border-radius: 10px; border: 1px solid rgba(255,255,255,0.08); }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(0)
        
        # 1. Thumbnail Container (Supports NSFW Blur & Red NSFW Badge)
        tw = w - 12
        th = int(tw * 9/16)
        self.thumb_container = QWidget()
        self.thumb_container.setFixedSize(tw, th)
        
        self.thumb = QLabel(self.thumb_container)
        self.thumb.setFixedSize(tw, th) 
        self.thumb.setStyleSheet("background: #111; border-radius: 6px; border: none;")
        self.thumb.setAlignment(Qt.AlignCenter)
        
        if self.is_nsfw:
            lbl_nsfw = QLabel("NSFW", self.thumb_container)
            lbl_nsfw.setStyleSheet("color: #ffffff; background: #dc2626; font-size: 9px; font-weight: bold; padding: 2px 5px; border-radius: 4px; border: none;")
            lbl_nsfw.move(6, 6)
            lbl_nsfw.raise_()

        layout.addWidget(self.thumb_container)
        
        # Inner Content Layout (Tightly joins Title, Author, Stats, and Category Badges)
        info_widget = QWidget()
        info_widget.setStyleSheet("background: transparent; border: none;")
        info_lay = QVBoxLayout(info_widget)
        info_lay.setContentsMargins(0, 2, 0, 0)
        info_lay.setSpacing(1)
        
        # 2. Title
        self.title = QLabel(data.get("_sName", "Unknown"))
        self.title.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.title.setStyleSheet("color: #fff; background: transparent; border: none; padding: 0px; margin: 0px;")
        self.title.setWordWrap(True)
        self.title.setMaximumHeight(26)
        self.title.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        info_lay.addWidget(self.title)
        
        # 3. Author
        author = data.get("_aSubmitter", {}).get("_sName", "Unknown")
        lbl_auth = QLabel(author)
        lbl_auth.setStyleSheet("color: #888; font-size: 9px; background: transparent; border: none; padding: 0px; margin: 0px;")
        info_lay.addWidget(lbl_auth)
        
        # 4. Stats Row
        stats_widget = QWidget()
        stats_widget.setStyleSheet("background: transparent; border: none; padding: 0px; margin-top: 1px;")
        slay = QHBoxLayout(stats_widget)
        slay.setContentsMargins(0, 0, 0, 0)
        slay.setSpacing(4)
        
        def inline_stat(ico_name, val):
            w_stat = QWidget()
            w_stat.setStyleSheet("background: transparent; border: none;")
            l_stat = QHBoxLayout(w_stat)
            l_stat.setContentsMargins(0,0,0,0)
            l_stat.setSpacing(3)
            
            ic = QLabel()
            ic.setPixmap(get_icon_pixmap(ico_name, 11))
            ic.setStyleSheet("background: transparent;")
            vl = QLabel(fmt_num(val))
            vl.setStyleSheet("color: #aaa; font-size: 9px; background: transparent;")
            
            l_stat.addWidget(ic)
            l_stat.addWidget(vl)
            return w_stat, vl

        self.like_stat_w, self.like_val_label = inline_stat("heart-symbolic", data.get("_nLikeCount", 0))
        self.view_stat_w, self.view_val_label = inline_stat("eye-symbolic", data.get("_nViewCount", 0))
        self.dl_stat_w, self.dl_val_label = inline_stat("download-symbolic", data.get("_nDownloadCount", 0))

        slay.addWidget(self.like_stat_w)
        slay.addWidget(self.view_stat_w)
        slay.addWidget(self.dl_stat_w)
        slay.addStretch()
        
        info_lay.addWidget(stats_widget)

        # 5. Category & Subcategory Pill Badges (With 5px Top Margin)
        cat_tuples = extract_mod_categories(data)
        if cat_tuples:
            cats_widget = QWidget()
            cats_widget.setFixedHeight(23)
            cats_widget.setStyleSheet("background: transparent; border: none;")
            clay = QHBoxLayout(cats_widget)
            clay.setContentsMargins(0, 5, 0, 0)
            clay.setSpacing(4)
            for cid, cname in cat_tuples:
                pill = CategoryBadgePill(cid, cname, self)
                pill.badge_clicked.connect(self.category_clicked)
                clay.addWidget(pill)
            clay.addStretch()
            info_lay.addWidget(cats_widget)

        layout.addWidget(info_widget)
        layout.addStretch(1)
        
        # 6. Download Button
        self.btn_dl = QPushButton("Download ")
        self.btn_dl.setCursor(Qt.PointingHandCursor)
        self.btn_dl.setFixedHeight(26)
        self.btn_dl.clicked.connect(self._on_dl_clicked)
        
        if is_downloaded:
            self.set_state("downloaded")
        else:
            self.set_state("download")
        
        layout.addWidget(self.btn_dl)
        
        # Fetch thumbnail
        imgs = (data.get("_aPreviewMedia") or {}).get("_aImages", [])
        if imgs and isinstance(imgs, list):
            base = imgs[0].get("_sBaseUrl", "")
            fn = imgs[0].get("_sFile220", "") or imgs[0].get("_sFile", "")
            if base and fn:
                url = f"{base}/{fn}"
                img_cache.image_ready.connect(self._on_image)
                img_cache.get_image(url)
    def update_stats(self, stat_data):
        if not shiboken6.isValid(self): return
        dls = stat_data.get("_nDownloadCount")
        likes = stat_data.get("_nLikeCount")
        views = stat_data.get("_nViewCount")
        if dls is not None and hasattr(self, 'dl_val_label') and shiboken6.isValid(self.dl_val_label):
            self.dl_val_label.setText(fmt_num(dls))
        if likes is not None and hasattr(self, 'like_val_label') and shiboken6.isValid(self.like_val_label):
            self.like_val_label.setText(fmt_num(likes))
        if views is not None and hasattr(self, 'view_val_label') and shiboken6.isValid(self.view_val_label):
            self.view_val_label.setText(fmt_num(views))

    def set_state(self, state, text=""):
        if not shiboken6.isValid(self) or not hasattr(self, 'btn_dl'): return
        self.btn_dl.setEnabled(True)
        if state == "downloaded":
            self.btn_dl.setText("Downloaded ")
            self.btn_dl.setIcon(QIcon(get_icon_pixmap("checkmark-symbolic", 12)))
            self.btn_dl.setLayoutDirection(Qt.RightToLeft)
            self.btn_dl.setStyleSheet("""
                QPushButton { background: #2e7d32; color: #fff; border: none; border-radius: 6px; font-size: 11px; font-weight: bold; }
                QPushButton:hover { background: #388e3c; }
            """)
        elif state == "downloading":
            pct = text if text else "0%"
            self.btn_dl.setText(f"Downloading... {pct}")
            self.btn_dl.setIcon(QIcon())
            self.btn_dl.setStyleSheet("""
                QPushButton { background: #eab308; color: #000; border: none; border-radius: 6px; font-size: 11px; font-weight: bold; }
                QPushButton:hover { background: #facc15; }
            """)
        elif state == "incompatible":
            self.btn_dl.setText("Incompatible ")
            self.btn_dl.setIcon(QIcon(get_icon_pixmap("dialog-warning-symbolic", 12)))
            self.btn_dl.setLayoutDirection(Qt.RightToLeft)
            self.btn_dl.setStyleSheet("""
                QPushButton { background: #d97706; color: #fff; border: none; border-radius: 6px; font-size: 11px; font-weight: bold; }
                QPushButton:hover { background: #f59e0b; }
            """)
        elif state == "error":
            self.btn_dl.setText("Error, Retry?")
            self.btn_dl.setIcon(QIcon(get_icon_pixmap("view-refresh-symbolic", 12)))
            self.btn_dl.setLayoutDirection(Qt.RightToLeft)
            self.btn_dl.setStyleSheet("""
                QPushButton { background: #dc2626; color: #fff; border: none; border-radius: 6px; font-size: 11px; font-weight: bold; }
                QPushButton:hover { background: #ef4444; }
            """)
        else: # "download"
            self.btn_dl.setText("Download ")
            self.btn_dl.setIcon(QIcon(get_icon_pixmap("download-symbolic", 12)))
            self.btn_dl.setLayoutDirection(Qt.RightToLeft)
            self.btn_dl.setStyleSheet("""
                QPushButton { background: #3584e4; color: #fff; border: none; border-radius: 6px; font-size: 11px; font-weight: bold; }
                QPushButton:hover { background: #4a90e2; }
            """)

    def set_downloaded_state(self, downloaded):
        if downloaded:
            self.set_state("downloaded")
        else:
            self.set_state("download")

    def _on_dl_clicked(self):
        self.set_state("downloading", "0%")
        self.quick_download.emit(self.mid)

    def _on_image(self, url, path):
        if not shiboken6.isValid(self): return
        imgs = (self.data.get("_aPreviewMedia") or {}).get("_aImages", [])
        if not imgs: return
        expected = f"{imgs[0].get('_sBaseUrl', '')}/{imgs[0].get('_sFile220', '') or imgs[0].get('_sFile', '')}"
        if url == expected:
            pix = QPixmap()
            if pix.load(path) and not pix.isNull():
                self.pixmap_original = pix
                self.update_nsfw_display()

    def update_nsfw_display(self):
        if not shiboken6.isValid(self) or not hasattr(self, 'pixmap_original') or self.pixmap_original.isNull(): return
        tw, th = self.thumb.width(), self.thumb.height()
        if self.is_nsfw and LoaderConfig().nsfwFilter:
            small = self.pixmap_original.scaled(12, 12, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            blurred = small.scaled(tw, th, Qt.IgnoreAspectRatio, Qt.FastTransformation)
            self.thumb.setPixmap(get_rounded_pixmap(blurred, tw, th, radius=6))
        else:
            self.thumb.setPixmap(get_rounded_pixmap(self.pixmap_original, tw, th, radius=6))

    def mousePressEvent(self, e):
        if not self.btn_dl.underMouse():
            self.clicked.emit(self.mid)
        super().mousePressEvent(e)


class MarqueeLabel(QLabel):
    def __init__(self, text="", parent=None, always_scroll=False):
        super().__init__(text, parent)
        self._full_text = text
        self._offset = 0
        self.always_scroll = always_scroll
        self._timer = QTimer(self)
        self._timer.setInterval(25)
        self._timer.timeout.connect(self._step)
        self.setMouseTracking(True)
        self.setTextFormat(Qt.PlainText)
        self._update_static_text()
        if self.always_scroll:
            self._timer.start()

    def setText(self, text):
        self._full_text = text
        self._offset = 0
        self._update_static_text()
        if self.always_scroll and not self._timer.isActive():
            self._timer.start()

    def _update_static_text(self):
        if not self.always_scroll:
            if len(self._full_text) > 24:
                super().setText(self._full_text[:24] + "...")
            else:
                super().setText(self._full_text)
        else:
            super().setText(self._full_text)

    def enterEvent(self, e):
        if not self.always_scroll:
            fm = self.fontMetrics()
            if len(self._full_text) > 24 or fm.horizontalAdvance(self._full_text) > self.width():
                self._timer.start()
        super().enterEvent(e)

    def leaveEvent(self, e):
        if not self.always_scroll:
            self._timer.stop()
            self._offset = 0
            self._update_static_text()
            self.update()
        super().leaveEvent(e)

    def _step(self):
        fm = self.fontMetrics()
        loop_str = self._full_text + "              "
        loop_w = fm.horizontalAdvance(loop_str)
        if loop_w > 0:
            self._offset = (self._offset + 2) % loop_w
        self.update()

    def paintEvent(self, e):
        if not self._timer.isActive():
            super().paintEvent(e)
            return
        
        painter = QPainter(self)
        painter.setClipRect(self.rect())
        painter.setPen(self.palette().color(self.foregroundRole()))
        painter.setFont(self.font())
        fm = self.fontMetrics()
        y = (self.height() + fm.ascent() - fm.descent()) // 2
        
        loop_str = self._full_text + "              "
        loop_w = fm.horizontalAdvance(loop_str)
        
        painter.drawText(-self._offset, y, loop_str)
        painter.drawText(-self._offset + loop_w, y, loop_str)


class ModListItemWidget(QFrame):
    clicked = Signal(int)
    quick_download = Signal(int)
    category_clicked = Signal(int)
    
    def __init__(self, data, img_cache, is_downloaded=False, parent=None):
        super().__init__(parent)
        self.mid = int(data.get("_idRow") or data.get("id") or 0)
        self.data = data
        self.is_downloaded = is_downloaded
        self.is_nsfw = (
            data.get("_sInitialVisibility") in ["warn", "hide"] or
            data.get("_bIsNsfw") or
            "nsfw" in str(data.get("_sName", "")).lower() or
            "18+" in str(data.get("_sName", "")).lower()
        )
        
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedHeight(64)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(f"QFrame {{ background: {BG_CARD}; border-radius: 8px; border: 1px solid rgba(255,255,255,0.08); }} QFrame:hover {{ background: {BG_HOVER}; }}")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)
        
        # 1. Super Small Thumbnail Container (64x36) + Red NSFW Badge
        tw, th = 64, 36
        self.thumb_container = QWidget()
        self.thumb_container.setFixedSize(tw, th)
        
        self.thumb = QLabel(self.thumb_container)
        self.thumb.setFixedSize(tw, th) 
        self.thumb.setStyleSheet("background: #111; border-radius: 4px; border: none;")
        self.thumb.setAlignment(Qt.AlignCenter)
        
        if self.is_nsfw:
            lbl_nsfw = QLabel("NSFW", self.thumb_container)
            lbl_nsfw.setStyleSheet("color: #ffffff; background: #dc2626; font-size: 8px; font-weight: bold; padding: 1px 4px; border-radius: 3px; border: none;")
            lbl_nsfw.move(3, 3)
            lbl_nsfw.raise_()

        layout.addWidget(self.thumb_container, 0, Qt.AlignVCenter)
        
        # 2. Title, Author, Stats & Category Pills Column
        info_lay = QVBoxLayout()
        info_lay.setContentsMargins(0, 0, 0, 0)
        info_lay.setSpacing(0)
        
        self.title = MarqueeLabel(data.get("_sName", "Unknown"))
        self.title.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.title.setStyleSheet("color: #fff; background: transparent; border: none;")
        
        author = data.get("_aSubmitter", {}).get("_sName", "Unknown")
        lbl_auth = QLabel(author)
        lbl_auth.setStyleSheet("color: #888; font-size: 8px; background: transparent; border: none;")
        
        # Stats row directly below author
        stats_widget = QWidget()
        stats_widget.setStyleSheet("background: transparent; border: none;")
        slay = QHBoxLayout(stats_widget)
        slay.setContentsMargins(0, 1, 0, 0)
        slay.setSpacing(6)
        
        def inline_stat(ico_name, val):
            w_stat = QWidget()
            w_stat.setStyleSheet("background: transparent; border: none;")
            l_stat = QHBoxLayout(w_stat)
            l_stat.setContentsMargins(0, 0, 0, 0)
            l_stat.setSpacing(2)
            
            ic = QLabel()
            ic.setPixmap(get_icon_pixmap(ico_name, 10))
            ic.setStyleSheet("background: transparent;")
            vl = QLabel(fmt_num(val))
            vl.setStyleSheet("color: #aaa; font-size: 8px; background: transparent;")
            
            l_stat.addWidget(ic)
            l_stat.addWidget(vl)
            return w_stat, vl

        self.like_stat_w, self.like_val_label = inline_stat("heart-symbolic", data.get("_nLikeCount", 0))
        self.view_stat_w, self.view_val_label = inline_stat("eye-symbolic", data.get("_nViewCount", 0))
        self.dl_stat_w, self.dl_val_label = inline_stat("download-symbolic", data.get("_nDownloadCount", 0))

        slay.addWidget(self.like_stat_w)
        slay.addWidget(self.view_stat_w)
        slay.addWidget(self.dl_stat_w)
        slay.addStretch()

        info_lay.addWidget(self.title)
        info_lay.addWidget(lbl_auth)
        info_lay.addWidget(stats_widget)

        # Category & Subcategory Pills for List View
        cat_tuples = extract_mod_categories(data)
        if cat_tuples:
            cats_widget = QWidget()
            cats_widget.setStyleSheet("background: transparent; border: none;")
            clay = QHBoxLayout(cats_widget)
            clay.setContentsMargins(0, 1, 0, 0)
            clay.setSpacing(3)
            for cid, cname in cat_tuples:
                pill = CategoryBadgePill(cid, cname, self)
                pill.badge_clicked.connect(self.category_clicked)
                clay.addWidget(pill)
            clay.addStretch()
            info_lay.addWidget(cats_widget)
        
        layout.addLayout(info_lay, 1)
        
        # 3. Icon-Only Download Button for List View (30x28)
        self.btn_dl = QPushButton()
        self.btn_dl.setCursor(Qt.PointingHandCursor)
        self.btn_dl.setFixedSize(30, 28)
        self.btn_dl.clicked.connect(self._on_dl_clicked)
        
        if is_downloaded:
            self.set_state("downloaded")
        else:
            self.set_state("download")
        
        layout.addWidget(self.btn_dl, 0, Qt.AlignVCenter)
        
        # Fetch thumbnail
        imgs = (data.get("_aPreviewMedia") or {}).get("_aImages", [])
        if imgs and isinstance(imgs, list):
            base = imgs[0].get("_sBaseUrl", "")
            fn = imgs[0].get("_sFile220", "") or imgs[0].get("_sFile", "")
            if base and fn:
                url = f"{base}/{fn}"
                img_cache.image_ready.connect(self._on_image)
                img_cache.get_image(url)

    def update_stats(self, stat_data):
        if not shiboken6.isValid(self): return
        dls = stat_data.get("_nDownloadCount")
        likes = stat_data.get("_nLikeCount")
        views = stat_data.get("_nViewCount")
        if dls is not None and hasattr(self, 'dl_val_label') and shiboken6.isValid(self.dl_val_label):
            self.dl_val_label.setText(fmt_num(dls))
        if likes is not None and hasattr(self, 'like_val_label') and shiboken6.isValid(self.like_val_label):
            self.like_val_label.setText(fmt_num(likes))
        if views is not None and hasattr(self, 'view_val_label') and shiboken6.isValid(self.view_val_label):
            self.view_val_label.setText(fmt_num(views))

    def set_state(self, state, text=""):
        if not shiboken6.isValid(self) or not hasattr(self, 'btn_dl'): return
        self.btn_dl.setEnabled(True)
        self.btn_dl.setText("") # Icon-only in List View!
        
        if state == "downloaded":
            self.btn_dl.setToolTip("Downloaded")
            self.btn_dl.setIcon(QIcon(get_icon_pixmap("checkmark-symbolic", 14)))
            self.btn_dl.setStyleSheet("""
                QPushButton { background: #2e7d32; border: none; border-radius: 6px; }
                QPushButton:hover { background: #388e3c; }
            """)
        elif state == "downloading":
            pct = text if text else "0%"
            self.btn_dl.setToolTip(f"Downloading... {pct}")
            self.btn_dl.setIcon(QIcon(get_icon_pixmap("download-symbolic", 14)))
            self.btn_dl.setStyleSheet("""
                QPushButton { background: #eab308; border: none; border-radius: 6px; }
                QPushButton:hover { background: #facc15; }
            """)
        elif state == "incompatible":
            self.btn_dl.setToolTip("Incompatible Mod")
            self.btn_dl.setIcon(QIcon(get_icon_pixmap("dialog-warning-symbolic", 14)))
            self.btn_dl.setStyleSheet("""
                QPushButton { background: #d97706; border: none; border-radius: 6px; }
                QPushButton:hover { background: #f59e0b; }
            """)
        elif state == "error":
            self.btn_dl.setToolTip("Download Error - Click to Retry")
            self.btn_dl.setIcon(QIcon(get_icon_pixmap("view-refresh-symbolic", 14)))
            self.btn_dl.setStyleSheet("""
                QPushButton { background: #dc2626; border: none; border-radius: 6px; }
                QPushButton:hover { background: #ef4444; }
            """)
        else: # "download"
            self.btn_dl.setToolTip("Download Mod")
            self.btn_dl.setIcon(QIcon(get_icon_pixmap("download-symbolic", 14)))
            self.btn_dl.setStyleSheet("""
                QPushButton { background: #3584e4; border: none; border-radius: 6px; }
                QPushButton:hover { background: #4a90e2; }
            """)

    def set_downloaded_state(self, downloaded):
        if downloaded:
            self.set_state("downloaded")
        else:
            self.set_state("download")

    def _on_dl_clicked(self):
        self.set_state("downloading", "0%")
        self.quick_download.emit(self.mid)

    def _on_image(self, url, path):
        if not shiboken6.isValid(self): return
        imgs = (self.data.get("_aPreviewMedia") or {}).get("_aImages", [])
        if not imgs: return
        expected = f"{imgs[0].get('_sBaseUrl', '')}/{imgs[0].get('_sFile220', '') or imgs[0].get('_sFile', '')}"
        if url == expected:
            pix = QPixmap()
            if pix.load(path) and not pix.isNull():
                self.pixmap_original = pix
                self.update_nsfw_display()

    def update_nsfw_display(self):
        if not shiboken6.isValid(self) or not hasattr(self, 'pixmap_original') or self.pixmap_original.isNull(): return
        tw, th = self.thumb.width(), self.thumb.height()
        if self.is_nsfw and LoaderConfig().nsfwFilter:
            small = self.pixmap_original.scaled(12, 12, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            blurred = small.scaled(tw, th, Qt.IgnoreAspectRatio, Qt.FastTransformation)
            self.thumb.setPixmap(get_rounded_pixmap(blurred, tw, th, radius=4))
        else:
            self.thumb.setPixmap(get_rounded_pixmap(self.pixmap_original, tw, th, radius=4))

    def mousePressEvent(self, e):
        if not self.btn_dl.underMouse():
            self.clicked.emit(self.mid)
        super().mousePressEvent(e)


class ModDetailPanel(QWidget):
    back_clicked = Signal()
    download_clicked = Signal(str, str) 
    category_clicked = Signal(int)
    
    def __init__(self, img_cache, parent=None):
        super().__init__(parent)
        self.img_cache = img_cache
        self.mid = None
        self.is_installed = False
        self.api_data = None
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.top_header_bar = QFrame()
        self.top_header_bar.setFixedHeight(50)
        self.top_header_bar.setStyleSheet(f"background: {BG_MAIN}; border-bottom: 1px solid rgba(255,255,255,0.08);")
        hlay = QHBoxLayout(self.top_header_bar)
        hlay.setContentsMargins(15, 0, 15, 0)
        
        btn_back = QPushButton("←")
        btn_back.setFixedSize(36, 36)
        btn_back.setStyleSheet(BTN_SECONDARY)
        btn_back.clicked.connect(self.back_clicked)
        hlay.addWidget(btn_back)
        
        self.title_header = QLabel("")
        self.title_header.setStyleSheet("color: #fff; font-size: 14px; font-weight: bold; background: transparent;")
        self.title_header.setAlignment(Qt.AlignCenter)
        hlay.addWidget(self.title_header, 1)
        
        self.btn_web = QPushButton("Open in Browser ")
        self.btn_web.setIcon(QIcon(get_icon_pixmap("external-link-symbolic", 12)))
        self.btn_web.setLayoutDirection(Qt.RightToLeft)
        self.btn_web.setStyleSheet(BTN_SECONDARY)
        self.btn_web.clicked.connect(self._open_web)
        hlay.addWidget(self.btn_web)
        layout.addWidget(self.top_header_bar)
        
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet(SCROLLBAR + f"QScrollArea {{ background: {BG_MAIN}; border: none; }}")
        
        self.content = QWidget()
        self.content.setStyleSheet(f"background: {BG_MAIN}; border: none;")
        self.vbox = QVBoxLayout(self.content)
        self.vbox.setContentsMargins(40, 30, 40, 40)
        self.vbox.setSpacing(20)
        
        self.top_row = QHBoxLayout()
        self.top_row.setSpacing(25)
        
        self.banner = QLabel()
        self.banner.setFixedSize(360, 200) 
        self.banner.setStyleSheet("background: #111; border-radius: 10px; border: none;")
        self.banner.setAlignment(Qt.AlignCenter)
        self.top_row.addWidget(self.banner, 0, Qt.AlignTop)
        
        self.info_panel = QVBoxLayout()
        self.info_panel.setSpacing(12)
        
        self.title = QLabel("")
        self.title.setFont(QFont("Segoe UI", 20, QFont.Bold))
        self.title.setStyleSheet("color: #fff; background: transparent; border: none;")
        self.title.setWordWrap(True)
        self.info_panel.addWidget(self.title)
        
        self.author_label = QLabel("")
        self.author_label.setStyleSheet("color: #aaa; font-size: 13px; background: transparent; border: none;")
        self.info_panel.addWidget(self.author_label)
        
        self.stats_row = QHBoxLayout()
        self.stats_row.setSpacing(10)
        self.stats_row.setAlignment(Qt.AlignLeft)
        
        def make_stat_widget(icon_name):
            w = QWidget()
            w.setStyleSheet("background: rgba(255, 255, 255, 0.08); border-radius: 8px; border: none;")
            l = QHBoxLayout(w)
            l.setContentsMargins(8, 4, 8, 4)
            l.setSpacing(6)
            ic = QLabel()
            ic.setPixmap(get_icon_pixmap(icon_name, 12))
            ic.setStyleSheet("background: transparent; border: none;")
            vl = QLabel("0")
            vl.setStyleSheet("color: #ccc; font-size: 12px; font-weight: bold; background: transparent; border: none;")
            l.addWidget(ic)
            l.addWidget(vl)
            return w, vl

        self.likes_w, self.likes_val = make_stat_widget("heart-symbolic")
        self.views_w, self.views_val = make_stat_widget("eye-symbolic")
        self.dls_w, self.dls_val = make_stat_widget("download-symbolic")
        
        self.stats_row.addWidget(self.likes_w)
        self.stats_row.addWidget(self.views_w)
        self.stats_row.addWidget(self.dls_w)
        self.stats_row.addStretch()
        self.info_panel.addLayout(self.stats_row)

        self.cats_container = QWidget()
        self.cats_container.setStyleSheet("background: transparent; border: none;")
        self.cats_lay = QHBoxLayout(self.cats_container)
        self.cats_lay.setContentsMargins(0, 4, 0, 0)
        self.cats_lay.setSpacing(8)
        self.cats_lay.setAlignment(Qt.AlignLeft)
        self.info_panel.addWidget(self.cats_container)
        
        self.files_container_widget = QWidget()
        self.files_container_widget.setStyleSheet("background: transparent; border: none;")
        self.files_container = QVBoxLayout(self.files_container_widget)
        self.files_container.setSpacing(8)
        self.files_container.setContentsMargins(0, 10, 0, 0)
        self.info_panel.addWidget(self.files_container_widget)
        
        self.info_panel.addStretch()
        self.top_row.addLayout(self.info_panel, 1)
        self.vbox.addLayout(self.top_row)
        
        # Requirements Container (Vertical List above Description)
        self.reqs_container = QWidget()
        self.reqs_container.setStyleSheet("background: transparent; border: none;")
        self.reqs_lay = QVBoxLayout(self.reqs_container)
        self.reqs_lay.setContentsMargins(0, 0, 0, 0)
        self.reqs_lay.setSpacing(6)
        self.reqs_lay.setAlignment(Qt.AlignLeft)
        self.vbox.addWidget(self.reqs_container)

        self.desc = QLabel("")
        self.desc.setWordWrap(True)
        self.desc.setStyleSheet("color: #ddd; font-size: 14px; background: transparent; border: none; line-height: 1.5;")
        self.desc.setTextFormat(Qt.PlainText)
        self.desc.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.vbox.addWidget(self.desc)
        
        self.vbox.addStretch()
        self.scroll.setWidget(self.content)
        layout.addWidget(self.scroll)

    def _open_web(self):
        if self.mid: webbrowser.open(f"https://gamebanana.com/mods/{self.mid}")

    def load_data(self, data, is_installed=False):
        if not shiboken6.isValid(self): return
        if not data: return
        self.mid = data.get("_idRow")
        self.is_installed = is_installed
        self.api_data = data
        
        name = data.get("_sName", "Unknown Mod")
        self.title.setText(name)
        self.title_header.setText(f"{name} - Mod")
        
        author = data.get("_aSubmitter", {}).get("_sName", "Unknown")
        self.author_label.setText(author)
        
        self.likes_val.setText(fmt_num(data.get('_nLikeCount', 0)))
        self.views_val.setText(fmt_num(data.get('_nViewCount', 0)))
        self.dls_val.setText(fmt_num(data.get('_nDownloadCount', 0)))
        
        while self.cats_lay.count():
            w = self.cats_lay.takeAt(0).widget()
            if w: w.deleteLater()

        cat_tuples = extract_mod_categories(data)
        if cat_tuples:
            for cid, cname in cat_tuples:
                pill = CategoryBadgePill(cid, cname, self)
                pill.badge_clicked.connect(self.category_clicked)
                self.cats_lay.addWidget(pill)
            self.cats_lay.addStretch()

        # Render Mod Requirements / Base Skin Requirements above description in list format
        reqs = data.get("_aRequirements") or data.get("requirements") or []
        if isinstance(reqs, dict): reqs = list(reqs.values())
        while self.reqs_lay.count():
            w = self.reqs_lay.takeAt(0).widget()
            if w: w.deleteLater()
            
        valid_reqs = []
        if reqs:
            for req in reqs:
                rname = extract_requirement_name(req)
                if rname and rname not in valid_reqs:
                    valid_reqs.append(rname)

        # Fallback: If no explicit API requirements found, scan description text for keywords ("over", "replaces", "replace")
        if not valid_reqs:
            raw_desc = data.get("_sText", "") or ""
            raw_desc = raw_desc.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n").replace("</p>", "\n\n").replace("</div>", "\n")
            clean_desc_text = re.sub(r"<[^>]+>", "", raw_desc).strip()
            valid_reqs = extract_requirements_from_text(clean_desc_text)

        if valid_reqs:
            lbl_req_head = QLabel("Requirements / Required Base Skin:")
            lbl_req_head.setStyleSheet("color: #ff8a65; font-size: 12px; font-weight: bold; background: transparent; border: none; margin-bottom: 2px;")
            self.reqs_lay.addWidget(lbl_req_head)
            for rname in valid_reqs:
                rpill = QLabel(f"⚠️  {rname}")
                rpill.setStyleSheet("color: #ffffff; background: rgba(227, 76, 34, 0.25); font-size: 11px; font-weight: bold; padding: 5px 10px; border-radius: 6px; border: 1px solid rgba(227, 76, 34, 0.5);")
                self.reqs_lay.addWidget(rpill)
            self.reqs_container.show()
        else:
            self.reqs_container.hide()

        raw = data.get("_sText", "") or ""
        raw = raw.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n").replace("</p>", "\n\n").replace("</div>", "\n")
        clean_text = re.sub(r"<[^>]+>", "", raw).strip()
        self.desc.setText(clean_text or "No description provided.")
        
        self.banner.clear()
        imgs = (data.get("_aPreviewMedia") or {}).get("_aImages", [])
        if imgs:
            base = imgs[0].get("_sBaseUrl", "")
            fn = imgs[0].get("_sFile", "")
            if base and fn:
                url = f"{base}/{fn}"
                self.img_cache.image_ready.connect(self._on_image)
                self.img_cache.get_image(url)
                
        self._build_files(data.get("_aFiles") or {})

    def _build_files(self, files_dict):
        while self.files_container.count():
            w = self.files_container.takeAt(0).widget()
            if w: w.deleteLater()
            
        files = files_dict
        if isinstance(files, dict): files = list(files.values())
        
        if not files: return
            
        for f in files:
            fname_str = f.get("_sFile", "Unknown file")
            btn_dl = QPushButton("Downloaded " if self.is_installed else "Download ")
            btn_dl.setCursor(Qt.PointingHandCursor)
            btn_dl.setLayoutDirection(Qt.RightToLeft)
            if self.is_installed:
                btn_dl.setStyleSheet("QPushButton { background: #2e7d32; color: #fff; border: none; border-radius: 6px; padding: 6px 14px; font-weight: bold; font-size: 12px; }")
                btn_dl.setIcon(QIcon(get_icon_pixmap("checkmark-symbolic", 12)))
            else:
                btn_dl.setStyleSheet(BTN_PRIMARY)
                btn_dl.setIcon(QIcon(get_icon_pixmap("download-symbolic", 12)))
            
            fid = f.get("_idRow")
            url = f"bmod://Mod,{self.mid},{fid}"
            btn_dl.clicked.connect(lambda *args, u=url, fn=fname_str: self.download_clicked.emit(u, fn))
            
            fs = f.get("_nFilesize", 0)
            size_str = f"{fs/(1024*1024):.1f} MB" if fs > 1024*1024 else f"{fs/1024:.1f} KB"
            flabel = QLabel(f"{fname_str} ({size_str})")
            flabel.setWordWrap(True)
            flabel.setStyleSheet("color: #888; font-size: 12px; background: transparent; border: none;")
            
            rlay = QHBoxLayout()
            rlay.setContentsMargins(0, 0, 0, 0)
            rlay.addWidget(btn_dl, 0)
            rlay.addWidget(flabel, 1)
            
            widg = QWidget()
            widg.setStyleSheet("background: transparent; border: none;")
            widg.setLayout(rlay)
            self.files_container.addWidget(widg)

    def _on_image(self, url, path):
        if not shiboken6.isValid(self): return
        if self.banner.width() > 0:
            pix = QPixmap()
            if pix.load(path) and not pix.isNull():
                self.banner.setPixmap(get_rounded_pixmap(pix, self.banner.width(), self.banner.height(), radius=10))


class ModDetailOverlay(QWidget):
    close_requested = Signal()

    def __init__(self, img_cache, parent=None):
        super().__init__(parent)
        self.img_cache = img_cache
        self.is_preview = False
        self.mid = None
        self.hide()
        
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 30, 40, 30)
        main_layout.setAlignment(Qt.AlignCenter)
        
        # Center Modal Box
        self.modal_box = QFrame(self)
        self.modal_box.setObjectName("ModalBoxContainer")
        self.modal_box.setStyleSheet(f"""
            QFrame#ModalBoxContainer {{
                background: {BG_MAIN};
                border-radius: 12px;
                border: 1px solid rgba(255,255,255,0.15);
            }}
        """)
        
        box_layout = QVBoxLayout(self.modal_box)
        box_layout.setContentsMargins(0, 0, 0, 0)
        box_layout.setSpacing(0)
        
        # Header with Title, Open Web Button, and prominent '✕' Close Button
        header = QFrame()
        header.setFixedHeight(48)
        header.setStyleSheet("background: rgba(255,255,255,0.03); border-bottom: 1px solid rgba(255,255,255,0.08); border-top-left-radius: 12px; border-top-right-radius: 12px;")
        hlay = QHBoxLayout(header)
        hlay.setContentsMargins(15, 0, 15, 0)
        
        self.lbl_modal_title = QLabel("Mod Details")
        self.lbl_modal_title.setStyleSheet("color: #fff; font-size: 14px; font-weight: bold; background: transparent; border: none;")
        hlay.addWidget(self.lbl_modal_title)
        hlay.addStretch()
        
        self.btn_web = QPushButton("Open in Browser ")
        self.btn_web.setIcon(QIcon(get_icon_pixmap("external-link-symbolic", 12)))
        self.btn_web.setLayoutDirection(Qt.RightToLeft)
        self.btn_web.setStyleSheet(BTN_SECONDARY)
        self.btn_web.clicked.connect(self._open_web)
        hlay.addWidget(self.btn_web)
        
        self.btn_close = QPushButton("✕")
        self.btn_close.setFixedSize(30, 30)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setStyleSheet("QPushButton { background: rgba(255,255,255,0.1); color: #fff; border: none; border-radius: 6px; font-size: 14px; font-weight: bold; } QPushButton:hover { background: #dc2626; }")
        self.btn_close.clicked.connect(self.close_overlay)
        hlay.addWidget(self.btn_close)
        
        box_layout.addWidget(header)
        
        # Inner Mod Detail Panel
        self.panel = ModDetailPanel(self.img_cache, self)
        self.panel.top_header_bar.hide() # Hide redundant sub-header bar!
        box_layout.addWidget(self.panel, 1)
        
        main_layout.addWidget(self.modal_box)

    def paintEvent(self, e):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 198))

    def mousePressEvent(self, e):
        if not self.modal_box.geometry().contains(e.pos()):
            self.close_overlay()
        super().mousePressEvent(e)

    def leaveEvent(self, e):
        if self.is_preview:
            self.close_overlay()
        super().leaveEvent(e)

    def _open_web(self):
        if self.mid: webbrowser.open(f"https://gamebanana.com/mods/{self.mid}")

    def show_mod(self, mid, is_preview=False):
        self.mid = mid
        self.is_preview = is_preview
        self.lbl_modal_title.setText("Mod Preview" if is_preview else "Mod Details")
        
        if self.parent():
            self.setGeometry(0, 0, self.parent().width(), self.parent().height())
            bw = min(780, max(360, self.parent().width() - 80))
            bh = min(620, max(300, self.parent().height() - 60))
            self.modal_box.setFixedSize(bw, bh)
            
        self.raise_()
        self.show()

    def close_overlay(self):
        self.hide()
        self.close_requested.emit()


class GameBananaFrame(QFrame):
    downloadMod = Signal(str, str)
    
    def __init__(self, modsPath=None, parent=None):
        super().__init__(parent)
        self.modsPath = modsPath
        self.installed_mods = []
        self.session_downloaded_mids = set()
        self.incompatible_mids = set()
        self.error_mids = set()
        self.raw_recs = []
        self.view_mode = "grid"
        
        # Purge any old persistent tracker files from disk so stale data is never restored
        try:
            tracker_file = os.path.join(os.environ.get("APPDATA", ""), "BModLoader", "gb_downloaded.json")
            metadata_file = os.path.join(os.environ.get("APPDATA", ""), "BModLoader", "gb_installed_meta.json")
            if os.path.exists(tracker_file): os.remove(tracker_file)
            if os.path.exists(metadata_file): os.remove(metadata_file)
        except Exception: pass

        self.api = GBApiWorker(self)
        self.img_cache = ImageCache(self)
        
        self.setStyleSheet(f"background: {BG_MAIN};")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.sidebar = CategorySidebarCompact(self.api, self.img_cache)
        self.sidebar.category_selected.connect(self._on_category_select)
        layout.addWidget(self.sidebar)
        
        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)
        
        # --- BROWSER PAGE ---
        self.browser_page = QWidget()
        blayout = QVBoxLayout(self.browser_page)
        blayout.setContentsMargins(0, 0, 0, 0)
        blayout.setSpacing(0)
        
        # Top Header Bar
        toolbar = QFrame()
        toolbar.setFixedHeight(55)
        toolbar.setStyleSheet(f"background: {BG_MAIN}; border-bottom: 1px solid rgba(255,255,255,0.08);")
        tlay = QHBoxLayout(toolbar)
        tlay.setContentsMargins(15, 8, 15, 8)
        tlay.setSpacing(10)
        
        # Background Download Bar Container
        self.dl_status_widget = QWidget()
        self.dl_status_widget.setStyleSheet("background: rgba(53, 132, 228, 0.15); border-radius: 6px; border: 1px solid rgba(53, 132, 228, 0.3);")
        dl_status_lay = QHBoxLayout(self.dl_status_widget)
        dl_status_lay.setContentsMargins(8, 4, 8, 4)
        dl_status_lay.setSpacing(8)
        
        self.dl_lbl = QLabel("Downloading...")
        self.dl_lbl.setStyleSheet("color: #3584e4; font-size: 11px; font-weight: bold; background: transparent;")
        dl_status_lay.addWidget(self.dl_lbl)
        
        self.dl_progress = QProgressBar()
        self.dl_progress.setFixedSize(80, 8)
        self.dl_progress.setTextVisible(False)
        self.dl_progress.setStyleSheet("""
            QProgressBar { background: rgba(255,255,255,0.1); border: none; border-radius: 4px; }
            QProgressBar::chunk { background: #3584e4; border-radius: 4px; }
        """)
        self.dl_progress.setRange(0, 100)
        self.dl_progress.setValue(0)
        dl_status_lay.addWidget(self.dl_progress)
        
        tlay.addWidget(self.dl_status_widget)
        self.dl_status_widget.hide()
        
        self.search_in = QLineEdit()
        self.search_in.setPlaceholderText("Search mods...")
        self.search_in.setStyleSheet("QLineEdit { background: rgba(255,255,255,0.08); color: #fff; border: none; border-radius: 6px; padding: 0 10px; font-size: 12px; } QLineEdit:focus { background: rgba(255,255,255,0.12); }")
        self.search_in.returnPressed.connect(self._refresh)
        tlay.addWidget(self.search_in, 1)
        
        self.sort_box = QComboBox()
        self.sort_opts = {"Newest": "Generic_Newest", "Most Downloaded": "Generic_MostDownloaded", "Most Liked": "Generic_MostLiked", "Most Viewed": "Generic_MostViewed"}
        self.sort_box.addItems(list(self.sort_opts.keys()))
        self.sort_box.setStyleSheet("QComboBox { background: rgba(255,255,255,0.08); color: #fff; border: none; border-radius: 6px; padding: 4px 10px; font-size: 12px; } QComboBox::drop-down { border: none; } QComboBox QAbstractItemView { background: #222; color: #fff; }")
        self.sort_box.currentIndexChanged.connect(self._refresh)
        tlay.addWidget(self.sort_box)
        
        # Toolbar Buttons (Grid View, List View, Reload GameBanana)
        icon_dir = os.path.join(os.path.dirname(__file__), "..", "ui_sources", "resources", "icons")
        grid_svg = os.path.join(icon_dir, "Grid View.svg")
        list_svg = os.path.join(icon_dir, "List View.svg")
        reload_png = os.path.join(icon_dir, "UpdateModsTable.png")
        
        self.btn_grid_view = QPushButton()
        self.btn_grid_view.setIcon(QIcon(grid_svg))
        self.btn_grid_view.setFixedSize(32, 32)
        self.btn_grid_view.setCursor(Qt.PointingHandCursor)
        self.btn_grid_view.setToolTip("Grid View")
        self.btn_grid_view.clicked.connect(lambda: self._set_view_mode("grid"))
        
        self.btn_list_view = QPushButton()
        self.btn_list_view.setIcon(QIcon(list_svg))
        self.btn_list_view.setFixedSize(32, 32)
        self.btn_list_view.setCursor(Qt.PointingHandCursor)
        self.btn_list_view.setToolTip("List View")
        self.btn_list_view.clicked.connect(lambda: self._set_view_mode("list"))
        
        self.btn_reload = QPushButton()
        self.btn_reload.setIcon(QIcon(reload_png))
        self.btn_reload.setIconSize(QSize(18, 18))
        self.btn_reload.setFixedSize(32, 32)
        self.btn_reload.setCursor(Qt.PointingHandCursor)
        self.btn_reload.setToolTip("Reload GameBanana")
        self.btn_reload.setStyleSheet("QPushButton { background: rgba(255,255,255,0.08); border: none; border-radius: 6px; } QPushButton:hover { background: rgba(255,255,255,0.14); }")
        self.btn_reload.clicked.connect(self._refresh)
        
        tlay.addWidget(self.btn_grid_view)
        tlay.addWidget(self.btn_list_view)
        tlay.addWidget(self.btn_reload)
        self._update_view_toggle_styles()
        
        blayout.addWidget(toolbar)

        # Warning Notice Banner (Paid Skin Requirement) with Infinite Marquee & No Bottom Border
        notice_banner = NoticeMarqueeBanner(
            "Remember that any existing skin mod requires a PAID skin, check the REQUIREMENTS section in GameBanana to find out which skin it replaces, we dont allow Default Skin Mods"
        )
        blayout.addWidget(notice_banner)
        
        self.mscroll = QScrollArea()
        self.mscroll.setWidgetResizable(True)
        self.mscroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.mscroll.setStyleSheet(SCROLLBAR)
        
        self.mcontent = QWidget()
        self.mcontent.setStyleSheet("background: transparent;")
        mlay = QVBoxLayout(self.mcontent)
        mlay.setContentsMargins(0, 0, 0, 0)
        mlay.setSpacing(10)
        
        self.carousel = TopCarouselWidget(self.api, self.img_cache, self)
        self.carousel.clicked.connect(self._on_card_click)
        self.carousel.hide()
        mlay.addWidget(self.carousel)
        
        self.grid_container = QWidget()
        self.grid_container.setStyleSheet("background: transparent;")
        self.grid = QGridLayout(self.grid_container)
        self.grid.setContentsMargins(10, 10, 10, 20)
        self.grid.setSpacing(8)
        self.grid.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        mlay.addWidget(self.grid_container)
        
        self.loading_indicator = QLabel("Loading...")
        self.loading_indicator.setStyleSheet("color: #888; font-size: 13px; background: transparent;")
        self.loading_indicator.setAlignment(Qt.AlignCenter)
        self.loading_indicator.hide()
        mlay.addWidget(self.loading_indicator)
        
        self.mscroll.setWidget(self.mcontent)
        self.mscroll.verticalScrollBar().valueChanged.connect(self._on_scroll)
        
        blayout.addWidget(self.mscroll)
        self.stack.addWidget(self.browser_page)
        
        # Modal Overlay for Mod Details / Hover Preview
        self.detail_overlay = ModDetailOverlay(self.img_cache, self)
        self.detail_overlay.panel.download_clicked.connect(self._start_download)
        self.detail_overlay.panel.category_clicked.connect(self.select_category_by_id)
        
        self.cards = []
        self.current_cat = None
        self.page = 1
        self.loading = False
        self.nomore = False
        
        self.api.mods_loaded.connect(self._on_mods_loaded)
        self.api.mod_detail_loaded.connect(self._on_detail_loaded)
        self.api.quick_file_ready.connect(self._on_quick_file_ready)
        
        self._refresh()

    def open_detail_modal(self, mid, is_preview=False):
        self.detail_overlay.panel.title.setText("Loading...")
        self.detail_overlay.panel.banner.clear()
        self.detail_overlay.show_mod(mid, is_preview=is_preview)
        self.api.fetch_mod_detail(mid)

    def select_category_by_id(self, cat_id):
        if not cat_id: return
        self.detail_overlay.close_overlay()
        self.sidebar.active_cat_id = cat_id
        self._on_category_select(cat_id)

    def showEvent(self, e):
        self._update_badges()
        super().showEvent(e)

    def _set_view_mode(self, mode):
        if self.view_mode == mode: return
        self.view_mode = mode
        self._update_view_toggle_styles()
        self._rebuild_cards()

    def _update_view_toggle_styles(self):
        active_style = "QPushButton { background: rgba(53, 132, 228, 0.3); border: 1px solid #3584e4; border-radius: 6px; }"
        inactive_style = "QPushButton { background: rgba(255,255,255,0.08); border: none; border-radius: 6px; } QPushButton:hover { background: rgba(255,255,255,0.14); }"
        self.btn_grid_view.setStyleSheet(active_style if self.view_mode == "grid" else inactive_style)
        self.btn_list_view.setStyleSheet(active_style if self.view_mode == "list" else inactive_style)

    def track_installed_mod_file(self, bmod_filename, mid, fid=""):
        self.mark_mod_downloaded(mid)

    def mark_mod_downloaded(self, mid):
        try:
            mid = int(mid)
            self.session_downloaded_mids.add(mid)
            self.incompatible_mids.discard(mid)
            self.error_mids.discard(mid)
            self._update_badges()
            print(f"[GameBanana] Marked mod ID {mid} as downloaded for session.")
        except Exception as e:
            print(f"[GameBanana ERROR] Could not mark mod {mid} as downloaded: {e}")

    def mark_mod_incompatible(self, mid):
        try:
            mid = int(mid)
            self.session_downloaded_mids.discard(mid)
            self.incompatible_mids.add(mid)
            self.error_mids.discard(mid)
            for c in self.cards:
                if c.mid == mid and shiboken6.isValid(c):
                    c.set_state("incompatible")
            print(f"[GameBanana] Marked mod ID {mid} as INCOMPATIBLE.")
        except Exception as e:
            print(f"[GameBanana ERROR] Could not mark mod {mid} as incompatible: {e}")

    def mark_mod_error(self, mid):
        try:
            mid = int(mid)
            self.session_downloaded_mids.discard(mid)
            self.error_mids.add(mid)
            for c in self.cards:
                if c.mid == mid and shiboken6.isValid(c):
                    c.set_state("error")
            print(f"[GameBanana] Marked mod ID {mid} as ERROR.")
        except Exception as e:
            print(f"[GameBanana ERROR] Could not mark mod {mid} as error: {e}")

    def update_installed_mods(self, names):
        self.installed_mods = [re.sub(r'[^\w\s]', '', n).lower().strip() for n in names if n]
        self.session_downloaded_mids.clear()
        self._update_badges()

    def set_download_progress(self, progress, mid=None):
        if progress < 100:
            self.dl_status_widget.show()
            self.dl_progress.setValue(progress)
            self.dl_lbl.setText(f"Downloading... {progress}%" if progress > 0 else "Downloading...")
            if mid:
                for c in self.cards:
                    if c.mid == int(mid) and shiboken6.isValid(c):
                        c.set_state("downloading", f"{progress}%")
        else:
            self.dl_progress.setValue(100)
            self.dl_lbl.setText("Downloaded")
            QTimer.singleShot(2000, self.dl_status_widget.hide)

    def is_downloaded(self, name, mid):
        if int(mid) in self.session_downloaded_mids:
            return True
        if not name: return False
        clean = re.sub(r'[^\w\s]', '', name).lower().strip()
        for i_name in self.installed_mods:
            if clean and (clean in i_name or i_name in clean):
                return True
        return False
        
    def _update_badges(self):
        for c in self.cards:
            if not shiboken6.isValid(c): continue
            if c.mid in self.incompatible_mids:
                c.set_state("incompatible")
            elif c.mid in self.error_mids:
                c.set_state("error")
            else:
                dled = self.is_downloaded(c.data.get("_sName"), c.mid)
                c.set_downloaded_state(dled)
            c.update_nsfw_display()
        if hasattr(self, 'carousel'):
            self.carousel.update_nsfw_display()

    def _on_category_select(self, cat_id):
        self.current_cat = cat_id
        if self.current_cat is None and not self.search_in.text().strip():
            self.carousel.show()
        else:
            self.carousel.hide()
        self._refresh()
        
    def _refresh(self):
        self.page = 1
        self.nomore = False
        self.loading = False
        self.loading_indicator.hide()
        self.raw_recs.clear()
        
        for c in list(self.cards): 
            c.deleteLater()
        self.cards.clear()
        
        if self.current_cat is None and not self.search_in.text().strip():
            self.carousel.show()
            self.api.fetch_featured()
            
        self._load_more()
        
    def _load_more(self):
        if self.loading or self.nomore: return
        self.loading = True
        self.loading_indicator.show()
        
        query = self.search_in.text().strip()
        sort = self.sort_opts.get(self.sort_box.currentText(), "Generic_Newest")
        self.api.fetch_mods(page=self.page, cat_id=self.current_cat, query=query, sort=sort)

    def _on_mods_loaded(self, recs, page):
        self.loading = False
        self.loading_indicator.hide()
        
        if not recs:
            self.nomore = True
            return
            
        self.page += 1
        self.raw_recs.extend(recs)
        
        mids_to_fetch = []
        for m in recs:
            mid = m.get("_idRow") or m.get("id")
            if mid:
                dled = self.is_downloaded(m.get("_sName"), mid)
                if self.view_mode == "list":
                    c = ModListItemWidget(m, self.img_cache, is_downloaded=dled, parent=self.grid_container)
                else:
                    c = ModCardWidget(m, self.img_cache, is_downloaded=dled, parent=self.grid_container)
                
                c.clicked.connect(self._on_card_click)
                c.quick_download.connect(self._on_quick_download)
                c.category_clicked.connect(self.select_category_by_id)
                self.cards.append(c)
                mids_to_fetch.append(mid)

        self._rebuild_grid()
        if mids_to_fetch:
            self.api.fetch_mod_stats(mids_to_fetch, self._on_mod_stat_loaded)

    def _rebuild_cards(self):
        for c in list(self.cards):
            c.deleteLater()
        self.cards.clear()
        
        for m in self.raw_recs:
            mid = m.get("_idRow") or m.get("id")
            if mid:
                dled = self.is_downloaded(m.get("_sName"), mid)
                if self.view_mode == "list":
                    c = ModListItemWidget(m, self.img_cache, is_downloaded=dled, parent=self.grid_container)
                else:
                    c = ModCardWidget(m, self.img_cache, is_downloaded=dled, parent=self.grid_container)
                
                c.clicked.connect(self._on_card_click)
                c.quick_download.connect(self._on_quick_download)
                c.category_clicked.connect(self.select_category_by_id)
                self.cards.append(c)
                
        self._rebuild_grid()

    def _on_mod_stat_loaded(self, stat_data):
        if not shiboken6.isValid(self): return
        mid = stat_data.get("_idRow")
        if not mid: return
        
        # Cache loaded stats in self.raw_recs so re-building cards never loses downloaded stats!
        for m in self.raw_recs:
            if (m.get("_idRow") or m.get("id")) == mid:
                if stat_data.get("_nDownloadCount") is not None: m["_nDownloadCount"] = stat_data["_nDownloadCount"]
                if stat_data.get("_nLikeCount") is not None: m["_nLikeCount"] = stat_data["_nLikeCount"]
                if stat_data.get("_nViewCount") is not None: m["_nViewCount"] = stat_data["_nViewCount"]
                break

        for c in self.cards:
            if c.mid == mid and shiboken6.isValid(c):
                c.update_stats(stat_data)
                break
        
    def _rebuild_grid(self):
        if not shiboken6.isValid(self): return
        while self.grid.takeAt(0): pass
            
        w = self.mscroll.viewport().width() - 20
        if self.view_mode == "list":
            cols = max(1, w // 340) # Ultra-compact 2-column list view without right clipping!
            for i, c in enumerate(self.cards):
                self.grid.addWidget(c, i // cols, i % cols)
        else:
            cols = max(1, w // 192) 
            for i, c in enumerate(self.cards):
                self.grid.addWidget(c, i // cols, i % cols)
            
    def _on_scroll(self, val):
        sb = self.mscroll.verticalScrollBar()
        if sb.maximum() > 0 and val >= sb.maximum() * 0.60:
            self._load_more()

    def resizeEvent(self, e):
        self._rebuild_grid()
        if hasattr(self, 'detail_overlay') and self.detail_overlay.isVisible():
            self.detail_overlay.setGeometry(0, 0, self.width(), self.height())
        super().resizeEvent(e)
        
    def _on_card_click(self, mid):
        self.open_detail_modal(mid, is_preview=False)
        
    def _on_detail_loaded(self, data):
        if not data or not isinstance(data, dict): return
        inst = self.is_downloaded(data.get("_sName"), data.get("_idRow"))
        self.detail_overlay.panel.load_data(data, inst)

    def _on_quick_download(self, mid):
        self.dl_status_widget.show()
        self.dl_lbl.setText("Fetching file...")
        self.dl_progress.setValue(10)
        self.api.fetch_quick_download(mid)
        
    def _on_quick_file_ready(self, url, fname):
        mid = int(url.split(",")[1])
        # Update card button to yellow DOWNLOADING state (do NOT mark as downloaded yet!)
        for c in self.cards:
            if c.mid == mid and shiboken6.isValid(c):
                c.set_state("downloading", "0%")
        self._start_download(url, fname)

    def _start_download(self, url, fname):
        self.dl_status_widget.show()
        self.dl_lbl.setText(f"Downloading...")
        self.dl_progress.setValue(20)
        self.downloadMod.emit(url, fname)
