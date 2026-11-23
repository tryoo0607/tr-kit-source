#!/usr/bin/env python3
"""Source/bundle entry point for the shared declared-read checker."""
import sys
from pathlib import Path
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'common/base/scripts'))
from context_check import main
if __name__=='__main__':raise SystemExit(main())
