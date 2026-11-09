"""Deployment-only scanning of verified package bytes with pinned native Gitleaks."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import tomllib


class ScanError(ValueError):
    """Scanner could not establish a trustworthy result."""


class FindingsError(ValueError):
    def __init__(self, counts):
        self.counts = counts
        super().__init__('unresolved deployment findings: ' + json.dumps(counts, sort_keys=True))


def strict_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('invalid JSON constant')))


def checksum_lines(blob):
    """Only canonical top-level files-map values already verified by delivery.verify."""
    data = strict_json(blob)
    if blob != (json.dumps(data, indent=2) + '\n').encode():
        raise ValueError('noncanonical deployment manifest')
    files = data['files']
    lines = blob.decode().splitlines()
    start = lines.index('  "files": {') + 1
    result = {}
    for offset, (key, digest) in enumerate(files.items()):
        line = '    ' + json.dumps(key) + ': ' + json.dumps(digest)
        if offset < len(files) - 1:
            line += ','
        number = start + offset + 1
        if lines[number - 1] != line:
            raise ValueError('ambiguous files map position')
        result[number] = (line, digest)
    return result


def _native(blobs, scanner):
    with tempfile.TemporaryDirectory(prefix='tr-delivery-scan-') as tmp:
        base = Path(tmp)
        payload = base / 'payload'
        payload.mkdir(mode=0o700)
        candidates = {}
        for number, (label, blob) in enumerate(blobs.items()):
            name = f'candidate-{number:08d}'
            target = payload / name
            target.write_bytes(blob)
            target.chmod(0o600)
            candidates[name] = label
        config = base / 'trusted.toml'
        config.write_text('[extend]\nuseDefault = true\n')
        ignore = base / 'empty-ignore'
        ignore.write_text('')
        report = base / 'redacted.json'
        env = {k: v for k, v in os.environ.items() if not k.startswith('GITLEAKS_')}
        try:
            run = subprocess.run([str(scanner), 'dir', str(payload), '--config', str(config),
                '--gitleaks-ignore-path', str(ignore), '--ignore-gitleaks-allow', '--redact=100',
                '--no-banner', '--no-color', '--log-level', 'error', '--report-format', 'json',
                '--report-path', str(report), '--exit-code', '42', '--timeout', '30'],
                cwd=tmp, env=env, capture_output=True, timeout=35)
            if run.returncode not in (0, 42):
                raise ScanError('deployment scanner failed; output withheld')
            findings = strict_json(report.read_bytes())
            if not isinstance(findings, list) or bool(findings) != (run.returncode == 42):
                raise ValueError()
            output = []
            for finding in findings:
                candidate = Path(finding['File'])
                if candidate.is_absolute():
                    if candidate.parent != payload:
                        raise ValueError()
                elif candidate.parent not in (Path('.'), Path('payload')):
                    raise ValueError()
                if candidate.name not in candidates:
                    raise ValueError()
                if not isinstance(finding['RuleID'], str):
                    raise ValueError()
                for field in ('StartLine', 'EndLine'):
                    if type(finding[field]) is not int or finding[field] < 1:
                        raise ValueError()
                if not all(isinstance(finding[f], str) for f in ('Match', 'Secret')):
                    raise ValueError()
                if finding['Secret'] != 'REDACTED' or not finding['RuleID']:
                    raise ValueError()
                line_count = len(blobs[candidates[candidate.name]].splitlines())
                if not (finding['StartLine'] <= finding['EndLine'] <= line_count):
                    raise ValueError()
                # Never expose scanner content, including on malformed reports.
                output.append((candidates[candidate.name], finding))
            return output
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
            raise ScanError('deployment scanner failed or returned invalid report; output withheld') from None


def scan(package, product, revision, scanner, *, candidate_paths=None):
    # Verify immediately before snapshotting; all scanner inputs are immutable bytes.
    from delivery import verify
    verify(package, product, revision)
    blobs = {str(p.relative_to(package)): p.read_bytes() for p in sorted(package.rglob('*'))
             if p.is_file() and '.git' not in p.relative_to(package).parts}
    with tempfile.TemporaryDirectory(prefix='tr-delivery-verify-') as tmp:
        snapshot = Path(tmp)
        for name, blob in blobs.items():
            target = snapshot / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(blob)
        verify(snapshot, product, revision)
    scanner = Path(scanner).expanduser().resolve() if scanner else None
    if scanner is None:
        raise ScanError('deployment requires an explicit pinned --gitleaks executable')
    expected = tomllib.loads((Path(__file__).resolve().parents[1] /
        'common/base/scripts/dev-tools.toml').read_text())['gitleaks']['version']
    try:
        version = subprocess.run([str(scanner), 'version'], capture_output=True, timeout=5)
        if version.returncode or version.stdout.decode().strip().lstrip('v') != expected:
            raise ValueError()
    except (OSError, ValueError, UnicodeError, subprocess.SubprocessError):
        raise ScanError('deployment scanner version check failed; output withheld') from None
    manifests = {'release.json', f'plugins/tr-{product}/assembly.json'}
    positions = {name: checksum_lines(blobs[name]) for name in manifests}
    projections = {}
    for name, positions_by_line in positions.items():
        lines = blobs[name].decode().splitlines(keepends=True)
        for number, (line, digest) in positions_by_line.items():
            # Replace just the JSON value; preserve keys, other content and line boundaries.
            prefix, separator, _ = line.rpartition(': ')
            lines[number - 1] = prefix + separator + '""' + (',' if line.endswith(',') else '') + '\n'
        projections[name] = ''.join(lines).encode()
    candidates = set(blobs) if candidate_paths is None else set(candidate_paths)
    if not candidates <= set(blobs):
        raise ValueError('unknown outgoing candidate')
    whole_original = _native(blobs, scanner)
    original = [(name, finding) for name, finding in whole_original if name in candidates]
    classified = 0
    for name, finding in original:
        number = finding['StartLine']
        known = positions.get(name, {}).get(number)
        if (finding['RuleID'] != 'generic-api-key' or finding['EndLine'] != number or
                known is None or finding['Secret'] != 'REDACTED'):
            continue
        line, digest = known
        # Gitleaks columns are not authoritative. Reconstruct every possible redacted
        # match at the verified digest position and require a unique explanation.
        match = finding['Match']
        if match.count('REDACTED') != 1:
            continue
        recovered = match.replace('REDACTED', digest)
        starts = [i for i in range(len(line)) if line.startswith(recovered, i)] if recovered else []
        digest_start = len(line.rsplit(': ', 1)[0]) + 3
        explanations = [i for i in starts if i + match.index('REDACTED') == digest_start]
        if len(starts) == 1 and len(explanations) == 1:
            classified += 1
    whole_projection = _native(projections, scanner)
    projection = [(name, finding) for name, finding in whole_projection if name in candidates]
    counts = {'original': len(original), 'classified': classified,
              'unresolved': len(original) - classified + len(projection),
              'projection': len(projection),
              'whole_package_original': len(whole_original),
              'unchanged_original': len(whole_original) - len(original),
              'unchanged_projection': len(whole_projection) - len(projection)}
    if counts['unresolved']:
        raise FindingsError(counts)
    return counts
