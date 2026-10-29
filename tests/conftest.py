"""The repository consists of scripts with sibling imports, not packages."""
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
for directory in (ROOT, ROOT / 'vdw', ROOT / 'ec'):
    sys.path.insert(0, str(directory))
