"""Reproduce the targeted mutation experiment in disposable repository copies.

Run: python tests/mutation_check.py --jobs 4
Only the copies are mutated. Before = the existing full verify_all.py gate;
after = that same result plus the new pytest suite. External DRAT tools are
used only if already installed, exactly as in the normal gate.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]

# (ID, module, unique old text, replacement). Deliberate, reviewable mutations
# of decisions and boundary conditions; no syntax-error mutants.
MUTANTS = [
    ('C01', 'vdw/verify_certificate.py', 'if dots > j:', 'if dots >= j:'),
    ('C02', 'vdw/verify_certificate.py', 'if bad:', 'if False:'),
    ('C03', 'vdw/verify_certificate.py', 'if a + (t - 1) * d > n:', 'if a + (t - 1) * d >= n:'),
    ('C04', 'vdw/verify_certificate.py', 'in ps for m in range(t))', 'in ps for m in range(t - 1))'),
    ('C05', 'vdw/verify_certificate.py', 'for c, t in enumerate(targets, start=1):\n        pos =', 'for c, t in enumerate(targets, start=0):\n        pos ='),
    ('C06', 'vdw/verify_certificate.py', 'return problems, dots', 'return problems, dots + 1'),
    ('V01', 'vdw/vdw4.py', 'if wild > j:', 'if wild >= j:'),
    ('V02', 'vdw/vdw4.py', 'if all((a + m * d) in ps for m in range(t)):', 'if False:'),
    ('V03', 'vdw/vdw4.py', 'range(1, (n - 1) // (t - 1) + 1)', 'range(1, (n - 1) // (t - 1))'),
    ('V04', 'vdw/vdw4.py', 'cnf.append([v(i, c) for c in range(r + 1)])', 'cnf.append([])'),
    ('V05', 'vdw/vdw4.py', 'cnf.append([-v(i, c) for i in ap])', 'cnf.append([v(i, c) for i in ap])'),
    ('V06', 'vdw/vdw4.py', 'if colour_sym and positions != list(range(1, k + 1)):', 'if colour_sym or positions != list(range(1, k + 1)):'),
    ('V07', 'vdw/vdw4.py', 'if asg.count(0) > j:', 'if asg.count(0) >= j:'),
    ('V08', 'vdw/vdw4.py', 'if any(all(asg[m] == c for m in ap) for c, ap in within):', 'if False:'),
    ('V09', 'vdw/vdw4.py', 'lo = (n - k) // 2 + 1', 'lo = (n - k) // 2'),
    ('V10', 'vdw/vdw4.py', 'm = set(l for l in model if l > 0)', 'm = set(l for l in model if l < 0)'),
    ('V11', 'vdw/vdw4.py', 'if not ok or _has_mono_ap(pre, targets):', 'if not ok and _has_mono_ap(pre, targets):'),
    ('V12', 'vdw/vdw4.py', 'if done != len(tasks):', 'if done == len(tasks):'),
    ('V13', 'vdw/vdw4.py', 'if res is not None:', 'if res is None:'),
    ('V14', 'vdw/vdw4.py', 'res = f.result()', 'res = None'),
    ('V15', 'vdw/vdw4.py', "if bad:\n        return False, wild, ('colour", "if False:\n        return False, wild, ('colour"),
    ('E01', 'vdw/cube_exhaustive.py', 'if assign.get(var, val) != val:', 'if assign.get(var, val) == val:'),
    ('E02', 'vdw/cube_exhaustive.py', 'if ci is None:', 'if ci is not None:'),
    ('E03', 'vdw/cube_exhaustive.py', 'if unassigned == 0:', 'if unassigned == 1:'),
    ('E04', 'vdw/cube_exhaustive.py', "counterexamples.append({'prefix': list(p), 'why': why_direct_failed})", 'return False'),
    ('E05', 'vdw/cube_exhaustive.py', "and r.get('formula_sha256') != expect_sha))", 'and False))'),
    ('E06', 'vdw/cube_exhaustive.py', "r.get('verdict') != 'VERIFIED'", "r.get('verdict') == 'VERIFIED'"),
    ('E07', 'vdw/cube_exhaustive.py', "elif 's VERIFIED' in status:", "elif 's VERIFIED' in out:"),
    ('E08', 'vdw/cube_exhaustive.py', 'if ci is None:', 'if False:'),
    ('D01', 'vdw/drat_certify.py', 'if solve.returncode == 10:', 'if solve.returncode != 10:'),
    ('D02', 'vdw/drat_certify.py', 'if solve.returncode != 20:', 'if solve.returncode == 20:'),
    ('D03', 'vdw/drat_certify.py', "elif 's VERIFIED' in status:", "elif 's VERIFIED' in out:"),
    ('D04', 'vdw/drat_certify.py', "rec['verdict'] = 'NOT_VERIFIED'", "rec['verdict'] = 'VERIFIED'"),
    ('D05', 'vdw/drat_certify.py', "fh.write(f'p cnf {nvars} {len(cnf)}\\n')", "fh.write(f'p cnf {nvars} {len(cnf) + 1}\\n')"),
    ('P01', 'vdw/cube_certify.py', 'if len(parts) != k:', 'if len(parts) == k:'),
    ('P02', 'vdw/cube_certify.py', 'if solve.returncode == 10:', 'if solve.returncode != 10:'),
    ('P03', 'vdw/cube_certify.py', 'if solve.returncode != 20:', 'if solve.returncode == 20:'),
    ('P04', 'vdw/cube_certify.py', "elif 's VERIFIED' in status:", "elif 's VERIFIED' in out:"),
    ('P05', 'vdw/cube_certify.py', 'if truncate:', 'if False:'),
    ('P06', 'vdw/cube_certify.py', "rec['proof_sha256'] = h.hexdigest()", "rec['proof_sha256'] = sha"),
    ('R01', 'ec/verify_rank.py', 'if C.disc == 0:', 'if C.disc != 0:'),
    ('R02', 'ec/verify_rank.py', 'if not C.on(P):', 'if C.on(P):'),
    ('R03', 'ec/verify_rank.py', 'if hh <= floor or', 'if hh < floor or'),
    ('R04', 'ec/verify_rank.py', 'hl / hh >= decay_tol', 'hl / hh > decay_tol'),
    ('R05', 'ec/verify_rank.py', 'if nh <= floor:', 'if nh < floor:'),
    ('R06', 'ec/verify_rank.py', 'elif decay >= decay_tol:', 'elif decay > decay_tol:'),
    ('R07', 'ec/verify_rank.py', 'if rel:', 'if False:'),
    ('R08', 'ec/verify_rank.py', 'd = -d', 'd = d'),
    ('S01', 'make_submit_pack.py', "if xc.get('j') != j:", 'if False:'),
    ('S02', 'make_submit_pack.py', "if list(xc.get('targets') or []) != list(targets):", 'if False:'),
    ('S03', 'make_submit_pack.py', "if int(xc.get('claim', -1)) != int(value):", 'if False:'),
    ('S04', 'make_submit_pack.py', "and rec.get('PASS') and rec.get('sat_at_w_minus_1')", "or rec.get('PASS') and rec.get('sat_at_w_minus_1')"),
    ('S05', 'make_submit_pack.py', 'if sat and unsat:', 'if sat or unsat:'),
    ('S06', 'make_submit_pack.py', "and rec.get('witness_verified'):", 'and True:'),
]


def run(command, directory, log, timeout=240):
    started = time.monotonic()
    try:
        result = subprocess.run(command, cwd=directory, capture_output=True,
                                text=True, timeout=timeout)
        code, output = result.returncode, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        # A timeout is unresolved, never misreported as a killed mutant.
        code, output = None, 'TIMEOUT'
    output = output.replace(str(directory), '.').replace(str(ROOT), '.')
    log.write_text(output, encoding='utf-8')
    return {'returncode': code, 'seconds': round(time.monotonic() - started, 2)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jobs', type=int, default=1)
    parser.add_argument('--only', nargs='+', help='rerun selected mutant IDs')
    parser.add_argument('--results', default='tests/mutation_results.json')
    args = parser.parse_args()
    mutants = [m for m in MUTANTS if not args.only or m[0] in args.only]
    if args.only and set(args.only) != {m[0] for m in mutants}:
        parser.error('unknown mutant ID')
    for ident, module, old, new in mutants:
        source = (ROOT / module).read_text(encoding='utf-8')
        if source.count(old) != 1:
            raise ValueError(f'{ident}: expected one mutation site')
        compile(source.replace(old, new), module, 'exec')
    output = ROOT / 'tests' / '.mutation-output'
    output.mkdir(exist_ok=True)
    gate = [sys.executable, 'verify_all.py']
    pytest = [sys.executable, '-m', 'pytest', '-q']
    baseline = {
        'gate': run(gate, ROOT, output / 'baseline-gate.log'),
        'pytest': run(pytest, ROOT, output / 'baseline-pytest.log'),
    }
    if any(r['returncode'] != 0 for r in baseline.values()):
        raise SystemExit('Unmutated baseline failed; inspect tests/.mutation-output')

    def measure(item, phase):
        ident, module, old, new = item
        with tempfile.TemporaryDirectory(prefix='.mutation-', dir=ROOT) as temporary:
            shadow = Path(temporary) / 'repo'
            shutil.copytree(ROOT, shadow, ignore=shutil.ignore_patterns(
                '.git', '.venv', '__pycache__', '.pytest_cache', '.mutation-*',
                '.mutation-output', '*.log'))
            path = shadow / module
            source = path.read_text(encoding='utf-8')
            if source.count(old) != 1:
                raise ValueError(f'{ident}: expected one mutation site')
            mutated = source.replace(old, new)
            compile(mutated, module, 'exec')
            path.write_text(mutated, encoding='utf-8')
            result = run(gate if phase == 'before' else pytest, shadow,
                         output / f'{ident}-{phase}.log')
        print(f'{phase} {ident}: {result["returncode"]}', flush=True)
        return result

    results = []
    with ThreadPoolExecutor(max_workers=args.jobs) as executor:
        for item, before in zip(mutants, executor.map(
                lambda item: measure(item, 'before'), mutants)):
            ident, module, old, new = item
            source = (ROOT / module).read_text(encoding='utf-8')
            results.append({'id': ident, 'module': module,
                            'line': source[:source.index(old)].count('\n') + 1,
                            'old': old, 'new': new, 'before': before})
        (output / 'before.json').write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')
        for record, after in zip(results, executor.map(
                lambda item: measure(item, 'after'), mutants)):
            record['after_pytest'] = after
            log = (output / f'{record["id"]}-after.log').read_text(encoding='utf-8')
            record['killing_tests'] = [line[7:].split(' - ', 1)[0]
                                       for line in log.splitlines()
                                       if line.startswith('FAILED tests/')]
            record['killed_before'] = record['before']['returncode'] not in (None, 0)
            record['killed_after'] = record['killed_before'] or after['returncode'] not in (None, 0)
    report = {'gate_command': 'python verify_all.py', 'test_command': 'python -m pytest -q',
              'baseline': baseline, 'mutants': results}
    (ROOT / args.results).write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(f'Tried {len(results)}; killed before {sum(r["killed_before"] for r in results)}; '
          f'killed after {sum(r["killed_after"] for r in results)}')
    if any(r['before']['returncode'] is None or r['after_pytest']['returncode'] is None
           for r in results):
        raise SystemExit('Unresolved timeouts; inspect logs')
    return 0


if __name__ == '__main__':
    sys.exit(main())
