#!/usr/bin/env python3
"""Source-tree entry point for the packaged skill context checker."""
from pathlib import Path
import runpy

if __name__ == '__main__':
    script = Path(__file__).resolve().parents[1] / 'common/base/skills/skill-authoring/scripts/context_check.py'
    runpy.run_path(str(script), run_name='__main__')
