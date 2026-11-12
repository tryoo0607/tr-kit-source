#!/usr/bin/env python3
"""Local, explicitly enrolled Git checks. Never changes the index or executes shell input."""
import argparse
import ast
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile


class GuardError(ValueError):
    pass


def git(repo, *args):
    env = dict(os.environ, GIT_NO_REPLACE_OBJECTS='1')
    result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, timeout=30, env=env)
    if result.returncode:
        raise GuardError('Git inspection failed (unknown range or unsupported repository state)')
    return result.stdout


def load_policy(path, repo):
    policy = json.loads(Path(path).read_text())
    root = Path(os.fsdecode(git(repo, 'rev-parse', '--show-toplevel')).strip()).resolve()
    matches = [r for r in policy['repositories'] if Path(r['path']).resolve() == root]
    if len(matches) != 1:
        raise GuardError('repository is not explicitly enrolled')
    scanner = Path(policy['gitleaks'])
    if not scanner.is_absolute():
        raise GuardError('scanner must be an absolute trusted path')
    entry = matches[0]
    for key in ('local_only', 'allow_artifacts'):
        patterns = entry.get(key, [])
        if not isinstance(patterns, list) or any(not isinstance(p, str) or not p or p.startswith('/') or '..' in p.split('/') for p in patterns):
            raise GuardError('invalid artifact policy')
    return root, policy, entry


def artifact_check(paths, entry):
    for name in paths:
        if any(fnmatch.fnmatchcase(name, p) for p in entry.get('local_only', [])) and not any(
                fnmatch.fnmatchcase(name, p) for p in entry.get('allow_artifacts', [])):
            raise GuardError('local-only artifact blocked: ' + json.dumps(name, ensure_ascii=True))


def scan(blobs, scanner):
    # Neutral names prevent logical filenames from activating scanner path allowlists.
    # Materialize exact bytes, including symlink blobs, without following repository links.
    with tempfile.TemporaryDirectory(prefix='tr-commit-guard-') as tmp:
        base = Path(tmp)
        payload = base / 'payload'
        payload.mkdir(mode=0o700)
        labels = {}
        go_sums = []
        for number, item in enumerate(blobs):
            label, blob = item if isinstance(item, tuple) else (None, item)
            name = f'candidate-{number:08d}'
            target = payload / name
            with target.open('xb') as stream:
                target.chmod(0o600)
                stream.write(blob)
            labels[name] = label
            if isinstance(label, str) and Path(label).name == 'go.sum':
                go_sums.append(re.escape(name))
        config = base / 'trusted.toml'
        trusted = '[extend]\nuseDefault = true\n'
        if go_sums:
            # Extend only the heuristic rule, not stronger credential detectors.
            # Bind its exception to our exact neutral filenames AND canonical Go
            # checksum lines. All other lines and original bytes remain scanned.
            checksum_line = (r'^[A-Za-z0-9][A-Za-z0-9._~!/-]* '
                r'v[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?'
                r'(?:\+incompatible)?(?:/go\.mod)? '
                r'h1:[A-Za-z0-9+/]{42}[AEIMQUYcgkosw048]=$')
            trusted += ('[[rules]]\nid = "generic-api-key"\n'
                '[[rules.allowlists]]\ncondition = "AND"\nregexTarget = "line"\n'
                'paths = [' + json.dumps(r'(?:^|/)(?:' + '|'.join(go_sums) + ')$') + ']\n'
                'regexes = [' + json.dumps(checksum_line) + ']\n')
        config.write_text(trusted)
        ignore = base / 'empty-ignore'
        ignore.write_text('')
        report = base / 'redacted.json'
        env = {k: v for k, v in os.environ.items() if not k.startswith('GITLEAKS_')}
        result = subprocess.run([str(scanner), 'dir', str(payload), '--config', str(config),
                                 '--gitleaks-ignore-path', str(ignore), '--ignore-gitleaks-allow',
                                 '--redact=100', '--no-banner', '--no-color', '--log-level', 'error',
                                 '--report-format', 'json', '--report-path', str(report),
                                 '--exit-code', '42', '--timeout', '30'],
                                capture_output=True, cwd=tmp, env=env, timeout=35)
        if result.returncode == 42:
            try:
                findings = json.loads(report.read_text())
                if not isinstance(findings, list) or not findings:
                    raise ValueError()
                found = []
                for finding in findings:
                    path = finding['File']
                    if not isinstance(path, str):
                        raise ValueError()
                    candidate = Path(path)
                    if candidate.is_absolute():
                        if candidate.parent != payload:
                            raise ValueError()
                    elif candidate.parent not in (Path('.'), Path('payload')):
                        raise ValueError()
                    if candidate.name not in labels:
                        raise ValueError()
                    label = labels[candidate.name]
                    if label is not None and label not in found:
                        found.append(label)
            except (OSError, ValueError, KeyError, TypeError):
                raise GuardError('scanner returned invalid findings; operation blocked') from None
            raise GuardError('secret detected' + (' in ' + ', '.join(json.dumps(label, ensure_ascii=True) for label in found) if found else '') + '; finding content is redacted')
        if result.returncode:
            raise GuardError('scanner failed; operation blocked (no scanner output disclosed)')


def candidate_bytes(repo, names, commit=None):
    """Read typed object IDs, never revision expressions derived from filenames."""
    args = ('ls-tree', '-r', '-z', commit) if commit else ('ls-files', '--stage', '-z')
    entries = {}
    for record in git(repo, *args).split(b'\0'):
        if not record:
            continue
        metadata, path = record.split(b'\t', 1)
        mode, kind_or_oid, oid_or_stage = metadata.split()
        if commit:
            kind, oid = kind_or_oid, oid_or_stage
        else:
            oid = kind_or_oid
            if oid_or_stage != b'0':
                raise GuardError('unmerged index cannot establish candidate content')
            kind = b'commit' if mode == b'160000' else b'blob'
        entries[os.fsdecode(path)] = (mode, kind, oid)
    for name in names:
        if name not in entries:
            raise GuardError('candidate object metadata is missing')
        mode, kind, oid = entries[name]
        if mode == b'160000' and kind == b'commit':
            # A gitlink records a pointer; its object may exist only in the submodule.
            yield name, b'Subproject commit ' + oid + b'\n'
        elif mode in (b'100644', b'100755', b'120000') and kind == b'blob':
            yield name, git(repo, 'cat-file', 'blob', oid.decode('ascii'))
        else:
            raise GuardError('unsupported candidate object type')


def check_index(repo, policy_path):
    root, policy, entry = load_policy(policy_path, repo)
    names = [os.fsdecode(n) for n in git(root, 'diff', '--cached', '--name-only', '-z', '--diff-filter=ACMRT', '--no-renames').split(b'\0') if n]
    artifact_check(names, entry)
    # Check scanner availability even for an empty index; enrolled failures are fail closed.
    if not Path(policy['gitleaks']).is_file():
        raise GuardError('scanner is missing; operation blocked')
    scan(candidate_bytes(root, names), policy['gitleaks'])


def check_push(repo, policy_path, data):
    root, policy, entry = load_policy(policy_path, repo)
    commits = set()
    candidates = []
    for line in data.splitlines():
        fields = line.split()
        if len(fields) != 4:
            raise GuardError('malformed pre-push input')
        _, local, _, remote = fields
        if not all(re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', oid) for oid in (local, remote)):
            raise GuardError('invalid pre-push object')
        if set(local) == {'0'}:
            continue
        obj = local
        for depth in range(32):
            kind = git(root, 'cat-file', '-t', obj).strip()
            if kind != b'tag':
                break
            tag = git(root, 'cat-file', 'tag', obj)
            candidates.append(('tag object ' + obj[:12], tag))
            header = tag.split(b'\n', 1)[0]
            if not re.fullmatch(rb'object [0-9a-f]{40}|object [0-9a-f]{64}', header):
                raise GuardError('unsupported tag object')
            obj = header.decode().split()[1]
        else:
            raise GuardError('unsupported nested tag depth')
        local_commit = git(root, 'rev-parse', '--verify', local + '^{commit}').decode().strip()
        args = ['rev-list', local_commit]
        if set(remote) != {'0'}:
            remote_commit = git(root, 'rev-parse', '--verify', remote + '^{commit}').decode().strip()
            args.append('^' + remote_commit)
        if git(root, 'rev-parse', '--is-shallow-repository').strip() == b'true':
            raise GuardError('shallow history cannot establish a complete outgoing range')
        commits.update(git(root, *args).decode().splitlines())
    if not Path(policy['gitleaks']).is_file() and (commits or candidates):
        raise GuardError('scanner is missing; operation blocked')
    for commit in sorted(commits):
        names = [os.fsdecode(n) for n in git(root, 'diff-tree', '--root', '-m', '--no-commit-id', '--name-only', '-r', '-z', '--diff-filter=ACMRT', '--no-renames', commit).split(b'\0') if n]
        names = list(dict.fromkeys(names))
        artifact_check(names, entry)
        candidates.extend(candidate_bytes(root, names, commit))
        candidates.append(('commit message ' + commit[:12], git(root, 'show', '-s', '--format=%B', commit)))
    if commits or candidates:
        scan(candidates, policy['gitleaks'])


def command_reason(command):
    """Recognize tested literal Git forms; never evaluate shell substitutions or scripts."""
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=';&|()\n')
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return None
    for i, token in enumerate(tokens):
        if Path(token).name != 'git':
            continue
        start = i
        while start and tokens[start-1] not in {';', '&&', '||', '|', '&', '(', ')', '\n'}:
            start -= 1
        prefix = tokens[start:i]
        if prefix and prefix[0] == 'env':
            prefix = prefix[1:]
        if any(not re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', part) for part in prefix):
            continue
        rest = []
        for t in tokens[i+1:]:
            if t in {';', '&&', '||', '|', '&', '(', ')', '\n'}:
                break
            rest.append(t)
        n = 0
        while n < len(rest):
            part = rest[n]
            if part in {'-c', '--config-env'} and n+1 < len(rest) and rest[n+1].partition('=')[0].lower() == 'core.hookspath':
                return 'visible hook path override'
            if ((part.startswith('--config-env=') and part[len('--config-env='):].partition('=')[0].lower() == 'core.hookspath') or
                    (part.startswith('-c') and part[2:].partition('=')[0].lower() == 'core.hookspath')):
                return 'visible hook path override'
            if part in {'-C', '-c', '--git-dir', '--work-tree', '--namespace', '--config-env'}:
                n += 2
                continue
            if part.startswith('-'):
                n += 1
                continue
            break
        if n >= len(rest):
            continue
        part, args = rest[n], rest[n+1:]
        if part in {'commit', 'push'}:
            start = i
            while start and tokens[start-1] not in {';', '&&', '||', '|', '&', '(', ')', '\n'}:
                start -= 1
            if any(re.match(r'^(?:GIT_CONFIG_COUNT|GIT_CONFIG_KEY_\d+|HUSKY|SKIP)=', t)
                   for t in tokens[start:i]):
                return 'visible hook bypass configuration'
        if part == 'config' and any(a.lower() == 'core.hookspath' for a in args) and not any(a in {'--get', '--get-all', '--get-regexp', '--get-urlmatch', '--list', '-l'} for a in args):
            return 'visible persistent hook path change'
        if part not in {'add', 'commit', 'push'}:
            continue
        positional = False
        skip_value = False
        update_all = False
        paths = []
        for arg in args:
            if skip_value:
                skip_value = False
                continue
            if arg == '--' and not positional:
                positional = True
                continue
            if not positional and arg.startswith('-'):
                short_flags = arg[1:] if not arg.startswith('--') else ''
                if part == 'commit':
                    for pos, flag in enumerate(short_flags):
                        if flag in 'mFCc':
                            short_flags = short_flags[:pos]
                            break
                if part == 'add' and (arg in {'--all', '--update'} or (not arg.startswith('--') and any(c in arg[1:] for c in 'Au'))):
                    update_all = True
                if part == 'commit' and (arg == '--all' or 'a' in short_flags):
                    return 'blanket staging requires explicit file paths'
                if arg == '--no-verify' or (part == 'commit' and 'n' in short_flags):
                    return 'visible Git hook bypass'
                if arg in {'-m', '--message', '-F', '--file', '-C', '--reuse-message', '-c', '--reedit-message', '--pathspec-from-file'}:
                    skip_value = True
                continue
            if part == 'add':
                paths.append(arg)
                scope = re.sub(r'^:\([^)]*\)', '', arg)
                while scope.startswith('./'):
                    scope = scope[2:]
                if scope in {'', '.', ':', ':/', '/', '*', '**', ':/*', ':/**'}:
                    return 'blanket staging requires explicit file paths'
        if part == 'add' and update_all and not paths:
            return 'blanket staging requires explicit file paths'
    return None


MAX_NATIVE_BYTES = 8 * 1024 * 1024
SAFE_NOTICE = 'tr-kit: tool output withheld by secret inspection; original content is not disclosed.'
SHELL_TOOLS = {'Bash', 'exec_command', 'write_stdin'}
READ_TOOLS = {'Read', 'read_file'}
RESULT_TOOLS = SHELL_TOOLS | READ_TOOLS | {'Write', 'Edit', 'MultiEdit', 'Glob', 'Grep',
    'NotebookEdit', 'WebFetch', 'WebSearch', 'apply_patch', 'list_mcp_resources',
    'list_mcp_resource_templates', 'read_mcp_resource'}


def supported_result_tool(name):
    return isinstance(name, str) and (name in RESULT_TOOLS or bool(re.fullmatch(r'mcp__[A-Za-z0-9_-]+__[A-Za-z0-9_.-]+', name)))


def trusted_scanner():
    """Use only our provisioned, manifest-pinned scanner; never PATH/repo config."""
    try:
        import tomllib
    except ImportError:
        raise GuardError('native inspection requires Python 3.11; operation blocked') from None
    config = tomllib.loads(Path(__file__).with_name('dev-tools.toml').read_text())['gitleaks']
    version = config['version']
    prefix = Path.home() / '.local/share/tr-kit/gitleaks' / version
    scanner = prefix / 'bin/gitleaks'
    receipt = json.loads((prefix / 'provisioned.json').read_text())
    if (not isinstance(receipt, dict) or not isinstance(receipt.get('version'), str) or
            receipt['version'].lstrip('v') != version or
            receipt.get('archive_sha256') != config['linux_x64_sha256'] or
            receipt.get('binary_sha256') != hashlib.sha256(scanner.read_bytes()).hexdigest() or
            not os.access(scanner, os.X_OK)):
        raise GuardError('trusted scanner identity failed; operation blocked')
    return scanner


def sensitive_path(value):
    if not isinstance(value, str):
        return False
    path = value.rstrip('/')
    name = Path(path).name.lower()
    if name in {'.env.example', '.env.sample', '.env.template'}:
        return False
    return (name in {'.env', 'auth.json', 'credentials.json', '.credentials.json',
                     '.claude.json', '.netrc', '.npmrc', '.pypirc'} or
            name.startswith('.env.') or
            bool(re.search(r'(?:^|/)(?:\.aws/credentials|proc/(?:self|[0-9]+)/environ)$', path)))


def secret_variable(name):
    return bool(re.search(r'(?i)(?:TOKEN|SECRET|PASSWORD|CREDENTIAL|AUTH|API_KEY)', name))


def unwrap_env_args(args):
    # Keep argument quoting intact for the literal echo/printf inspection.
    while args:
        if re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', args[0]) or args[0] in {'-0', '--null', '-i', '--ignore-environment'} or args[0].startswith(('--unset=', '--chdir=')):
            args = args[1:]
        elif args[0] in {'-u', '--unset', '-C', '--chdir'} and len(args) >= 2:
            args = args[2:]
        elif args[0] == '--':
            return args[1:]
        else:
            break
    return args


def literal_shell_secret_output(command):
    lexer = shlex.shlex(command, posix=False, punctuation_chars=';&|()\n')
    lexer.whitespace_split = True
    try:
        words = list(lexer)
    except ValueError:
        return False
    segments, current = [], []
    for word in words + [';']:
        if word in {';', '&&', '||', '|', '&', '(', ')', '\n'}:
            segments.append(current)
            current = []
        else:
            current.append(word)
    for words in segments:
        while words and re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', words[0]):
            words = words[1:]
        if words and Path(words[0].strip('"\'')).name == 'env':
            words = unwrap_env_args(words[1:])
        if not words or Path(words[0].strip('"\'')).name not in {'echo', 'printf'}:
            continue
        for word in words[1:]:
            if word.startswith("'"):
                continue
            for name in re.findall(r'(?<!\\)\$\{?([A-Za-z_][A-Za-z0-9_]*)', word):
                if secret_variable(name):
                    return True
    return False


def disclosure_reason(command):
    """Inspect literal command positions only; quoted source/prose stays data."""
    if literal_shell_secret_output(command):
        return 'secret environment value disclosure blocked'
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=';&|()\n')
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return None
    segments, current = [], []
    for item in tokens + [';']:
        if item in {';', '&&', '||', '|', '&', '(', ')', '\n'}:
            if current:
                segments.append(current)
            current = []
        else:
            current.append(item)
    for words in segments:
        while words and re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', words[0]):
            words = words[1:]
        if not words:
            continue
        executable = Path(words[0]).name
        args = words[1:]
        if executable == 'env':
            args = unwrap_env_args(args)
            if not args:
                return 'whole environment disclosure blocked'
            # env assignments before a normal command are preserved.
            executable, args = Path(args[0]).name, args[1:]
        if (executable == 'printenv' and (not args or all(arg in {'-0','--null'} for arg in args) or
                any(re.search(r'(?i)(?:TOKEN|SECRET|PASSWORD|CREDENTIAL|AUTH|API_KEY)', arg) for arg in args)) or
                (executable in {'set', 'export', 'declare', 'typeset'} and
                 (not args or args in [['-p'], ['-x'], ['-xp'], ['-px']]))):
            return 'whole environment disclosure blocked'
        if executable in {'cat', 'head', 'tail', 'sed', 'awk', 'jq', 'bat', 'less', 'more', 'strings', 'base64'} and any(sensitive_path(arg) for arg in args):
            return 'authentication or environment file disclosure blocked'
        if executable in {'sh', 'bash', 'zsh'} and len(args) >= 2 and args[0] in {'-c', '-lc'}:
            if disclosure_reason(args[1]):
                return 'nested environment or authentication disclosure blocked'
        if executable in {'node', 'nodejs'} and len(args) >= 2 and args[0] in {'-e', '--eval', '-p', '--print'}:
            match = re.fullmatch(r'\s*(?:console\.log\(\s*(?:JSON\.stringify\(\s*)?)?process\.env(?P<access>\.[A-Za-z_][A-Za-z0-9_]*|\[[^]]+\])?\s*\)*\s*;?\s*', args[1])
            if match:
                access = match['access']
                try:
                    key = access[1:] if access and access.startswith('.') else ast.literal_eval(access[1:-1]) if access else None
                except (ValueError, SyntaxError):
                    key = None
                if not isinstance(key, str) or secret_variable(key):
                    return 'environment value disclosure blocked'
        if executable in {'python', 'python3'} and len(args) >= 2 and args[0] == '-c':
            try:
                source = ast.parse(args[1])
            except (SyntaxError, ValueError):
                continue
            for statement in source.body:
                if not isinstance(statement, ast.Expr) or not isinstance(statement.value, ast.Call):
                    continue
                call = statement.value
                name = call.func.id if isinstance(call.func, ast.Name) else getattr(call.func, 'attr', '')
                if name not in {'print', 'pprint'}:
                    continue
                for argument in call.args:
                    if isinstance(argument, ast.Compare) or (isinstance(argument, ast.Call) and isinstance(argument.func, ast.Name) and argument.func.id in {'bool', 'len', 'hash'}):
                        continue
                    parents = {child: parent for parent in ast.walk(argument) for child in ast.iter_child_nodes(parent)}
                    for node in ast.walk(argument):
                        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and
                                isinstance(node.func.value, ast.Name) and node.func.value.id == 'os' and
                                node.func.attr == 'getenv' and node.args and isinstance(node.args[0], ast.Constant) and
                                isinstance(node.args[0].value, str) and secret_variable(node.args[0].value)):
                            return 'secret environment value disclosure blocked'
                        if (isinstance(node, ast.Attribute) and node.attr == 'environ' and
                                isinstance(node.value, ast.Name) and node.value.id == 'os'):
                            parent = parents.get(node)
                            key = None
                            if isinstance(parent, ast.Subscript) and parent.value is node and isinstance(parent.slice, ast.Constant):
                                key = parent.slice.value
                            elif isinstance(parent, ast.Attribute) and parent.attr == 'get':
                                lookup = parents.get(parent)
                                if isinstance(lookup, ast.Call) and lookup.func is parent and lookup.args and isinstance(lookup.args[0], ast.Constant):
                                    key = lookup.args[0].value
                            if isinstance(key, str) and not secret_variable(key):
                                continue
                            return 'whole environment disclosure blocked'
                        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and
                                node.func.id == 'open' and node.args and
                                isinstance(node.args[0], ast.Constant) and sensitive_path(node.args[0].value)):
                            return 'authentication or environment file disclosure blocked'
    return None


def deny(reason):
    return {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny',
                                   'permissionDecisionReason': reason}}


def agent(product, payload):
    if not isinstance(payload, dict):
        raise GuardError('invalid native payload; operation blocked')
    tool = payload.get('tool_name', '')
    data = payload.get('tool_input', {})
    command = data.get('command', data.get('cmd', '')) if isinstance(data, dict) else ''
    if isinstance(command, list):
        command = shlex.join(command)
    reason = command_reason(command) if isinstance(command, str) else None
    if not reason and tool in SHELL_TOOLS and isinstance(command, str):
        reason = disclosure_reason(command)
    if not reason and tool in READ_TOOLS and isinstance(data, dict):
        if sensitive_path(data.get('file_path', data.get('path'))):
            reason = 'authentication or environment file disclosure blocked'
    if reason:
        return deny(reason)
    # Scan all literal input, including source snippets and non-shell tools.
    literal = json.dumps(data, ensure_ascii=False).encode()
    if len(literal) > MAX_NATIVE_BYTES:
        return deny('native input exceeds inspection limit; operation blocked')
    try:
        scan([literal], trusted_scanner())
    except GuardError as error:
        return deny('secret detected in literal input; operation blocked' if str(error).startswith('secret detected') else
                    'secret inspection failed; operation blocked')
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        return deny('secret inspection failed; operation blocked')
    return {}


def protected_output(product, payload, failed=False):
    notice = ('tr-kit: secret inspection failed; tool output withheld and execution stopped.'
              if failed else SAFE_NOTICE)
    if payload.get('hook_event_name') == 'PostToolUseFailure':
        return {'continue': False, 'stopReason': 'tr-kit: ' + ('inspection failed; ' if failed else 'secret detected; ') + 'failure result replacement is unsupported; stopped.'}
    if product == 'codex':
        # Codex PostToolUse uses a blocking reason as the replacement tool result.
        result = {'decision': 'block', 'reason': notice}
    else:
        tool = payload.get('tool_name')
        original = payload.get('tool_response')
        if tool == 'Bash':
            replacement = {'stdout': notice, 'stderr': '', 'interrupted': False, 'isImage': False}
        elif tool == 'Read' and isinstance(original, dict) and original.get('type') == 'text' and isinstance(original.get('file'), dict):
            replacement = {'type': 'text', 'file': {'filePath': '[withheld]', 'content': notice,
                           'numLines': 1, 'startLine': 1, 'totalLines': 1}}
        elif isinstance(tool, str) and tool.startswith('mcp__'):
            # Official McpOutput admits string, block array and plain-object
            # variants. A fixed string is valid independently of original shape.
            replacement = notice
        else:
            return {'continue': False, 'stopReason': 'tr-kit: result replacement contract is unsupported; stopped.'}
        result = {'hookSpecificOutput': {'hookEventName': 'PostToolUse', 'updatedToolOutput': replacement}}
    if failed:
        result.update({'continue': False, 'stopReason': 'tr-kit: secret inspection failed; stopped.'})
    return result


def output(product, payload):
    if not isinstance(payload, dict):
        raise GuardError('invalid native payload; operation blocked')
    event = payload.get('hook_event_name', 'PostToolUse')
    if event not in {'PostToolUse', 'PostToolUseFailure'}:
        return {'continue': False, 'stopReason': 'tr-kit: tool event contract is unsupported; stopped.'}
    if not supported_result_tool(payload.get('tool_name')):
        return {'continue': False, 'stopReason': 'tr-kit: tool output protection is unsupported; stopped.'}
    result = {k: payload[k] for k in ('tool_response', 'tool_result', 'tool_output', 'error') if k in payload}
    if not result:
        return {'continue': False, 'stopReason': 'tr-kit: tool result contract is unknown; stopped.'}
    raw = json.dumps(result, ensure_ascii=False).encode()
    try:
        if len(raw) > MAX_NATIVE_BYTES:
            raise GuardError('native output exceeds inspection limit')
        scan([raw], trusted_scanner())
    except GuardError as error:
        return protected_output(product, payload, failed=not str(error).startswith('secret detected'))
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        return protected_output(product, payload, failed=True)
    return {}


def native_payload():
    raw = sys.stdin.buffer.read(MAX_NATIVE_BYTES + 1)
    if len(raw) > MAX_NATIVE_BYTES:
        raise GuardError('native payload exceeds inspection limit; operation blocked')
    return json.loads(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['index', 'push', 'agent', 'output'])
    parser.add_argument('--repo', default='.')
    parser.add_argument('--event', choices=['PostToolUse', 'PostToolUseFailure'], default='PostToolUse')
    parser.add_argument('--policy', type=Path)
    parser.add_argument('--product', choices=['codex', 'claude'], default='codex')
    args = parser.parse_args()
    try:
        if args.mode in {'agent', 'output'}:
            payload = native_payload()
            if args.mode == 'output' and (not isinstance(payload, dict) or payload.get('hook_event_name') != args.event):
                raise GuardError('native event contract mismatch; operation blocked')
            print(json.dumps((agent if args.mode == 'agent' else output)(args.product, payload)))
        elif args.mode == 'index':
            check_index(args.repo, args.policy)
        else:
            check_push(args.repo, args.policy, sys.stdin.read())
    except (GuardError, OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
        # Never expose subprocess stdout/stderr, blob content or JSON input.
        if args.mode == 'agent':
            print(json.dumps(deny('native input inspection failed; operation blocked')))
        elif args.mode == 'output':
            stopped = {'continue': False, 'stopReason': 'tr-kit: output inspection failed; stopped.'}
            if args.event == 'PostToolUse':
                if args.product == 'codex':
                    stopped.update({'decision': 'block', 'reason': 'tr-kit: output inspection failed; result blocked.'})
                else:
                    # No tool-specific replacement is safe without a parsed envelope.
                    stopped['stopReason'] = 'tr-kit: output contract unknown; replacement unsupported; stopped.'
            print(json.dumps(stopped))
            return 0
        print('commit-guard: ' + (str(error) if isinstance(error, GuardError) else 'inspection error; operation blocked'), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
