import os
import json

class LoaderConfig:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LoaderConfig, cls).__new__(cls)
            cls._instance._load()
        return cls._instance

    def _load(self):
        self.config_path = os.path.join(os.getenv("APPDATA"), "BModloader", "config_loader.json")
        self.defaults = {
            "brawlhallaPath": "",
            "modsPath": "",
            "favorites": [],
            "showListPreviews": True
        }
        
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    self.data = json.load(f)
            except:
                self.data = self.defaults.copy()
        else:
            self.data = self.defaults.copy()
            self._save()

    def _save(self):
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        temp_path = self.config_path + ".tmp"
        try:
            with open(temp_path, "w") as f:
                json.dump(self.data, f, indent=4)
            # Atomic swap
            if os.path.exists(self.config_path):
                os.remove(self.config_path)
            os.rename(temp_path, self.config_path)
        except Exception as e:
            print(f"Error saving config: {e}")
            if os.path.exists(temp_path):
                try: os.remove(temp_path)
                except: pass

    @property
    def brawlhallaPath(self):
        return self.data.get("brawlhallaPath", self.defaults["brawlhallaPath"])

    @brawlhallaPath.setter
    def brawlhallaPath(self, value):
        self.data["brawlhallaPath"] = value
        self._save()

    @property
    def modsPath(self):
        return self.data.get("modsPath", self.defaults["modsPath"])

    @modsPath.setter
    def modsPath(self, value):
        self.data["modsPath"] = value
        self._save()

    @property
    def favorites(self):
        return self.data.get("favorites", self.defaults["favorites"])

    @favorites.setter
    def favorites(self, value):
        self.data["favorites"] = value
        self._save()

    @property
    def showListPreviews(self):
        return self.data.get("showListPreviews", self.defaults["showListPreviews"])

    @showListPreviews.setter
    def showListPreviews(self, value):
        self.data["showListPreviews"] = value
        self._save()

    @property
    def nsfwFilter(self):
        return self.data.get("nsfwFilter", True)

    @nsfwFilter.setter
    def nsfwFilter(self, value):
        self.data["nsfwFilter"] = value
        self._save()
