#!/usr/bin/env python3
"""Prepare official pinned Gitleaks only, never enroll a repository."""
import sys
from pathlib import Path
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'common/base/scripts'))
from toolchain import setup_cli
if __name__=='__main__':raise SystemExit(setup_cli('gitleaks'))
