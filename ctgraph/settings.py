"""Préférences persistantes (registre Windows via QSettings) : fenêtre, fichiers récents, affichage."""
from __future__ import annotations

import os
from typing import List

from PySide6.QtCore import QSettings

MAX_RECENT = 12


class Settings:
    def __init__(self):
        # CTGRAPH_SETTINGS=<fichier.ini> isole les préférences (tests, version portable).
        override = os.environ.get("CTGRAPH_SETTINGS")
        if override:
            self.s = QSettings(override, QSettings.Format.IniFormat)
        else:
            self.s = QSettings("CTgraph", "CTgraph")

    def get(self, key: str, default=None):
        return self.s.value(key, default)

    def set(self, key: str, value) -> None:
        self.s.setValue(key, value)

    def get_bool(self, key: str, default: bool) -> bool:
        v = self.s.value(key, default)
        if isinstance(v, str):
            return v.lower() in ("1", "true", "yes", "oui")
        return bool(v)

    def get_int(self, key: str, default: int) -> int:
        try:
            return int(self.s.value(key, default))
        except (TypeError, ValueError):
            return default

    def sync(self) -> None:
        self.s.sync()

    # -- fichiers récents -----------------------------------------------------

    def recent_files(self) -> List[str]:
        v = self.s.value("recentFiles", [])
        if isinstance(v, str):
            v = [v]
        return [str(p) for p in (v or []) if p]

    def add_recent(self, path: str) -> None:
        files = [p for p in self.recent_files() if p.lower() != path.lower()]
        files.insert(0, path)
        self.s.setValue("recentFiles", files[:MAX_RECENT])

    def remove_recent(self, path: str) -> None:
        self.s.setValue("recentFiles", [p for p in self.recent_files() if p.lower() != path.lower()])
