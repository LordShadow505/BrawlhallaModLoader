import json, re, datetime, webbrowser, os
import shiboken6
from urllib.parse import urlencode
from PySide6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QScrollArea, QWidget, QGridLayout, QComboBox, QStackedWidget, QSizePolicy, QToolTip)
from PySide6.QtCore import Qt, Signal, QObject, QUrl, QSize
from PySide6.QtGui import QPixmap, QIcon, QFont, QDesktopServices
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

SCROLLBAR = """
    QScrollArea { border: none; background: transparent; }
    QScrollBar:vertical { border: none; background: #2B2C32; width: 7px; margin: 0; }
    QScrollBar::handle:vertical { background: #616161; min-height: 30px; border-radius: 3px; }
    QScrollBar::handle:vertical:hover { background: #A1A1A1; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { border: none; background: none; height: 0; }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
"""

class Net(QObject):
    BASE = "https://gamebanana.com/apiv11"
    GAME = 5704
    UA   = b"BModLoader/1.0"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._m = QNetworkAccessManager(self)

    def _get(self, url, cb):
        # Removed print to clean up logs
        req = QNetworkRequest(QUrl(url))
        req.setRawHeader(b"User-Agent", self.UA)
        r = self._m.get(req)
        r.finished.connect(lambda: cb(r))

    def json(self, url, params, cb):
        full = f"{url}?{urlencode(params)}" if params else url
        def done(r):
            err = r.error()
            if err != QNetworkReply.NetworkError.NoError:
                print(f"[GB NET] ERR: {err} for {r.url().toString()}")
                cb(None); r.deleteLater(); return
            raw_bytes = bytes(r.readAll())
            try:
                data = json.loads(raw_bytes.decode())
            except Exception as e:
                print(f"[GB NET] JSON ERR: {e}")
                data = None
            finally: r.deleteLater()
            cb(data)
        self._get(full, done)

    def pix(self, url, cb):
        if not url: return
        def done(r):
            try:
                p = QPixmap()
                if p.loadFromData(bytes(r.readAll())) and not p.isNull(): cb(p)
            finally: r.deleteLater()
        self._get(url, done)

    def cats(self, pid, cb):
        p = {"_idGameRow": self.GAME, "_sSort": "a_to_z", "_bShowEmpty": "true"}
        if pid is not None: p["_idParentRow"] = pid
        self.json(f"{self.BASE}/Mod/Categories", p, cb)

    def mods(self, page, sid, q, sort, cb):
        if q and len(q) >= 2:
            p = {"_sModelName": "Mod", "_idGameRow": self.GAME, "_nPage": page, "_nPerpage": 30, "_sSearchString": q}
            self.json(f"{self.BASE}/Util/Search/Results", p, cb)
        else:
            p = {"_nPage": page, "_nPerpage": 30, "_sSort": sort, "_aFilters[Generic_Game]": self.GAME}
            if sid is not None: p["_aFilters[Generic_Category]"] = sid
            self.json(f"{self.BASE}/Mod/Index", p, cb)

    def detail(self, mid, cb):
        props = "_sName,_aSubmitter,_aPreviewMedia,_nViewCount,_nLikeCount,_nDownloadCount,_tsDateAdded,_tsDateUpdated,_sText,_aFiles"
        self.json(f"{self.BASE}/Mod/{mid}", {"_csvProperties": props}, cb)


def _ico(name, size=14): return QIcon(f":/icons/resources/icons/{name}").pixmap(size, size)


class CatBtn(QPushButton):
    def __init__(self, sec, net, on_leaf, on_branch):
        super().__init__()
        self.setCheckable(True); self.setFixedHeight(46); self.setCursor(Qt.PointingHandCursor)
        row = QHBoxLayout(self); row.setContentsMargins(14, 0, 14, 0); row.setSpacing(10)
        self._ico = QLabel(); self._ico.setFixedSize(24, 24); self._ico.setScaledContents(True)
        self._ico.setStyleSheet("background: transparent;"); row.addWidget(self._ico)
        name = sec.get("_sName") or "All Submissions"
        lbl = QLabel(name); lbl.setStyleSheet("color: #ffffff; font-size: 10pt; font-weight: 600; background: transparent;")
        row.addWidget(lbl, 1)
        if int(sec.get("_nCategoryCount") or 0) > 0:
            arr = QLabel(">"); arr.setStyleSheet("color: #666; font-size: 12pt; background: transparent;"); row.addWidget(arr)
            self.clicked.connect(lambda: on_branch(sec))
        else:
            self.clicked.connect(lambda: on_leaf(sec.get("_idRow"), self))
        self.setStyleSheet("""
            CatBtn { background: transparent; border: none; border-radius: 6px; margin: 1px 8px; }
            CatBtn:hover  { background: #2A2B2D; }
            CatBtn:checked { background: #F9A825; }
            CatBtn:checked QLabel { color: #000000; }
        """)
        u = sec.get("_sIconUrl")
        if u: net.pix(u, self._set_pix)

    def _set_pix(self, pix):
        if shiboken6.isValid(self) and shiboken6.isValid(self._ico):
            self._ico.setPixmap(pix)


class ModCard(QFrame):
    clicked = Signal(int)
    downloadClicked = Signal(str, str)
    def __init__(self, mid, net, frame=None):
        super().__init__(); self.mid = mid; self._net = net; self._data = None; self.is_installed = False; self._frame = frame
        self.setCursor(Qt.PointingHandCursor); self.setFixedSize(195, 330)
        self.setStyleSheet("""
            ModCard { background: #1D1E20; border: 1px solid #333; border-radius: 10px; }
            ModCard:hover { background: #151518; border: 1px solid #F9A825; }
            ModCard QLabel { background: transparent; }
        """)
        col = QVBoxLayout(self); col.setContentsMargins(10,10,10,10); col.setSpacing(5)
        
        self._thumb = QLabel(); self._thumb.setFixedSize(175,98); self._thumb.setAlignment(Qt.AlignCenter)
        self._thumb.setStyleSheet("background:#000;border-radius:5px;"); col.addWidget(self._thumb,0,Qt.AlignCenter)
        
        self._name = QLabel("Loading..."); self._name.setWordWrap(True); self._name.setFont(QFont("Roboto",9,QFont.Bold)); self._name.setStyleSheet("color:#fff;"); self._name.setFixedHeight(32); col.addWidget(self._name)
        self._auth = QLabel(""); self._auth.setStyleSheet("color:#888;font-size:8pt;"); col.addWidget(self._auth)
        
        sg = QGridLayout(); sg.setContentsMargins(0,2,0,2); sg.setSpacing(4)
        self._vDate = self._stat(sg,0,0,"GB_DateAdded.png")
        self._vUpd  = self._stat(sg,0,2,"GB_Updated.png")
        self._vDl   = self._stat(sg,1,0,"GB_Downloads.png")
        self._vLike = self._stat(sg,1,2,"GB_Likes.png")
        self._vView = self._stat(sg,2,0,"GB_Views.png")
        col.addLayout(sg)
        
        self._req = QLabel("Requirements: —"); self._req.setStyleSheet("color:#FF8F00;font-size:7pt;font-weight:bold;"); self._req.setWordWrap(True); col.addWidget(self._req)
        col.addStretch()
        
        btnL = QHBoxLayout(); btnL.setSpacing(5)
        self._webBtn = QPushButton(); self._webBtn.setFixedSize(30, 30); self._webBtn.setToolTip("Open in browser")
        self._webBtn.setIcon(QIcon(":/icons/resources/icons/Website.png")); self._webBtn.setIconSize(QSize(18,18))
        self._webBtn.setStyleSheet("QPushButton{background:#2196F3;border-radius:6px;}QPushButton:hover{background:#1E88E5;}")
        self._webBtn.clicked.connect(self._open_web)
        
        self._btn = QPushButton(" DOWNLOAD"); self._btn.setEnabled(False); self._btn.setFixedHeight(30)
        self._btn.setIcon(QIcon(":/icons/resources/icons/DownloadMod.png")); self._btn.setIconSize(QSize(16,16))
        self._btn.clicked.connect(self._download)
        self._update_btn_style()
        
        btnL.addWidget(self._webBtn); btnL.addWidget(self._btn, 1)
        col.addLayout(btnL)
        
        net.detail(mid, self._on_data)

    def _update_btn_style(self):
        if self.is_installed:
            self._btn.setText(" REDOWNLOAD")
            self._btn.setStyleSheet("QPushButton{background:#9C27B0;color:#fff;border:none;border-radius:6px;padding:5px;font-weight:bold;font-size:8pt;}QPushButton:hover{background:#7B1FA2;}QPushButton:disabled{background:#151515;color:#444;}")
        else:
            self._btn.setText(" DOWNLOAD")
            self._btn.setStyleSheet("QPushButton{background:#43C15F;color:#fff;border:none;border-radius:6px;padding:5px;font-weight:bold;font-size:8pt;}QPushButton:hover{background:#38A14F;}QPushButton:disabled{background:#151515;color:#444;}")

    def _stat(self, g, r, c, ico):
        img = QLabel(); img.setFixedSize(12,12); img.setPixmap(_ico(ico)); img.setScaledContents(True); g.addWidget(img,r,c)
        v = QLabel("—"); v.setStyleSheet("color:#aaa;font-size:7pt;"); g.addWidget(v,r,c+1); return v

    def _on_data(self, d):
        if not shiboken6.isValid(self): return
        try:
            if not d or "_sName" not in d: return
            self._data = d; self._data["_idRow"] = self.mid
            self._name.setText(d["_sName"]); self._auth.setText(f"by {d.get('_aSubmitter',{}).get('_sName','?')}")
            def fmt(n):
                try: n=int(n or 0); return f"{n/1000:.1f}k" if n>=1000 else str(n)
                except: return "0"
            self._vDl.setText(fmt(d.get("_nDownloadCount"))); self._vLike.setText(fmt(d.get("_nLikeCount"))); self._vView.setText(fmt(d.get("_nViewCount")))
            try:
                if d.get("_tsDateAdded"): self._vDate.setText(datetime.datetime.fromtimestamp(int(d["_tsDateAdded"])).strftime("%d/%m/%y"))
                if d.get("_tsDateUpdated"): self._vUpd.setText(datetime.datetime.fromtimestamp(int(d["_tsDateUpdated"])).strftime("%d/%m/%y"))
            except: pass
            
            # Check if name is in installed list
            if self._frame and hasattr(self._frame, "is_mod_installed"):
                if self._frame.is_mod_installed(d["_sName"]):
                    self.is_installed = True; self._update_btn_style()

            req_list = []
            try:
                files = d.get("_aFiles") or {}
                if isinstance(files, dict): files = list(files.values())
                if files and isinstance(files[0], dict) and files[0].get("_sDescription"):
                    req_list.append(files[0].get("_sDescription"))
            except: pass
            
            if req_list:
                txt = ", ".join([str(x) for x in req_list if x])
                self._req.setText(f"Requirements: {txt[:80]}...")
            else:
                self._req.setText("Requirements: Not found, please check the GameBanana page")
                
            self._btn.setEnabled(True)
            imgs = (d.get("_aPreviewMedia") or {}).get("_aImages",[])
            if imgs and isinstance(imgs, list):
                base=imgs[0].get("_sBaseUrl",""); fn=imgs[0].get("_sFile220","") or imgs[0].get("_sFile","")
                if base and fn: self._net.pix(f"{base}/{fn}", self._set_thumb)
        except Exception as e:
            print(f"[GB DEBUG] Error in ModCard data: {e}")

    def _set_thumb(self, pix):
        if shiboken6.isValid(self) and shiboken6.isValid(self._thumb):
            scaled = pix.scaled(self._thumb.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self._thumb.setPixmap(scaled)

    def _open_web(self):
        webbrowser.open(f"https://gamebanana.com/mods/{self.mid}")

    def _download(self):
        if not self._data: return
        files = self._data.get("_aFiles") or {}
        if isinstance(files, dict): files = list(files.values())
        if not files: return
        fid = files[0].get("_idRow"); fn = files[0].get("_sFile","mod.zip")
        self.downloadClicked.emit(f"bmod://Mod,{self.mid},{fid}", fn)

    def mousePressEvent(self, e):
        if self._data: self.clicked.emit(self.mid)
        super().mousePressEvent(e)


class FileRow(QFrame):
    download = Signal(str, str)
    def __init__(self, mid, f, installed=False):
        super().__init__(); self.is_installed = installed
        self.setStyleSheet("QFrame{background:#2A2B2D;border-radius:6px;padding:5px;}QFrame:hover{background:#333;}")
        l = QHBoxLayout(self); l.setContentsMargins(10,5,10,5)
        name = QLabel(f.get("_sFile", "Unknown file"))
        name.setStyleSheet("color:#fff;font-weight:bold;font-size:9pt;background:transparent;")
        l.addWidget(name, 1)
        
        fs = f.get("_nFilesize")
        if isinstance(fs, int):
            if fs > 1024*1024: size_str = f"{fs/(1024*1024):.1f} MB"
            elif fs > 1024: size_str = f"{fs/1024:.1f} KB"
            else: size_str = f"{fs} B"
        else: size_str = str(fs or "—")
        size = QLabel(size_str)
        size.setStyleSheet("color:#888;font-size:8pt;background:transparent;")
        l.addWidget(size)
        
        self._btn = QPushButton("REDOWNLOAD" if installed else "Download")
        self._btn.setFixedSize(100, 26)
        self._update_btn_style()
        fid = f.get("_idRow")
        self._btn.clicked.connect(lambda: self.download.emit(f"bmod://Mod,{mid},{fid}", f.get("_sFile","mod.zip")))
        l.addWidget(self._btn)

    def _update_btn_style(self):
        if self.is_installed:
            self._btn.setText("REDOWNLOAD")
            self._btn.setStyleSheet("QPushButton{background:#9C27B0;color:#fff;border-radius:4px;font-size:8pt;font-weight:bold;}QPushButton:hover{background:#7B1FA2;}")
        else:
            self._btn.setText("Download")
            self._btn.setStyleSheet("QPushButton{background:#43C15F;color:#fff;border-radius:4px;font-size:8pt;font-weight:bold;}QPushButton:hover{background:#52D46E;}")

class DetailView(QWidget):
    back = Signal(); download = Signal(str, str)
    def __init__(self, net):
        super().__init__(); self._net = net
        root = QVBoxLayout(self); root.setContentsMargins(25,20,25,20); root.setSpacing(10)
        top = QHBoxLayout(); b = QPushButton("Back to Browser")
        b.setStyleSheet("QPushButton{background:#2A2B2D;color:#fff;border:1px solid #444;border-radius:8px;padding:8px 18px;font-weight:bold;}QPushButton:hover{background:#3A3B3D;}")
        b.clicked.connect(self.back); top.addWidget(b); top.addStretch(); root.addLayout(top)
        sc = QScrollArea(); sc.setWidgetResizable(True); sc.setStyleSheet(SCROLLBAR)
        cw = QWidget(); self._cl = QVBoxLayout(cw); self._cl.setContentsMargins(0,10,0,10); self._cl.setSpacing(12); sc.setWidget(cw); root.addWidget(sc)
        self._title = QLabel(""); self._title.setFont(QFont("Roboto",18,QFont.Bold)); self._title.setStyleSheet("color:#F9A825;background:transparent;"); self._title.setWordWrap(True); self._cl.addWidget(self._title)
        self._auth = QLabel(""); self._auth.setStyleSheet("color:#888;font-size:10pt;background:transparent;"); self._cl.addWidget(self._auth)
        
        self._prev = QLabel(); self._prev.setFixedSize(480, 270); self._prev.setAlignment(Qt.AlignCenter)
        self._prev.setStyleSheet("background:#000;border-radius:10px;"); self._cl.addWidget(self._prev, 0, Qt.AlignCenter)
        
        self._desc = QLabel(""); self._desc.setWordWrap(True); self._desc.setStyleSheet("color:#ddd;font-size:10pt;background:#1D1E20;padding:16px;border-radius:8px;"); self._cl.addWidget(self._desc)
        
        self._fileHeader = QLabel("Available Files:"); self._fileHeader.setStyleSheet("color:#F9A825;font-weight:bold;margin-top:10px;background:transparent;")
        self._cl.addWidget(self._fileHeader)
        self._fileContainer = QVBoxLayout(); self._fileContainer.setSpacing(5)
        self._cl.addLayout(self._fileContainer)
        
        self._cl.addStretch()
        self._files = []; self._mid = None

    def show_mod(self, mid, cached=None):
        self._mid = mid; self._files = []
        while self._fileContainer.count():
            w = self._fileContainer.takeAt(0).widget()
            if w: w.deleteLater()
        self._title.setText("Loading..."); self._auth.setText(""); self._desc.setText(""); self._prev.clear()
        if cached: self._apply(cached)
        else: self._net.detail(mid, self._apply)

    def _apply(self, d):
        if not shiboken6.isValid(self): return
        if not d: return
        self._title.setText(d.get("_sName",""))
        self._auth.setText(f"by {d.get('_aSubmitter',{}).get('_sName','?')}")
        raw = re.sub(r"<[^>]+>", "", d.get("_sText","") or "").strip()
        self._desc.setText(raw or "No description.")
        imgs = (d.get("_aPreviewMedia") or {}).get("_aImages",[])
        if imgs:
            base=imgs[0].get("_sBaseUrl",""); fn=imgs[0].get("_sFile","")
            if base and fn: self._net.pix(f"{base}/{fn}", self._set_prev)
        files = d.get("_aFiles") or {}
        if isinstance(files, dict): files = list(files.values())
        self._files = files
        is_inst = False
        if hasattr(self.parent(), "is_mod_installed"):
            is_inst = self.parent().is_mod_installed(d.get("_sName"))

        for f in files:
            row = FileRow(self._mid, f, installed=is_inst)
            row.download.connect(self.download)
            self._fileContainer.addWidget(row)

    def _set_prev(self, pix):
        if shiboken6.isValid(self) and shiboken6.isValid(self._prev):
            scaled = pix.scaled(self._prev.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self._prev.setPixmap(scaled)


class GameBananaFrame(QFrame):
    downloadMod = Signal(str, str)
    SORTS = {"Newest":"Generic_Newest","Oldest":"Generic_Oldest","Most Viewed":"Generic_MostViewed","Most Downloaded":"Generic_MostDownloaded","Most Liked":"Generic_MostLiked"}

    def __init__(self, modsPath=None, parent=None):
        super().__init__(parent)
        self._net = Net(self); self.modsPath = modsPath; self.installed_mod_names = []
        self.setStyleSheet("background:#151518;")
        self._page=1; self._sid=None; self._loading=False; self._nomore=False; self._path=[]; self._cards=[]

        root = QHBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)

        # sidebar
        side = QFrame(); side.setFixedWidth(255); side.setStyleSheet("background:#1D1E20;border-right:1px solid #333;")
        sl = QVBoxLayout(side); sl.setContentsMargins(0,0,0,0); sl.setSpacing(0)
        hdr = QLabel("Browse"); hdr.setFont(QFont("Roboto",13,QFont.Bold)); hdr.setStyleSheet("color:#F9A825;padding:16px 18px 8px 18px;background:transparent;"); sl.addWidget(hdr)
        self._secScroll = QScrollArea(); self._secScroll.setWidgetResizable(True); self._secScroll.setStyleSheet(SCROLLBAR)
        self._secW = QWidget(); self._secL = QVBoxLayout(self._secW); self._secL.setContentsMargins(0,4,0,10); self._secL.setSpacing(1); self._secL.setAlignment(Qt.AlignTop)
        self._secScroll.setWidget(self._secW); sl.addWidget(self._secScroll); root.addWidget(side)

        # stack
        self._stack = QStackedWidget()
        # browser page
        bp = QWidget(); bl = QVBoxLayout(bp); bl.setContentsMargins(0,0,0,0); bl.setSpacing(0)
        tb = QFrame(); tb.setFixedHeight(62); tb.setStyleSheet("background:#1D1E20;border-bottom:1px solid #333;")
        tr = QHBoxLayout(tb); tr.setContentsMargins(16,0,16,0); tr.setSpacing(10)
        self._search = QLineEdit(); self._search.setPlaceholderText("Search mods..."); self._search.setStyleSheet("QLineEdit{background:#2A2B2D;color:#fff;border:1px solid #444;border-radius:18px;padding:8px 18px;font-size:10pt;}")
        self._search.returnPressed.connect(self._refresh); tr.addWidget(self._search)
        self._sortC = QComboBox(); self._sortC.addItems(list(self.SORTS.keys())); self._sortC.setFixedWidth(165)
        self._sortC.setStyleSheet("QComboBox{background:#2A2B2D;color:#fff;border:1px solid #444;border-radius:8px;padding:8px 10px;font-weight:bold;}QComboBox::drop-down{border:none;}QComboBox QAbstractItemView{background:#2A2B2D;color:#fff;selection-background-color:#F9A825;selection-color:#000;}")
        self._sortC.currentIndexChanged.connect(self._refresh); tr.addWidget(self._sortC)
        bl.addWidget(tb)
        self._mScroll = QScrollArea(); self._mScroll.setWidgetResizable(True); self._mScroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff); self._mScroll.setStyleSheet(SCROLLBAR)
        self._mW = QWidget(); self._grid = QGridLayout(self._mW); self._grid.setSpacing(12); self._grid.setContentsMargins(14,14,14,14); self._grid.setAlignment(Qt.AlignTop|Qt.AlignLeft)
        self._mScroll.setWidget(self._mW); self._mScroll.verticalScrollBar().valueChanged.connect(self._on_scroll); bl.addWidget(self._mScroll)
        self._stack.addWidget(bp)
        # detail page
        self._detail = DetailView(self._net); self._detail.back.connect(lambda: self._stack.setCurrentIndex(0)); self._detail.download.connect(self.downloadMod)
        self._stack.addWidget(self._detail)
        root.addWidget(self._stack)

        self._load_cats(); self._refresh()

    def update_installed_mods(self, names):
        self.installed_mod_names = names
        for c in self._cards:
            if hasattr(c, "_data") and c._data:
                if self.is_mod_installed(c._data.get("_sName")):
                    c.is_installed = True; c._update_btn_style()
                elif c.mid in getattr(self, "downloaded_mids", set()):
                    c.is_installed = True; c._update_btn_style()
                else:
                    c.is_installed = False; c._update_btn_style()
                    
        # Update DetailView
        if hasattr(self, "_detail") and self._detail._title.text():
            is_inst = self.is_mod_installed(self._detail._title.text())
            if hasattr(self, "downloaded_mids") and self._detail._mid in self.downloaded_mids:
                is_inst = True
            for i in range(self._detail._fileContainer.count()):
                w = self._detail._fileContainer.itemAt(i).widget()
                if isinstance(w, FileRow):
                    w.is_installed = is_inst
                    w._update_btn_style()

    def mark_mod_downloaded(self, mid):
        if not hasattr(self, "downloaded_mids"): self.downloaded_mids = set()
        self.downloaded_mids.add(mid)
        for c in self._cards:
            if c.mid == mid:
                c.is_installed = True; c._update_btn_style()
                
        if hasattr(self, "_detail") and self._detail._mid == mid:
            for i in range(self._detail._fileContainer.count()):
                w = self._detail._fileContainer.itemAt(i).widget()
                if isinstance(w, FileRow):
                    w.is_installed = True
                    w._update_btn_style()

    def is_mod_installed(self, name):
        if not name: return False
        # Clean name for better matching (GameBanana names can have special chars)
        clean_name = re.sub(r'[^\w\s]', '', name).lower().strip()
        for i_name in self.installed_mod_names:
            if clean_name in re.sub(r'[^\w\s]', '', i_name).lower().strip():
                return True
        return False

    def _load_cats(self, pid=None):
        self._net.cats(pid, self._show_cats)

    def _show_cats(self, data):
        while self._secL.count():
            w = self._secL.takeAt(0).widget()
            if w: w.deleteLater()
        if self._path:
            bb = QPushButton("Back"); bb.setFixedHeight(42); bb.setCursor(Qt.PointingHandCursor)
            bb.setStyleSheet("QPushButton{background:#2A2B2D;color:#F9A825;border:none;border-radius:6px;margin:4px 10px;padding-left:14px;text-align:left;font-weight:bold;}QPushButton:hover{background:#333;}")
            bb.clicked.connect(self._pop); self._secL.addWidget(bb)
        all_btn = CatBtn({"_sName":"All Submissions","_idRow":None,"_nCategoryCount":0}, self._net, self._set_sec, self._push)
        all_btn.setChecked(self._sid is None); self._secL.addWidget(all_btn)
        for s in (data or []):
            b = CatBtn(s, self._net, self._set_sec, self._push); b.setChecked(self._sid == s.get("_idRow")); self._secL.addWidget(b)

    def _push(self, sec): self._path.append(sec); self._set_sec(sec.get("_idRow")); self._load_cats(sec.get("_idRow"))
    def _pop(self): self._path.pop() if self._path else None; pid=self._path[-1].get("_idRow") if self._path else None; self._set_sec(pid); self._load_cats(pid)
    def _set_sec(self, sid, btn=None): self._sid=sid; self._refresh()

    def _refresh(self):
        self._page=1; self._nomore=False; self._loading=False
        for c in self._cards: c.deleteLater()
        self._cards=[]; self._load_more()

    def _load_more(self):
        if self._loading or self._nomore: return
        self._loading=True; sort=self.SORTS.get(self._sortC.currentText(),"Generic_Newest")
        self._net.mods(self._page, self._sid, self._search.text(), sort, self._on_mods)

    def _on_mods(self, data):
        self._loading=False
        if not data: self._nomore=True; return
        recs = data.get("_aRecords", data) if isinstance(data, dict) else data
        if not recs: self._nomore=True; return
        self._page+=1
        for m in recs:
            try:
                mid=m.get("_idRow") or m.get("id")
                if mid:
                    c=ModCard(int(mid), self._net, frame=self)
                    c.clicked.connect(self._on_card_click)
                    c.downloadClicked.connect(self.downloadMod)
                    self._cards.append(c)
            except Exception as e:
                print(f"[GB DEBUG] Error creating card: {e}")
        self._rebuild()

    def _on_card_click(self, mid):
        if mid <= 0: return
        self._detail.show_mod(mid); self._stack.setCurrentIndex(1)

    def _rebuild(self):
        w=self._mScroll.viewport().width() - 60; cols=max(3,min(6,w//205))
        while self._grid.count(): self._grid.takeAt(0)
        for i,c in enumerate(self._cards): self._grid.addWidget(c, i//cols, i % cols)

    def _on_scroll(self, v):
        sb=self._mScroll.verticalScrollBar()
        if sb.maximum()>0 and v>=sb.maximum()*0.88: self._load_more()

    def resizeEvent(self, e): self._rebuild(); super().resizeEvent(e)
