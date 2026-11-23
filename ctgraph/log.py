"""Journal d'activité (ouvertures, enregistrements, résolutions) pour le diagnostic."""
from __future__ import annotations

import logging
import os
import tempfile
from logging.handlers import RotatingFileHandler

LOG_NAME = "ctgraph"


def log_path() -> str:
    base = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
    return os.path.join(base, "CTgraph", "ctgraph.log")


def setup() -> str:
    """Active le journal dans un fichier (500 Ko, un fichier de secours). Renvoie son chemin."""
    logger = logging.getLogger(LOG_NAME)
    if any(isinstance(h, RotatingFileHandler) for h in logger.handlers):
        return log_path()
    logger.setLevel(logging.INFO)
    path = log_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        handler = RotatingFileHandler(path, maxBytes=500_000, backupCount=1, encoding="utf-8")
    except OSError:
        handler = logging.NullHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S"))
    logger.addHandler(handler)
    logger.propagate = False
    return path


def get() -> logging.Logger:
    logger = logging.getLogger(LOG_NAME)
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())  # silencieux tant que setup() n'a pas été appelé
    return logger
