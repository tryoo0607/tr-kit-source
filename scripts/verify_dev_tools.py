#!/usr/bin/env python3
"""Exercise bundled instructions' real tools against isolated local fixtures."""
import argparse
from functools import partial
import http.server
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import tomllib
import uuid


def verify(plugin, toolchain, network_context7=False):
    evidence = Path(tempfile.mkdtemp(prefix='tr-devtools-proof-'))
    checks = []
    config = tomllib.loads((plugin / 'scripts/dev-tools.toml').read_text())
    env = dict(os.environ, PATH=f"{toolchain / 'bin'}:{os.environ.get('PATH', '')}",
               XDG_CACHE_HOME=str(evidence / 'cache'), XDG_CONFIG_HOME=str(evidence / 'config'),
               XDG_STATE_HOME=str(evidence / 'state'),
               PLAYWRIGHT_BROWSERS_PATH=str(toolchain / 'browsers'),
               SEMGREP_SETTINGS_FILE=str(evidence / 'semgrep-settings.yml'),
               SEMGREP_LOG_FILE=str(evidence / 'semgrep.log'),
               SEMGREP_ENABLE_VERSION_CHECK='0', SEMGREP_SEND_METRICS='off',
               TRIVY_CACHE_DIR=str(evidence / 'trivy-cache'),
               CONTEXT7_API_KEY='', CI='1')
    # Never inherit platform-upload credentials into local scan probes.
    env.pop('SEMGREP_APP_TOKEN', None)
    env.pop('SEMGREP_APP_URL', None)
    env.pop('ANTHROPIC_API_KEY', None)
    logs = []

    def run(*args, expected=(0,), timeout=90):
        result = subprocess.run(list(map(str, args)), cwd=evidence, env=env,
                                capture_output=True, text=True, timeout=timeout)
        name = f'{len(logs):02d}'
        (evidence / f'{name}.stdout').write_text(result.stdout)
        (evidence / f'{name}.stderr').write_text(result.stderr)
        logs.append({'args': list(map(str, args)), 'exit_code': result.returncode, 'log': name})
        if result.returncode not in expected:
            raise RuntimeError(f'{args[0]} exited {result.returncode}: {result.stderr[-1500:]}')
        return result.stdout

    session = 'proof-' + uuid.uuid4().hex[:12]
    other = session + '-other'
    opened = []
    server = None
    try:
        for name, version in [('ctx7', config['node']['ctx7']),
                              ('playwright-cli', config['node']['playwright_cli']),
                              ('semgrep', config['python']['semgrep']),
                              ('trivy', config['trivy']['version'])]:
            if version not in run(toolchain / 'bin' / name, '--version'):
                raise RuntimeError(f'version mismatch: {name}')
        checks.append('pinned executable versions')
        source = evidence / 'src'
        source.mkdir()
        (source / 'unsafe.py').write_text('def parse(user_input):\n    return eval(user_input)\n')
        rule = evidence / 'rule.yaml'
        rule.write_text('rules:\n- id: no-eval\n  languages: [python]\n'
                        '  message: Untrusted evaluation\n  severity: ERROR\n  pattern: eval(...)\n')
        result = evidence / 'semgrep-unsafe.json'
        run(toolchain / 'bin/semgrep', 'scan', '--config', rule, '--metrics', 'off',
            '--error', '--json', '--output', result, source, expected=(1,))
        scan = json.loads(result.read_text())
        if len(scan['results']) != 1 or scan['errors']:
            raise RuntimeError('Semgrep did not cleanly detect the fixture')
        (source / 'unsafe.py').write_text('def parse(user_input):\n    return str(user_input)\n')
        run(toolchain / 'bin/semgrep', 'scan', '--config', rule, '--metrics', 'off',
            '--error', '--json', '--output', evidence / 'semgrep-fixed.json', source)
        if json.loads((evidence / 'semgrep-fixed.json').read_text())['results']:
            raise RuntimeError('Semgrep fixed fixture still reported')
        checks.append('Semgrep vulnerable and corrected fixtures, local rule, no metrics')

        infra = evidence / 'infra'
        infra.mkdir()
        (infra / 'Dockerfile').write_text('FROM ubuntu:22.04\nUSER root\nRUN echo hello\n')
        result = evidence / 'trivy.json'
        run(toolchain / 'bin/trivy', 'config', '--format', 'json', '--output', result, infra,
            timeout=180)
        scan = json.loads(result.read_text())
        findings = [f for r in scan.get('Results', []) for f in r.get('Misconfigurations', [])]
        if not findings:
            raise RuntimeError('Trivy did not detect the unsafe Dockerfile')
        checks.append('Trivy real IaC checks and structured findings (not a CVE database scan)')

        packages = evidence / 'packages'
        packages.mkdir()
        (packages / 'package-lock.json').write_text(json.dumps({
            'name': 'vulnerability-fixture', 'version': '1.0.0', 'lockfileVersion': 2,
            'packages': {'': {'name': 'vulnerability-fixture', 'version': '1.0.0',
                              'dependencies': {'lodash': '4.17.15'}},
                         'node_modules/lodash': {'version': '4.17.15'}},
            'dependencies': {'lodash': {'version': '4.17.15'}},
        }))
        result = evidence / 'trivy-packages.json'
        run(toolchain / 'bin/trivy', 'fs', '--scanners', 'vuln', '--format', 'json',
            '--output', result, packages, timeout=240)
        package_scan = json.loads(result.read_text())
        vulnerabilities = [f for r in package_scan.get('Results', [])
                           for f in r.get('Vulnerabilities', []) if f.get('PkgName') == 'lodash']
        if not vulnerabilities:
            raise RuntimeError('Trivy did not report the vulnerable package fixture')
        checks.append('Trivy live vulnerability database and vulnerable lockfile detection')

        (evidence / 'index.html').write_text('<!doctype html><html><head><title>UI probe</title>'
            '</head><body><button onclick="document.querySelector(\'output\').textContent='
            '\'saved\'">Save</button><output>pending</output></body></html>')

        class Handler(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *_):
                pass

        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=evidence))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        url = f'http://127.0.0.1:{server.server_port}'

        def browser(name, *args):
            return run(toolchain / 'bin/playwright-cli', f'-s={name}', *args)

        for name in (session, other):
            opened.append(name)
            browser(name, 'open', url, f'--config={toolchain / "playwright.json"}')
        browser(session, 'click', "getByRole('button', { name: 'Save' })")
        if 'saved' not in browser(session, 'eval', "document.querySelector('output').textContent"):
            raise RuntimeError('browser click did not update the output')
        if 'pending' not in browser(other, 'eval', "document.querySelector('output').textContent"):
            raise RuntimeError('browser sessions leaked state')
        browser(session, 'screenshot', f'--filename={evidence / "ui.png"}')
        browser(session, 'close')
        opened.remove(session)
        if 'UI probe' not in browser(other, 'eval', 'document.title'):
            raise RuntimeError('closing one session affected the other')
        checks.append('Playwright CLI real click, assertion, screenshot, session isolation and scoped close')

        diagram = evidence / 'diagram.html'
        diagram.write_text('<!doctype html><html lang="en"><head><meta charset="UTF-8">'
            '<title>Probe</title></head><body><svg xmlns="http://www.w3.org/2000/svg" '
            'viewBox="0 0 400 120" role="img" aria-labelledby="probe-title probe-desc">'
            '<title id="probe-title">Probe</title><desc id="probe-desc">Input reaches storage.</desc>'
            '<rect x="12" y="12" width="376" height="96" fill="#eeeeee"/>'
            '<text x="32" y="64">Input to storage</text></svg></body></html>')
        scripts = plugin / 'skills/diagram-design/scripts'
        python = toolchain / 'python/bin/python'
        run(python, scripts / 'self_check.py', diagram)
        svg = evidence / 'diagram.svg'
        png = evidence / 'diagram.png'
        run(python, scripts / 'export_svg.py', diagram, svg, '--system-fonts')
        run(python, scripts / 'export_png.py', diagram, png)
        if 'https://' in svg.read_text() or not png.read_bytes().startswith(b'\x89PNG\r\n\x1a\n'):
            raise RuntimeError('diagram export invalid or unexpectedly remote')
        checks.append('bundled diagram self-check, offline SVG and Python Playwright PNG export')

        context = 'not requested'
        if network_context7:
            # Public query only. No code, secrets, authentication or host setup.
            result = run(toolchain / 'bin/ctx7', 'library', 'react', 'useEffect cleanup', '--json')
            data = json.loads(result)
            if not data:
                raise RuntimeError('Context7 returned no libraries')
            library = next((item for item in data if item.get('id') == '/react/react'), None)
            if not library or 'v18.2.0' not in library.get('versions', []):
                raise RuntimeError('the exact Context7 fixture version is not indexed')
            docs = run(toolchain / 'bin/ctx7', 'docs', '/react/react/v18.2.0',
                       'use-subscription useSubscription memoize subscribe', '--json')
            parsed = json.loads(docs)
            snippets = parsed.get('codeSnippets', [])
            if not snippets or 'useSubscription' not in docs or not any(
                    '/blob/v18.2.0/' in snippet.get('codeId', '') for snippet in snippets):
                raise RuntimeError('Context7 returned no matching version-specific docs')
            context = 'live anonymous library lookup and explicitly indexed v18.2.0 docs'
            checks.append('Context7 live lookup and exact indexed-version documentation')
        report = {'passed': True, 'checks': checks, 'context7': context,
                  'evidence_root': str(evidence),
                  'unverified': ['model routing and UI aesthetics', 'live host plugin registration',
                                 'runtime memory and token comparison']}
    except Exception as error:
        report = {'passed': False, 'checks': checks, 'error': str(error), 'evidence_root': str(evidence)}
    finally:
        cleanup = []
        for name in opened:
            try:
                run(toolchain / 'bin/playwright-cli', f'-s={name}', 'close', timeout=20)
            except Exception as error:
                cleanup.append(str(error))
        if server:
            server.shutdown()
            server.server_close()
        if cleanup:
            report['cleanup_errors'] = cleanup
            report['passed'] = False
        report['commands'] = logs
        (evidence / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'commands'}, indent=2))
    return report['passed']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plugin', type=Path, required=True)
    parser.add_argument('--toolchain', type=Path, required=True)
    parser.add_argument('--network-context7', action='store_true')
    args = parser.parse_args()
    sys.exit(0 if verify(args.plugin.resolve(), args.toolchain.resolve(), args.network_context7) else 1)
