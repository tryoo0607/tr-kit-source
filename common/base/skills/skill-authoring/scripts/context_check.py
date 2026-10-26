#!/usr/bin/env python3
"""Compare declared instruction reads without invoking models or external tools."""
import argparse
import json
from pathlib import Path
import re

import yaml


def read_text(root, item):
    path = (root / item['path']).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f'read escapes root: {item["path"]}')
    text = path.read_text()
    section = item.get('section')
    if not section:
        return text
    if path.name == 'SKILL.md':
        raise ValueError('SKILL.md must be counted in full')
    lines = text.splitlines(keepends=True)
    headings = []
    fence = None
    for index, line in enumerate(lines):
        marker = re.match(r'^\s*(`{3,}|~{3,})', line)
        if marker:
            if fence is None:
                fence = marker[1][0]
            elif marker[1][0] == fence:
                fence = None
            continue
        match = re.match(r'^(#{1,6})\s+(.+?)\s*$', line) if fence is None else None
        if match:
            headings.append((index, len(match[1]), match[2]))
    selected = [h for h in headings if h[2] == section]
    if len(selected) != 1:
        raise ValueError(f'missing or ambiguous section: {item["path"]}: {section}')
    start, level, _ = selected[0]
    end = next((i for i, depth, _ in headings if i > start and depth <= level), len(lines))
    return ''.join(lines[start:end])


def measure(root, reads):
    seen = set()
    chars = duplicates = 0
    for item in reads:
        text = read_text(root, item)
        key = (item['path'], item.get('section'))
        chars += len(text)
        if key in seen:
            duplicates += len(text)
        seen.add(key)
    return {'chars': chars, 'read_steps': len(reads), 'duplicate_chars': duplicates}


def discovery(root):
    total = count = 0
    for path in sorted((root / 'skills').glob('*/SKILL.md')):
        content = path.read_text()
        match = re.match(r'^---\n(.*?)\n---', content, re.S)
        if not match:
            raise ValueError(f'missing frontmatter: {path}')
        data = yaml.safe_load(match[1])
        total += len(data['name']) + len(data['description'])
        count += 1
    return {'skills': count, 'name_description_chars': total}


def compare(before, after, cases):
    results = []
    for case in cases:
        old = measure(before, case['before'])
        new = measure(after, case['after'])
        allowance = case.get('allowed_growth_chars', 0)
        if type(allowance) is not int or allowance < 0 or (allowance and not case.get('growth_reason')):
            raise ValueError('growth allowance requires a nonnegative integer and reason')
        passed = new['chars'] <= old['chars'] + allowance and new['duplicate_chars'] <= old['duplicate_chars']
        results.append({'name': case['name'], 'before': old, 'after': new,
                        'delta_chars': new['chars'] - old['chars'],
                        'allowed_growth_chars': allowance, 'growth_reason': case.get('growth_reason'),
                        'unmeasured': case.get('unmeasured', []), 'passed': passed})
    old_discovery, new_discovery = discovery(before), discovery(after)
    passed = all(item['passed'] for item in results) and (
        new_discovery['name_description_chars'] <= old_discovery['name_description_chars'])
    return {'measurement': 'declared instruction characters; not tokens or observed runtime reads',
            'before_discovery': old_discovery, 'after_discovery': new_discovery,
            'cases': results, 'passed': passed}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', type=Path, required=True)
    parser.add_argument('--after', type=Path, required=True)
    parser.add_argument('--cases', type=Path, required=True)
    args = parser.parse_args()
    try:
        report = compare(args.before, args.after, json.loads(args.cases.read_text()))
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError) as error:
        parser.exit(2, f'context check failed: {error}\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report['passed'] else 1)
