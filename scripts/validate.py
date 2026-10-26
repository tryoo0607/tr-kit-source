#!/usr/bin/env python3
"""Validate skills with the pinned creator, preserving compatibility metadata."""
import argparse
import importlib.util
from pathlib import Path
import re
import sys
import tempfile

import yaml


def validate_skill(folder, creator):
    path = folder / 'SKILL.md'
    try:
        content = path.read_text()
        match = re.match(r'^---\n(.*?)\n---(?:\n|$)', content, re.S)
        if not match:
            return False, 'Missing or invalid YAML frontmatter'
        metadata = yaml.safe_load(match[1])
        if not isinstance(metadata, dict):
            return False, 'Frontmatter must be a dictionary'
        if metadata.get('name') != folder.name:
            return False, 'Skill name must match its folder'
        if not isinstance(metadata.get('description'), str) or not metadata['description'].strip():
            return False, 'Description must be a non-empty string'
        validator = creator / 'scripts/quick_validate.py'
        spec = importlib.util.spec_from_file_location('pinned_creator_validator', validator)
        module = importlib.util.module_from_spec(spec)
        previous = sys.dont_write_bytecode
        try:
            sys.dont_write_bytecode = True
            spec.loader.exec_module(module)
        finally:
            sys.dont_write_bytecode = previous
        if 'compatibility' not in metadata:
            return module.validate_skill(folder)
        compatibility = metadata['compatibility']
        if not isinstance(compatibility, str) or not compatibility.strip():
            return False, 'Compatibility must be a non-empty string'
        # The pinned creator predates this field. Validate the rest through a
        # temporary view; neither the original skill nor the release is changed.
        remaining = {key: value for key, value in metadata.items() if key != 'compatibility'}
        with tempfile.TemporaryDirectory(prefix='skill-validation-') as temporary:
            view = Path(temporary)
            (view / 'SKILL.md').write_text('---\n' + yaml.safe_dump(remaining, allow_unicode=True)
                                         + '---\n' + content[match.end():])
            return module.validate_skill(view)
    except (OSError, yaml.YAMLError) as error:
        return False, str(error)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('skill', type=Path)
    parser.add_argument('--creator', type=Path, required=True)
    args = parser.parse_args()
    valid, message = validate_skill(args.skill, args.creator)
    print(message)
    raise SystemExit(0 if valid else 1)
