"""Per-user data directory for Windows and Linux (no Qt, safe to import from lan.py)."""
import os, sys
from pathlib import Path


def data_dir():
    """BFT_DATA_DIR wins. Windows: %LOCALAPPDATA%\\BFT-DopeWars. Linux/macOS: $XDG_DATA_HOME/BFT-DopeWars."""
    override = os.environ.get('BFT_DATA_DIR')
    if override:
        return Path(override)
    if sys.platform == 'win32':
        base = Path(os.environ.get('LOCALAPPDATA', str(Path.home())))
    else:
        base = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local' / 'share')
    return base / 'BFT-DopeWars'
