"""Shared own Git/literal/scanner checks; product responses live in adapters."""
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
    def __init__(self, message, diagnostic=None):
        super().__init__(message)
        self.diagnostic = diagnostic or {}


class PolicyViolation(GuardError):
    pass



def git(repo, *args):
    env = dict(os.environ, GIT_NO_REPLACE_OBJECTS='1')
    result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, timeout=30, env=env)
    if result.returncode:
        raise GuardError('Git inspection failed (unknown range or unsupported repository state)')
    return result.stdout


def validate_artifact_policy(root, entry):
    """Exceptions relax artifact classification only, never the secret scan."""
    for key in ('local_only', 'allow_artifacts'):
        patterns = entry.get(key, [])
        if not isinstance(patterns, list) or any(
                not isinstance(p, str) or not p or '\x00' in p or '\\' in p or
                p.startswith('/') or any(c in ('', '.', '..') for c in p.split('/'))
                for p in patterns):
            raise GuardError('invalid artifact policy')
    allowances = entry.get('allow_artifacts', [])
    if allowances and (root.name != 'tr-local-docs' or any(
            p.split('/')[-2:] != ['_bmad-output', '**'] for p in allowances)):
        raise GuardError('artifact allowances require an explicit tr-local-docs root and _bmad-output/** suffix')


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
    validate_artifact_policy(root, entry)
    if 'scanner_sha256' in policy:
        verify_scanner(scanner)
        if policy['scanner_sha256'] != hashlib.sha256(scanner.read_bytes()).hexdigest():
            raise GuardError('registered scanner changed; operation blocked')
    return root, policy, entry


def artifact_check(paths, entry):
    for name in paths:
        if any(fnmatch.fnmatchcase(name, p) for p in entry.get('local_only', [])) and not any(
                fnmatch.fnmatchcase(name, p) for p in entry.get('allow_artifacts', [])):
            raise PolicyViolation('local-only artifact blocked')


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
            checksum_row = (r'[A-Za-z0-9][A-Za-z0-9._~!/-]* '
                r'v[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?'
                r'(?:\+incompatible)?(?:/go\.mod)? '
                r'h1:[A-Za-z0-9+/]{42}[AEIMQUYcgkosw048]=')
            # v8.30.1 may supply a preceding LF, or the full canonical block
            # when the last line lacks a newline. Every supplied row must fit;
            # a multiline search for any good row would hide adjacent secrets.
            checksum_line = r'^(?:\r?\n)?' + checksum_row + r'(?:\r?\n' + checksum_row + r')*\r?$'
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
            raise GuardError('secret detected; finding content is redacted', safe_findings(findings))
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


def shell_continuations(command):
    """Remove shell continuation bytes outside single quotes, not quoted data."""
    output, quote, i = [], None, 0
    while i < len(command):
        char = command[i]
        if char == '\\' and quote != "'" and i + 1 < len(command):
            if command[i+1] == '\n':
                i += 2
                continue
            output.extend(command[i:i+2]); i += 2
            continue
        if char in ("'", '"'):
            if quote is None: quote = char
            elif quote == char: quote = None
        output.append(char); i += 1
    return ''.join(output)


BOUNDARY = '\x00'


def literal_tokens(command):
    """Literal word/quote/operator boundaries, without expansion or execution."""
    command = shell_continuations(command)
    tokens, word, quote, active, i = [], [], None, False, 0
    def flush():
        nonlocal word, active
        if active: tokens.append(''.join(word))
        word, active = [], False
    while i < len(command):
        c = command[i]
        if quote == "'":
            if c == "'": quote = None
            else: word.append(c)
        elif c == '\\' and i+1 < len(command):
            next_char = command[i+1]
            if quote == '"' and next_char not in '$`"\\': word.append(c)
            else: word.append(next_char); i += 1
            active = True
        elif quote == '"':
            if c == '"': quote = None
            else: word.append(c)
        elif c in ("'", '"'):
            quote = c; active = True
        elif c in ';|&()\n':
            flush(); tokens.append(BOUNDARY)
        elif c in ' \t\r':
            flush()
        elif c == '#' and not active:
            while i < len(command) and command[i] != '\n': i += 1
            flush(); tokens.append(BOUNDARY)
            continue
        else:
            word.append(c); active = True
        i += 1
    if quote is not None: raise ValueError('unclosed literal quote')
    flush()
    return tokens


def command_reason(command):
    """Recognize tested literal Git forms; never evaluate shell substitutions or scripts."""
    try:
        tokens = literal_tokens(command)
    except ValueError:
        return None
    for i, token in enumerate(tokens):
        if token == BOUNDARY or Path(token).name != 'git':
            continue
        start = i
        while start and tokens[start-1] != BOUNDARY:
            start -= 1
        prefix = tokens[start:i]
        if prefix and prefix[0] == 'env':
            prefix = unwrap_env_args(prefix[1:])
        if any(not re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', part) for part in prefix):
            continue
        rest = []
        for t in tokens[i+1:]:
            if t == BOUNDARY:
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
            while start and tokens[start-1] != BOUNDARY:
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
                if arg.partition('=')[0] == '--pathspec-from-file':
                    return 'pathspec file targets not established; operation blocked'
                short_flags = arg[1:] if not arg.startswith('--') else ''
                if part == 'commit':
                    for pos, flag in enumerate(short_flags):
                        if flag in 'mFCcSt':
                            short_flags = short_flags[:pos]
                            break
                if part == 'add' and (arg in {'--all', '--update'} or (not arg.startswith('--') and any(c in arg[1:] for c in 'Au'))):
                    update_all = True
                if part == 'commit' and (arg == '--all' or 'a' in short_flags):
                    return 'blanket staging requires explicit file paths'
                if arg == '--no-verify' or (part == 'commit' and 'n' in short_flags):
                    return 'visible Git hook bypass'
                if arg in {'-m', '--message', '-F', '--file', '-C', '--reuse-message', '-c', '--reedit-message',
                           '--author', '--date', '--cleanup', '--trailer', '--fixup', '--squash', '--template', '-t'}:
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


def verify_scanner(scanner):
    """Verify an explicitly selected official provision receipt; no installation."""
    try:
        import tomllib
    except ImportError:
        raise GuardError('native inspection requires Python 3.11; operation blocked') from None
    config = tomllib.loads(Path(__file__).with_name('secret-tools.toml').read_text())['gitleaks']
    version = config['version']
    scanner = Path(scanner)
    if not scanner.is_absolute() or scanner.is_symlink() or scanner.resolve() != scanner:
        raise GuardError('scanner must be a regular absolute provisioned path')
    prefix = scanner.parent.parent
    if scanner.parent.name != 'bin' or scanner.name != 'gitleaks':
        raise GuardError('unsupported scanner receipt layout')
    if (prefix / 'provisioned.json').is_symlink():
        raise GuardError('scanner receipt must be a regular file')
    receipt = json.loads((prefix / 'provisioned.json').read_text())
    if (not isinstance(receipt, dict) or not isinstance(receipt.get('version'), str) or
            receipt['version'].lstrip('v') != version or
            receipt.get('archive_sha256') != config['linux_x64_sha256'] or
            receipt.get('binary_sha256') != hashlib.sha256(scanner.read_bytes()).hexdigest() or
            not os.access(scanner, os.X_OK)):
        raise GuardError('trusted scanner identity failed; operation blocked')
    return scanner


def trusted_scanner():
    """Use only our provisioned, manifest-pinned scanner; never PATH/repo config."""
    try:
        import tomllib
    except ImportError:
        raise GuardError('native inspection requires Python 3.11; operation blocked') from None
    version = tomllib.loads(Path(__file__).with_name('secret-tools.toml').read_text())['gitleaks']['version']
    return verify_scanner(Path.home() / '.local/share/tr-kit/gitleaks' / version / 'bin/gitleaks')


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
    command = shell_continuations(command)
    lexer = shlex.shlex(command, posix=False, punctuation_chars=';&|()\n')
    lexer.whitespace = ' \t\r'
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


def python_inline_source(words):
    """Only literal Python -c, including harmless interpreter flags; never run it."""
    if not words or Path(words[0]).name not in {'python', 'python3'}:
        return None
    args = words[1:]
    while args and args[0] in {'-B', '-u', '-I', '-E', '-s', '-S'}:
        args = args[1:]
    return args[1] if len(args) >= 2 and args[0] == '-c' else None


def python_child_commands(command):
    """Inspect known literal child calls, not aliases, dynamic values or Python execution.

    A string without shell=True is one executable, not shell source. Original
    payload bytes are still scanned independently, including unrecognized code.
    """
    try:
        tokens = literal_tokens(command)
    except ValueError:
        return []
    children, words = [], []
    for token in tokens + [BOUNDARY]:
        if token != BOUNDARY:
            words.append(token)
            continue
        source = python_inline_source(words)
        words = []
        if source is None:
            continue
        try:
            tree = ast.parse(source)
        except (SyntaxError, ValueError):
            continue
        for call in ast.walk(tree):
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute) or not call.args:
                continue
            owner = call.func.value
            if not isinstance(owner, ast.Name):
                continue
            shell_call = (owner.id == 'os' and call.func.attr in {'system', 'popen'} or
                          owner.id == 'subprocess' and call.func.attr in {'getoutput', 'getstatusoutput'})
            argv_call = owner.id == 'subprocess' and call.func.attr in {
                'run', 'call', 'Popen', 'check_call', 'check_output'}
            if not (shell_call or argv_call):
                continue
            try:
                value = ast.literal_eval(call.args[0])
            except (ValueError, TypeError, SyntaxError):
                continue
            shell_options = [kw.value for kw in call.keywords if kw.arg == 'shell']
            if shell_options:
                if not isinstance(shell_options[0], ast.Constant) or type(shell_options[0].value) is not bool:
                    continue
                shell_call = shell_options[0].value
            if isinstance(value, str):
                children.append(value if shell_call else shlex.join([value]))
            elif isinstance(value, (list, tuple)) and value and all(isinstance(arg, str) for arg in value):
                children.append(value[0] if shell_call else shlex.join(value))
    return children


def disclosure_reason(command):
    """Inspect literal command positions only; quoted source/prose stays data."""
    command = shell_continuations(command)
    if literal_shell_secret_output(command):
        return 'secret environment value disclosure blocked'
    try:
        tokens = literal_tokens(command)
    except ValueError:
        return None
    segments, current = [], []
    for item in tokens + [BOUNDARY]:
        if item == BOUNDARY:
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
        python_source = python_inline_source([executable, *args])
        if python_source is not None:
            try:
                source = ast.parse(python_source)
            except (SyntaxError, ValueError):
                continue
            for statement in ast.walk(source):
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


SAFE_RULE_IDS = frozenset({'generic-api-key', 'github-pat', 'github-fine-grained-pat',
                          'aws-access-token', 'private-key'})


def safe_findings(findings):
    rules = sorted({f.get('RuleID') if isinstance(f.get('RuleID'), str) and
                    f.get('RuleID') in SAFE_RULE_IDS else 'other-rule' for f in findings})
    return {'count': len(findings), 'rules': rules}


def literal_command_view(command):
    """Separate narrow quoted cat data and Python stdin from shell positions.

    Gitleaks still receives the complete original input. This is not a shell
    interpreter: unknown heredoc headers are retained, not certified as safe.
    Python bodies become inspection-only -c arguments; the tool input is intact.
    """
    lines = command.splitlines(keepends=True)
    output, i = [], 0
    while i < len(lines):
        header = lines[i]
        match = re.fullmatch(r"[ \t]*cat[ \t]+[^\n]*?<<[ \t]*(['\"])([A-Za-z_][A-Za-z0-9_]*)\1[ \t]*\r?\n", header)
        python_match = re.fullmatch(
            r"[ \t]*(?P<exe>(?:/[A-Za-z0-9_.-]+)*/python3?|python3?)"
            r"(?P<flags>(?:[ \t]+-(?:B|u|I|E|s|S))*)[ \t]+-[ \t]*"
            r"<<[ \t]*(['\"])(?P<delimiter>[A-Za-z_][A-Za-z0-9_]*)\3[ \t]*\r?\n", header)
        if python_match:
            j = i + 1
            while j < len(lines) and lines[j].rstrip('\r\n') != python_match['delimiter']:
                j += 1
            if j < len(lines):
                body = ''.join(lines[i + 1:j])
                output.append(shlex.join([python_match['exe'], *python_match['flags'].split(), '-c', body]) + '\n')
                i = j + 1
                continue
        quote, comment, j = None, False, 0
        while j < len(header):
            c = header[j]
            if c == '\\' and quote != "'": j += 2; continue
            if c in ("'", '"'):
                if quote is None: quote = c
                elif quote == c: quote = None
            elif c == '#' and quote is None and (j == 0 or header[j-1] in ' \t<>'):
                comment = True; break
            j += 1
        # Refuse compound/expanding headers in this narrow data-only recognizer.
        if match and not comment and not any(c in header for c in (';', '&', '|', '$', '`', '(', ')')):
            j = i + 1
            while j < len(lines) and lines[j].rstrip('\r\n') != match[2]:
                j += 1
            if j < len(lines):
                # Keep actual cat operands/redirections inspectable (e.g. .env).
                output.append(header)
                i = j + 1
                continue
        output.append(header); i += 1
    return ''.join(output)


def inspect_input(payload):
    if (not isinstance(payload, dict) or not isinstance(payload.get('tool_name'), str) or
            not payload['tool_name'] or 'tool_input' not in payload):
        return 'native input inspection failed; operation blocked'
    tool = payload.get('tool_name', '')
    data = payload.get('tool_input', {})
    command = data.get('command', data.get('cmd', '')) if isinstance(data, dict) else ''
    if tool in ('Bash', 'exec_command'):
        if (not isinstance(data, dict) or not command or
                not (isinstance(command, str) or
                     isinstance(command, list) and all(isinstance(c, str) and c for c in command))):
            return 'native shell input inspection failed; operation blocked'
        if isinstance(command,str) and '\x00' in command:
            return 'native shell input inspection failed; operation blocked'
    if tool in READ_TOOLS and (not isinstance(data, dict) or not isinstance(data.get('file_path',data.get('path')), str)):
        return 'native file input inspection failed; operation blocked'
    if isinstance(command, list):
        command = shlex.join(command)
    if isinstance(command, str) and '\x00' in command:
        return 'native shell input inspection failed; operation blocked'
    if isinstance(command, str):
        command = literal_command_view(command)
    reason = None
    if tool in SHELL_TOOLS and isinstance(command, str):
        pending = [command]
        for index, candidate in enumerate(pending):
            if index >= 32:
                reason = 'nested command inspection limit; operation blocked'
                break
            reason = command_reason(candidate) or disclosure_reason(candidate)
            if reason:
                break
            pending.extend(literal_command_view(child) for child in python_child_commands(candidate))
    if not reason and tool in READ_TOOLS and isinstance(data, dict):
        if sensitive_path(data.get('file_path', data.get('path'))):
            reason = 'authentication or environment file disclosure blocked'
    if reason:
        return reason
    try:
        scan(native_candidates(data), trusted_scanner())
    except GuardError as error:
        return ('secret detected in literal input; operation blocked' + diagnostic_suffix(error.diagnostic, 'input') if
                str(error).startswith('secret detected') else 'secret inspection failed; operation blocked')
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        return 'secret inspection failed; operation blocked'
    return None


def inspect_output(payload):
    if not isinstance(payload, dict) or not supported_result_tool(payload.get('tool_name')):
        return {'status': 'unsupported'}
    if payload.get('hook_event_name', 'PostToolUse') not in ('PostToolUse', 'PostToolUseFailure'):
        return {'status': 'unsupported'}
    result = {k: payload[k] for k in ('tool_response', 'tool_result', 'tool_output', 'error') if k in payload}
    if not result:
        return {'status': 'error'}
    try:
        scan(native_candidates(result), trusted_scanner())
    except GuardError as error:
        return {'status': 'finding', 'diagnostic': error.diagnostic} if str(error).startswith('secret detected') else {'status': 'error'}
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        return {'status': 'error'}
    return {'status': 'clean'}


def native_candidates(value):
    """Preserve both structure and raw string bytes; never reconstruct source."""
    raw = json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
    if len(raw) > MAX_NATIVE_BYTES:
        raise GuardError('native content exceeds inspection limit')
    candidates, stack, visited = [raw], [value], 0
    while stack:
        item = stack.pop(); visited += 1
        if visited > 65536:
            raise GuardError('native content node limit exceeded')
        if isinstance(item, str):
            candidates.append(item.encode())
        elif isinstance(item, (dict,list)):
            needed = len(item) * (2 if isinstance(item,dict) else 1)
            if len(stack) + visited + needed > 65536:
                raise GuardError('native content node limit exceeded')
            if isinstance(item,dict):
                for k,v in item.items(): stack.extend((k,v))
            else: stack.extend(item)
    return candidates


def notice(result):
    if result['status'] != 'finding':
        return 'tr-kit: secret inspection failed; tool output withheld and execution stopped.'
    return SAFE_NOTICE + diagnostic_suffix(result.get('diagnostic', {}), 'output')


def diagnostic_suffix(diag, stage):
    rules = sorted({r if r in SAFE_RULE_IDS else 'other-rule' for r in diag.get('rules', []) if isinstance(r, str)})
    count = diag.get('count')
    return ((' stage=' + stage + '; findings=' + str(count) + '; rules=' + ','.join(rules))
                          if type(count) is int and 0 < count <= 100000 and rules else '')
