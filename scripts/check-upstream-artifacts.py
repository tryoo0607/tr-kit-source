#!/usr/bin/env python3
"""Fresh pre-assembly/pre-transfer gate; no build, transmission or activation."""
import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'common/base/scripts'))
from upstream_artifacts import inspect


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--catalog', required=True, type=Path)
    parser.add_argument('--scope', required=True, type=Path)
    parser.add_argument('--phase', choices=['assembly', 'transfer'], required=True)
    args = parser.parse_args()
    report = inspect(args.root, args.catalog, args.scope, args.phase)
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report['complete'] and report['status'] == 'pass' else 2


if __name__ == '__main__':
    raise SystemExit(main())
