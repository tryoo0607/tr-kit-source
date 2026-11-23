#!/usr/bin/env python3
"""Read-only selected official installation review."""
from pathlib import Path
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'common/base/scripts'))
from provider_review import main

if __name__ == '__main__':
    raise SystemExit(main())
