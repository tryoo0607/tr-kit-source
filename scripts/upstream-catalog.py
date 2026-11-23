#!/usr/bin/env python3
"""Fingerprint explicit external files. Never walks a host or copies source text."""
import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'common/base/scripts'))
from upstream_guard import MAX_BYTES, make_catalog


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        output = args.output.absolute()
        if output.exists() or output.is_symlink():
            raise ValueError('output must be a new file; review replacement explicitly')
        catalog = make_catalog(args.source)
        encoded = (json.dumps(catalog, ensure_ascii=False, indent=2) + '\n').encode()
        if len(encoded) > MAX_BYTES:
            raise ValueError('catalog exceeds inspection limit')
        # Exclusive creation prevents overwriting a selected source or existing policy.
        with output.open('xb') as stream:
            stream.write(encoded)
    except Exception:
        print('catalog creation failed; check explicit inputs and output', file=sys.stderr)
        return 2
    print('catalog created; no hook registered or activated')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
