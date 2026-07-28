from typing import List

from ..utils.textformater import TextFormatter


class ModClass:
    def __init__(self,
                 gameVersion: str,
                 name: str,
                 author: str,
                 version: str,
                 description: str,
                 tags: List[str],
                 previewsPaths: List[str],
                 hash: str,
                 platform: str,
                 installed: bool,
                 currentVersion: bool,
                 modFileExist: bool,
                 date: float = 0.0,
                 favorite: bool = False,
                 swfNames: List[str] = None,
                 fileNames: List[str] = None,
                 spriteNames: List[str] = None,
                 modPath: str = ""
                 ):
        self.gameVersion = gameVersion or ""
        self.name = name or ""
        self.author = author or ""
        self.version = version or ""
        self.description = TextFormatter.format(description or "")
        self.tags = tags or []
        self.previewsPaths = previewsPaths or []
        self.hash = hash or ""
        self.platform = platform if platform is not None else ""
        self.installed = installed
        self.currentVersion = currentVersion
        self.modFileExist = modFileExist
        self.date = date
        self.favorite = favorite
        self.swfNames = swfNames or []
        self.fileNames = fileNames or []
        self.spriteNames = spriteNames or []
        self.modPath = modPath or ""

