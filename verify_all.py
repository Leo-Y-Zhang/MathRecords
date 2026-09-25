#!/usr/bin/env python3
"""Re-check every claim this project makes, from scratch, in one command.

The point is to be able to say "it is complete" and mean something checkable
rather than remembered.  Nothing here trusts a previous run: every certificate
on disk is re-verified by the standalone checker, every audit is re-executed,
and every number quoted in the prose is compared against the JSON the
computation actually wrote.

Exit code 0 means every claim in the repository is currently supported by
evidence on disk.  Anything else means a claim has drifted from its evidence and
the write-up is wrong until it is fixed.

Usage:
    python verify_all.py            # everything
    python verify_all.py --fast     # skip the two slow audits
"""
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))
VDW = os.path.join(ROOT, 'vdw')
EC = os.path.join(ROOT, 'ec')
PY = sys.executable

# Claimed results: sequence -> (targets, published terms, new index, new value,
#                               witness json, refutation json)
CLAIMS = {
    'A217058': ([3, 4],
                [18, 21, 25, 29, 33, 36, 40, 42, 45, 48, 52, 55],
                12, 57, 'probe_n56.json', 'probe_n57.json'),
    'A217005': ([3, 3],
                [9, 14, 17, 20, 21, 24, 25, 28, 31, 33, 35, 37, 39, 42, 44, 46,
                 48, 50, 51],
                19, 52, 'probe_A217005_n51_witness.json',
                'probe_A217005_n52.json'),
    'A217007': ([4, 4],
                [35, 40, 53, 54, 56, 66, 67],
                7, 68, 'probe_A217007_a7_n67_witness.json',
                'probe_A217007_a7_n68.json'),
    'A217059': ([3, 5],
                [22, 32, 43, 44, 50, 55, 61, 65, 70],
                9, 74, 'probe_A217059_a9_n73.json',
                'probe_A217059_a9_n74.json'),
    'A217236': ([4, 5],
                [55, 71, 75, 79],
                4, 84, 'probe_A217236_a4_n83.json',
                'probe_A217236_a4_n84.json'),
}

_fail = []
_pass = []
_skip = []

# Cube depth k of the committed cube-and-conquer certification behind each new
# upper bound: vdw/cube_run_n{value}_j{j}_k{k}/ holds its per-cube records
# (results.jsonl) and its composition certificate (exhaustive_cert.json).
CUBE_DEPTH = {'A217058': 8, 'A217005': 8, 'A217007': 8, 'A217059': 8,
              'A217236': 8}


def check(name, ok, detail='', fail_detail=''):
    """`detail` is context shown either way; `fail_detail` only on failure.

    An earlier version passed the failure explanation as `detail`, so a PASS
    line cheerfully printed 'quoted certificate differs from the computed one'
    underneath the word PASS.
    """
    (_pass if ok else _fail).append(name)
    extra = detail if ok else (fail_detail or detail)
    print(f'  [{"PASS" if ok else "FAIL"}] {name}{("  " + extra) if extra else ""}',
          flush=True)
    return ok


def skip(name, detail=''):
    """A check that was not run because a tool this environment lacks was
    needed, not because anything failed. Counted separately from _pass/_fail
    so a bare clone's summary line shows, in numbers, how much of the gate a
    missing tool actually took out -- rather than that count silently
    vanishing into a section that never runs its checks at all.
    """
    _skip.append(name)
    print(f'  [SKIPPED] {name}{("  " + detail) if detail else ""}', flush=True)


def run(cmd, cwd):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return r.returncode, (r.stdout or '') + (r.stderr or '')


def section(t):
    print(f'\n=== {t} ===', flush=True)


def main():
    fast = '--fast' in sys.argv

    section('standalone checkers self-test')
    rc, out = run([PY, 'verify_certificate.py', '--selftest'], VDW)
    check('vdw verify_certificate --selftest', rc == 0 and 'SELFTEST PASSED' in out)
    # cube_certify.py certifies the per-cube UNSAT obligations behind the
    # headline upper bounds (23,851 DRAT proofs across all five) but was
    # never imported or invoked anywhere in this gate -- so every mutation to
    # its verdict logic (parse_cube's arity check, certify_cube's VERIFIED /
    # NOT_VERIFIED dispatch) survived silently (audit/mutants/SAT_checkers.md,
    # MathRecords, M2-M4). This selftest imports cube_certify directly and
    # calls its real functions -- kissat/drat-trim stand in for the two
    # external tools (not installed here; their own DRAT proof-checking is a
    # separate, explicitly SKIPPED section below), so what is checked is that
    # cube_certify.py itself turns a genuine proof into VERIFIED and a
    # corrupted one into NOT_VERIFIED, not that any particular proof is valid.
    rc, out = run([PY, 'cube_certify.py', '--selftest'], VDW)
    check('vdw cube_certify --selftest (parse_cube + certify_cube verdict '
          'dispatch, real function, corrupted proof REJECTED)',
          rc == 0 and 'SELFTEST PASSED' in out)
    rc, out = run([PY, 'verify_rank.py', '--selftest'], EC)
    check('ec verify_rank --selftest', rc == 0 and 'SELFTEST PASSED' in out)

    section('each claimed term, re-derived from its own evidence files')
    for seq, (targets, published, jnew, value, wf, rf) in CLAIMS.items():
        wp, rp = os.path.join(VDW, wf), os.path.join(VDW, rf)
        if not (os.path.exists(wp) and os.path.exists(rp)):
            check(f'{seq}: evidence files present', False, f'missing {wf} or {rf}')
            continue
        wit, ref = json.load(open(wp)), json.load(open(rp))

        check(f'{seq}: a({jnew}) is the next unpublished index',
              jnew == len(published))
        check(f'{seq}: refutation is UNSAT at n={value}',
              ref['sat'] is False and ref['n'] == value and ref['j'] == jnew
              and ref['targets'] == targets)
        check(f'{seq}: refutation had every cube report',
              'all' in str(ref.get('via', '')) or ref.get('via') == 'probe',
              str(ref.get('via')))
        check(f'{seq}: witness is SAT at n={value-1}',
              wit['sat'] is True and wit['n'] == value - 1 and wit['j'] == jnew
              and wit['targets'] == targets)

        cert = wit.get('certificate', '')
        check(f'{seq}: certificate length is a({jnew})-1 = {value-1}',
              len(cert) == value - 1, f'len={len(cert)}')
        check(f'{seq}: certificate wildcard count within budget',
              cert.count('.') <= jnew, f'{cert.count(".")}/{jnew}')

        rc, out = run([PY, 'verify_certificate.py', cert, str(jnew)]
                      + [str(t) for t in targets], VDW)
        check(f'{seq}: certificate ACCEPTED by standalone verifier',
              rc == 0 and 'ACCEPTED' in out)

        # a wrong value here is the whole risk, so state the deduction explicitly
        check(f'{seq}: SAT at {value-1} and UNSAT at {value} give a({jnew})={value}',
              wit['sat'] is True and ref['sat'] is False
              and ref['n'] == wit['n'] + 1)

    section('elliptic curve rank certificate')
    best = os.path.join(EC, 'ec_search_best.json')
    if os.path.exists(best):
        rc, out = run([PY, 'verify_rank.py', best], EC)
        m = re.search(r'rank E\(Q\) >= (\d+)', out)
        check('ec certificate ACCEPTED by standalone checker',
              rc == 0 and 'ACCEPTED' in out, m.group(0) if m else '')
        d = json.load(open(best))
        b = d.get('best', d)
        v = b.get('verification', {})
        check('ec reported rank equals the verified rank',
              b['rank_lower_bound'] == v.get('rank_verified', -1),
              f"reported {b['rank_lower_bound']}, verified {v.get('rank_verified')}")
    else:
        check('ec certificate present', False)

    # Which terms the evidence actually supports. Computed HERE, above the prose
    # section, because the prose section used to iterate CLAIMS -- every claimed
    # term -- and demand that each be written up as established, certificate and
    # full extended sequence included. That did not merely fail to catch an
    # overstatement in the public write-up: it REQUIRED one. A217059 was blocked
    # from SUBMIT.md for having no completed family gate, while this gate went on
    # insisting PAPER.md and README.md present it as an established result.
    sys.path.insert(0, ROOT)
    import importlib

    import make_submit_pack
    importlib.reload(make_submit_pack)

    ready, blocked = [], []
    for seq, (targets, published, j, value, wf, rf) in CLAIMS.items():
        wit, ref = make_submit_pack.load(wf), make_submit_pack.load(rf)
        xc, _why = make_submit_pack.crosscheck(seq, targets, j, value)
        gate = make_submit_pack.family_gate(seq, targets, published, j)
        entry = (seq, j, value)
        (ready if (wit and ref and xc and xc.get('AGREES') and gate) else blocked).append(entry)
    blocked_seqs = {seq for seq, _j, _v in blocked}

    section('prose matches evidence')
    # A result that is computed but never written up is not "complete", and an
    # earlier version of this harness skipped any sequence absent from the prose
    # -- so an undocumented result passed silently by not being mentioned.
    # Presence is now required, not assumed.
    for doc in ('PAPER.md', 'README.md'):
        p = os.path.join(ROOT, doc)
        if not os.path.exists(p):
            check(f'{doc} present', False)
            continue
        text = open(p, encoding='utf-8').read()
        for seq, (targets, published, jnew, value, wf, rf) in CLAIMS.items():
            if seq in blocked_seqs:
                continue  # handled by the withheld-term checks below
            if not check(f'{doc}: documents {seq}', seq in text):
                continue
            wit = json.load(open(os.path.join(VDW, wf)))
            cert = wit.get('certificate', '')
            check(f'{doc}: {seq} certificate string matches the JSON',
                  bool(cert) and cert in text, '',
                  'quoted certificate differs from the computed one')
            # Require the whole extended sequence, not a loose mention of the
            # value: that catches a stale published list as well as a wrong new
            # term, and does not depend on how the prose happens to phrase it.
            full = ', '.join(str(t) for t in published + [value])
            check(f'{doc}: {seq} shows the full extended sequence ending {value}',
                  full in text, '', 'extended data line missing or stale')

        # A withheld term must NOT be presented as an established result. The
        # extended data line ending in the new value is the specific thing that
        # asserts it, so either the prose omits that line or it carries an
        # explicit marker beside the sequence saying the term is not established.
        for seq, _j, value in blocked:
            published = CLAIMS[seq][1]
            full = ', '.join(str(t) for t in published + [value])
            marked = any(
                w in text for w in ('withheld', 'withdrawn', 'not established', 'NOT established')
            )
            check(f'{doc}: does not present withheld {seq} as established',
                  (full not in text) or marked, '',
                  f'{seq} is blocked (its evidence is incomplete) but this document '
                  f'states its extended sequence as a result with no withheld marker')

        # The reverse must hold once a term's evidence is complete: a leftover
        # withheld marker beside it asserts the opposite of the evidence. This
        # happened -- A217059's gate finally ran and SUBMIT.md was regenerated,
        # but both prose files kept calling the term WITHHELD. Scoped to lines
        # that name the sequence and to the uppercase marker convention these
        # documents use, so running prose may still tell the history in
        # lowercase ("was withheld until the gate completed").
        for seq, _j, value in ready:
            stale = [ln for ln in text.splitlines()
                     if seq in ln and any(w in ln for w in
                        ('WITHHELD', 'not established', 'NOT established'))]
            check(f'{doc}: does not mark established {seq} as withheld',
                  not stale, '',
                  f'a line still carries a withheld marker beside {seq}: '
                  f'"{stale[0][:70] if stale else ""}..."')


    # SUBMIT.md is the file whose contents are actually pasted into OEIS, and
    # until now nothing here opened it. The gate could therefore print "EVERY
    # CLAIM IN THIS REPOSITORY IS SUPPORTED BY EVIDENCE ON DISK" while SUBMIT.md
    # presented a term as ready whose family gate had never finished -- which is
    # exactly what happened to A217059, through 76 consecutive passes. A gate
    # that does not read the artifact cannot vouch for it.
    section('SUBMIT.md agrees with the evidence')
    submit_path = os.path.join(ROOT, 'SUBMIT.md')
    if not os.path.exists(submit_path):
        check('SUBMIT.md exists', False, fail_detail='run make_submit_pack.py')
    else:
        submit_text = open(submit_path, encoding='utf-8').read()

        # Every section heading offering a term to paste must be a term the
        # evidence actually supports.
        offered = set(re.findall(r'^## (A\d+) — a\(\d+\) = \d+', submit_text, re.M))
        unsupported = sorted(offered - {s for s, _, _ in ready})
        check('SUBMIT.md offers no term the evidence does not support',
              not unsupported,
              f'{len(offered)} term(s) offered',
              fail_detail=f'offered without support: {", ".join(unsupported)} — '
                          f'regenerate with make_submit_pack.py')

        for seq, j, value in blocked:
            check(f'SUBMIT.md does not present blocked {seq} a({j})={value} as ready',
                  f'## {seq} — a({j}) = {value}' not in submit_text,
                  'listed as blocked',
                  fail_detail='it is offered for pasting despite missing evidence')

        for seq, j, value in ready:
            check(f'SUBMIT.md carries the section for {seq} a({j})={value}',
                  f'## {seq} — a({j}) = {value}' in submit_text,
                  fail_detail='evidence supports it but the pack is stale — '
                              'run make_submit_pack.py')

    # The five b-files committed at the repository root are the copies anyone
    # actually gets: SUBMIT.md names them to an editor ("b217058.txt (13 rows,
    # 0 to 12) is in this repository if an editor ever asks for one"), and they
    # are the only b-files a clone or a CI runner has at all. Nothing opened
    # them. The staged copies checked below live outside the repository, so that
    # section skips on every machine but the one holding the staging folder --
    # which meant that in practice no b-file content was ever checked anywhere.
    # Measured: rewriting the last row of b217058.txt to "12 58" left the gate
    # at 0 failed, still printing that every claim is supported.
    section('committed b-files match the claims')
    ready_seqs = {seq for seq, _j, _v in ready}
    for seq, (targets, published, jnew, value, wf, rf) in CLAIMS.items():
        bpath = os.path.join(ROOT, f'b{seq[1:]}.txt')
        if not check(f'{seq}: b{seq[1:]}.txt is committed', os.path.exists(bpath),
                     fail_detail=f'missing {bpath}'):
            continue
        rows = [r.split() for r in
                open(bpath, encoding='ascii').read().split('\n') if r.strip()]
        try:
            got = [(int(a), int(b)) for a, b in rows]
        except ValueError:
            check(f'{seq}: b-file rows are "index value" pairs', False,
                  fail_detail=f'unparseable rows in b{seq[1:]}.txt: {rows[:3]}')
            continue

        if seq not in ready_seqs:
            check(f'{seq}: committed b-file does not carry the withheld a({jnew})',
                  not got or got[-1] != (jnew, value), 'withheld term absent',
                  fail_detail=f'{seq} is blocked (its evidence is incomplete) but '
                              f'b{seq[1:]}.txt ends a({jnew})={value}, ready to hand '
                              f'to an editor')
            continue

        want = list(enumerate(published + [value], start=jnew - len(published)))
        check(f'{seq}: b-file rows equal the claimed sequence',
              got == want, f'{len(got)} rows, last a({got[-1][0]})={got[-1][1]}'
              if got else 'empty',
              fail_detail=f'b{seq[1:]}.txt disagrees with CLAIMS: got '
                          f'{got[:3]}...{got[-1:]} want {want[:3]}...{want[-1:]}')

    # The b-file is the DATA that is uploaded to OEIS. The gate checked
    # certificates, prose and SUBMIT.md and never opened one, so the only
    # artifact whose contents literally become the public record was the one
    # thing unverified. Same shape as the SUBMIT.md gap: a chain of checks that
    # stops one link short of the thing that ships.
    #
    # Both directions, because one is not a gate: a READY term's file must exist
    # and match its claim exactly, and a BLOCKED term's file must NOT be sitting
    # there pasteable. The staging folder lives outside the repo, so a clean
    # clone skips this section rather than failing it.
    staging = os.path.join(os.path.expanduser('~'), 'OEIS-upload')
    if not os.path.isdir(staging):
        section('staged b-files (skipped: no staging folder on this machine)')
    else:
        section('staged b-files match the claims')
        ready_seqs = {seq for seq, _j, _v in ready}
        for seq, (targets, published, jnew, value, wf, rf) in CLAIMS.items():
            bpath = os.path.join(staging, f'b{seq[1:]}.txt')
            staged_here = os.path.exists(bpath)

            if seq not in ready_seqs:
                check(f'{seq}: withheld term is NOT staged for upload',
                      not staged_here, 'not staged',
                      fail_detail=f'{bpath} exists but {seq} is blocked - it would be '
                                  f'pasted from a folder that looks ready')
                continue

            if not check(f'{seq}: b-file is staged', staged_here,
                         fail_detail=f'missing {bpath}'):
                continue

            rows = [r.split() for r in
                    open(bpath, encoding='ascii').read().split('\n') if r.strip()]
            got = [(int(a), int(b)) for a, b in rows]
            want = list(enumerate(published + [value], start=jnew - len(published)))
            check(f'{seq}: b-file rows equal the claimed sequence',
                  got == want, f'{len(got)} rows, last a({got[-1][0]})={got[-1][1]}'
                  if got else 'empty',
                  fail_detail=f'b-file disagrees with CLAIMS: got {got[:3]}...{got[-1:]} '
                              f'want {want[:3]}...{want[-1:]}')
            check(f'{seq}: b-file final row is the claimed new term a({jnew})={value}',
                  bool(got) and got[-1] == (jnew, value), '',
                  fail_detail='the uploaded file would not carry the term being claimed')

        # The approval watcher is the one thing that speaks to the operator
        # unprompted, and it does so at the single moment they are most likely to
        # act without re-checking: the instant a term is approved. Its target list
        # is therefore a second place where "what to submit next" is written down,
        # and it drifted -- A217059 was withdrawn from the staging folder and the
        # pack while the watcher kept watching it. Nothing read the two together.
        targets_path = os.path.join(staging, 'watch_targets.json')
        if not os.path.exists(targets_path):
            section('approval watcher targets (skipped: no watch_targets.json)')
        else:
            section('approval watcher targets agree with SUBMIT.md')
            try:
                watch = json.load(open(targets_path, encoding='utf-8'))
            except (ValueError, OSError) as exc:
                watch = None
                check('watch_targets.json parses', False, fail_detail=str(exc))
            if watch is not None:
                blocked_seqs = {seq for seq, _j, _v in blocked}
                watched = {t.get('seq') for t in watch}
                offending = sorted(watched & blocked_seqs)
                check('the watcher tracks no term the pack refuses',
                      not offending, f'{len(watched)} target(s)',
                      fail_detail=f'{", ".join(offending)} is blocked but still in '
                                  f'watch_targets.json - on approval the watcher '
                                  f'would name it as the next thing to submit')
                for t in watch:
                    seq = t.get('seq')
                    claim = CLAIMS.get(seq)
                    check(f'{seq}: watcher target matches the claimed term',
                          claim is not None
                          and (t.get('idx'), t.get('val')) == (claim[2], claim[3]),
                          f"a({t.get('idx')})={t.get('val')}",
                          fail_detail='the watcher would announce approval of a term '
                                      'this repository does not claim')

    # The upper bounds are the half of every result with no self-checking
    # artifact: a colouring proves a lower bound to anyone in milliseconds, but
    # "no colouring exists" is an absence, and until now it rested on a solver
    # saying UNSAT with nothing to replay. drat_certify.py emits a DRAT proof and
    # has drat-trim check it, which shrinks what is trusted to drat-trim plus the
    # encoding audit below -- and the encoding half is audited exhaustively.
    #
    # Symmetry breaking is OFF in those proofs, so the reversal lex-leader
    # argument is not assumed by the thing meant to check it.
    section('DRAT certificate table agrees with the claims')
    sys.path.insert(0, VDW)
    import drat_certify
    importlib.reload(drat_certify)
    for seq, fam in sorted(drat_certify.FAMILIES.items()):
        claim = CLAIMS.get(seq)
        check(f'{seq}: drat_certify published terms match CLAIMS',
              claim is not None and fam['published'] == claim[1]
              and fam['targets'] == claim[0],
              f"{len(fam['published'])} published, targets {fam['targets']}",
              fail_detail='the certifier would certify a different sequence from '
                          'the one this repository claims')

    # Two binaries this repository does not ship. A clean clone and a CI runner
    # both lack them, and neither is a failure: the section skips, loudly.
    ladder = {'A217058': '0-3' if fast else '0-6',
              'A217005': '0-1', 'A217007': '0-1', 'A217236': '0-1',
              'A217059': '0-1'}
    started = False
    for seq, spec in ladder.items():
        rc, out = run([PY, 'drat_certify.py', '--seq', seq, '--ladder', spec,
                       '--json'], VDW)
        if rc == drat_certify.TOOLS_MISSING:
            # Missing tools, not a broken claim -- but silently `break`-ing out
            # here used to make the whole ladder vanish with no trace in the
            # summary line, so a bare clone's "N passed, 0 failed" looked
            # identical whether or not this entire layer ran. List exactly what
            # was not checked, so the gap is a number, not an absence.
            section('DRAT refutations: SKIPPED (needs kissat, drat-trim) '
                    '- see vdw/DRAT.md')
            for s, spec2 in ladder.items():
                for n_val, j_val in drat_certify.rungs_for(s, spec2):
                    skip(f'{s}: a({j_val}) <= {n_val} refutation replay',
                         'needs kissat, drat-trim')
            print('  CI should build both from source per vdw/DRAT.md (there '
                  'is no apt or cargo package for either): drat-trim is one '
                  'file (`cc -O2 -o drat-trim drat-trim.c`); kissat ships its '
                  'own `./configure && make`.')
            break
        if not started:
            section('DRAT refutations replayed under drat-trim')
            started = True
        try:
            recs = json.loads(out)
        except ValueError:
            recs = None
        if not check(f'{seq}: certifier returned results', bool(recs),
                     fail_detail=out.strip()[-300:]):
            continue
        for r in recs:
            # Anything other than the checker's own VERIFIED line fails. A
            # satisfiable instance reports SAT and fails here too, which is the
            # point: it would mean the upper bound itself is false.
            check(f"{seq}: a({r['j']}) <= {r['n']} refutation is machine-checked",
                  r['verdict'] == 'VERIFIED',
                  f"{r['verdict']}, {r.get('proof_mb', 0)} MB proof checked in "
                  f"{r.get('check_s', 0)} s",
                  fail_detail=r.get('detail', r['verdict']))

    # "All five upper bounds are reduced to checked proof objects: 23,851
    # per-cube DRAT proofs in total ... each family with a composition proof"
    # is the headline claim of the README and the paper, and no line of this
    # gate opened the evidence behind it. Measured: marking one of A217058's
    # cubes NOT_VERIFIED in its results.jsonl, deleting another cube's record
    # outright, and setting A217236's composition certificate to FAIL left this
    # gate at 0 failed. Same shape as the SUBMIT.md and b-file gaps above: a
    # chain of checks stopping one link short of the artifact the claim is
    # about. cube_exhaustive.py, the composition argument itself, was run by
    # nothing here either.
    #
    # Most of it needs no solver. cube_exhaustive.py re-walks the whole
    # assignment tree over the RECORDED cube set, in pure Python, against the
    # formula built here, and fails unless every branch is a cube or refuted by
    # a clause of that formula and every cube's record is VERIFIED against it
    # (by its SHA-256). Replaying the composition tail needs drat-trim, and
    # re-proving a cube needs kissat as well; those skip, like the ladder
    # above, when the tools are absent.
    section('cube-level certificates of the five new upper bounds')
    tools, _missing = drat_certify.find_tools()
    have_trim = 'drat_trim' in tools
    have_both = have_trim and 'kissat' in tools
    rederived = {}
    with tempfile.TemporaryDirectory(prefix='verify_all_cubes_') as tmp:
        for seq, (targets, published, jnew, value, wf, rf) in CLAIMS.items():
            k = CUBE_DEPTH[seq]
            run_dir = os.path.join(VDW, f'cube_run_n{value}_j{jnew}_k{k}')
            results = os.path.join(run_dir, 'results.jsonl')
            committed = os.path.join(run_dir, 'exhaustive_cert.json')
            if not check(f'{seq}: cube run n={value} j={jnew} k={k} is committed',
                         os.path.exists(results) and os.path.exists(committed),
                         fail_detail=f'missing {os.path.relpath(results, ROOT)} '
                                     f'or {os.path.relpath(committed, ROOT)}'):
                continue

            # Read strictly. cube_certify.py and cube_exhaustive.py skip a torn
            # line and keep the last record per cube, which is right for
            # resuming a killed run and wrong for committed evidence: a line
            # that does not parse, or a cube recorded twice, is a defect in the
            # record, not something to read past.
            recs, torn = [], 0
            with open(results, encoding='ascii') as fh:
                for ln in fh:
                    if not ln.strip():
                        continue
                    try:
                        rec = json.loads(ln)
                    except ValueError:
                        rec = None
                    if isinstance(rec, dict):
                        recs.append(rec)
                    else:
                        torn += 1
            cubes = [tuple(r.get('cube') or ()) for r in recs]
            not_ok = sum(1 for r in recs if r.get('verdict') != 'VERIFIED')
            dupes = len(cubes) - len(set(cubes))
            check(f'{seq}: all {len(recs)} per-cube refutations recorded '
                  f'VERIFIED, one record per cube',
                  bool(recs) and not torn and not not_ok and not dupes,
                  fail_detail=f'{torn} unparseable line(s), {not_ok} record(s) '
                              f'not VERIFIED, {dupes} duplicate cube(s)')

            fresh_path = os.path.join(tmp, f'{seq}_exhaustive.json')
            cmd = ([PY, 'cube_exhaustive.py', '--n', str(value), '--j', str(jnew),
                    '--targets'] + [str(t) for t in targets]
                   + ['--k', str(k), '--cubes', results, '--out', fresh_path,
                      '--timeout', '600'])
            if not have_trim:
                cmd.append('--no-tail')
            rc, out = run(cmd, VDW)
            try:
                with open(fresh_path, encoding='ascii') as fh:
                    fresh = json.load(fh)
            except (OSError, ValueError):
                fresh = {}
            stats = fresh.get('stats') or {}
            uncovered = fresh.get('counterexamples') or []
            if uncovered:
                why = (f"{len(uncovered)} uncovered prefix(es), first "
                       f"{uncovered[0].get('prefix')}: {uncovered[0].get('why')}")
            elif fresh.get('cube_results_nonverified'):
                why = (f"{fresh['cube_results_nonverified']} cube record(s) not "
                       f"VERIFIED against this formula, "
                       f"{fresh.get('cube_results_foreign_formula')} of them "
                       f"proved against a different formula")
            else:
                why = out.strip()[-300:]
            check(f'{seq}: exhaustiveness re-walked over the recorded cubes '
                  f'(every branch a cube or refuted by the formula, every cube '
                  f'VERIFIED against this formula)',
                  bool(fresh) and not uncovered
                  and fresh.get('cube_results_nonverified') == 0
                  and fresh.get('cube_count') == len(set(cubes)),
                  f"{fresh.get('cube_count')} cubes, "
                  f"{stats.get('dropped_mono_ap')} + {stats.get('dropped_up')} "
                  f"refuted prefixes",
                  fail_detail=why)

            with open(committed, encoding='ascii') as fh:
                cert = json.load(fh)
            keys = ('n', 'j', 'targets', 'k', 'formula', 'cube_count',
                    'cube_set_sha256', 'stats', 'tail_lemmas')
            differ = [key for key in keys if cert.get(key) != fresh.get(key)]
            cert_tail = (cert.get('tail') or {}).get('verdict')
            check(f'{seq}: committed composition certificate is PASS and agrees '
                  f'with the re-walk',
                  bool(fresh) and not differ and cert.get('verdict') == 'PASS'
                  and cert_tail == 'VERIFIED'
                  and cert.get('cube_results_nonverified') == 0,
                  fail_detail=f"verdict {cert.get('verdict')}, tail {cert_tail}, "
                              f"fields that differ from the re-walk: {differ}")

            if fresh.get('formula') and fresh.get('cube_count'):
                rederived[seq] = (fresh['cube_count'], fresh.get('tail_lemmas'),
                                  fresh['formula']['clauses'] + fresh['cube_count'])

            tail = fresh.get('tail') or {}
            if have_trim:
                check(f'{seq}: composition proof replayed under drat-trim',
                      tail.get('verdict') == 'VERIFIED',
                      f"{tail.get('tail_lemmas')} lemmas over "
                      f"{tail.get('fprime_clauses')} F' clauses",
                      fail_detail=str(tail.get('detail') or out.strip()[-300:]))
            else:
                skip(f'{seq}: composition proof replayed under drat-trim',
                     'needs drat-trim')

            # One recorded cube per family is re-proved from scratch by kissat
            # and replayed under drat-trim, through cube_certify.py itself. Not
            # a replay of the evidence -- that is some 180 CPU-hours -- but a
            # check that the recorded pipeline still turns this formula plus a
            # recorded cube into a proof drat-trim accepts. Chosen by rule, not
            # by hand: the cheapest recorded cube spending at most two
            # wildcards. Spent wildcards are what make a cube easy, so this
            # stays in the hard part of the split while keeping the proof to
            # megabytes and the run to seconds.
            if fast:
                continue
            light = [r for r in recs if isinstance(r.get('cube'), list)
                     and r['cube'].count(0) <= 2
                     and 'solve_s' in r and 'check_s' in r]
            if not light:
                check(f'{seq}: a recorded cube re-proved by kissat and replayed '
                      f'under drat-trim', False,
                      fail_detail='no recorded cube spends at most two wildcards')
                continue
            pick = min(light, key=lambda r: (r['solve_s'] + r['check_s'],
                                             r['cube']))
            name = (f"{seq}: recorded cube {''.join(map(str, pick['cube']))} "
                    f"re-proved by kissat and replayed under drat-trim")
            if not have_both:
                skip(name, 'needs kissat, drat-trim')
                continue
            cube_dir = os.path.join(tmp, f'{seq}_cube')
            rc, out = run([PY, 'cube_certify.py', '--n', str(value),
                           '--j', str(jnew), '--targets']
                          + [str(t) for t in targets]
                          + ['--k', str(k), '--workers', '1', '--timeout', '1200',
                             '--only', ','.join(map(str, pick['cube'])),
                             '--run-dir', cube_dir], VDW)
            try:
                with open(os.path.join(cube_dir, 'results.jsonl'),
                          encoding='ascii') as fh:
                    new = json.loads([ln for ln in fh if ln.strip()][-1])
            except (OSError, ValueError, IndexError):
                new = {}
            check(name,
                  rc == 0 and new.get('verdict') == 'VERIFIED'
                  and new.get('formula_sha256') == pick.get('formula_sha256'),
                  f"{new.get('proof_bytes', 0) / 1e6:.1f} MB proof, solve "
                  f"{new.get('solve_s')} s, check {new.get('check_s')} s",
                  fail_detail=f"verdict {new.get('verdict')}: "
                              f"{out.strip()[-300:]}")

    # The prose quotes these counts. Checked against the re-walk above rather
    # than against the committed certificates, so a stale certificate cannot
    # vouch for a stale sentence.
    if len(rederived) == len(CLAIMS):
        total = sum(c for c, _lemmas, _fprime in rederived.values())
        with open(os.path.join(ROOT, 'README.md'), encoding='utf-8') as fh:
            readme = fh.read()
        check(f'README.md: quotes the {total:,} per-cube proofs on disk',
              f'{total:,} per-cube DRAT proofs' in readme)

        def tex(x):
            return f'{x:,}'.replace(',', '{,}')
        with open(os.path.join(ROOT, 'paper', 'main.tex'), encoding='utf-8') as fh:
            paper = fh.read()
        check(f'paper/main.tex: quotes the {total:,} per-cube proofs on disk',
              f'${tex(total)}$ per-cube DRAT proofs' in paper)
        for seq, (ncubes, lemmas, fprime) in rederived.items():
            row = f'${tex(ncubes)}$ & ${tex(lemmas)}$ & ${tex(fprime)}$'
            check(f'paper/main.tex: {seq} row of the certification table '
                  f'matches the re-walk',
                  any(row in ln for ln in paper.splitlines()
                      if f'\\seq{{{seq}}} &' in ln),
                  fail_detail=f'no \\seq{{{seq}}} row ending {row}')
    else:
        check('README.md and paper/main.tex cube counts', False,
              fail_detail='not checked: a cube run above could not be re-walked')

    if not fast:
        section('audits re-executed (slow)')
        rc, out = run([PY, 'encoding_audit.py'], VDW)
        check('encoding audit: CNF equals the definition',
              # matched by pattern, not by a hardcoded count: pinning the number
              # here means adding a case to the audit fails this check instead of
              # strengthening it, which is backwards.
              rc == 0 and re.search(r'all \d+ cases pass', out) is not None,
              re.search(r'all \d+ cases pass', out).group(0) if
              re.search(r'all \d+ cases pass', out) else '')
        rc, out = run([PY, 'scale_test.py'], VDW)
        check('scale test: wildcard budget correct at n=55..58, j=12',
              rc == 0 and 'SCALE TEST PASSED' in out)

    skipped = f', {len(_skip)} skipped (needs kissat, drat-trim)' if _skip else ''
    print(f'\n{len(_pass)} passed, {len(_fail)} failed{skipped}')
    if _fail:
        print('\nFAILED:')
        for f in _fail:
            print('  -', f)
        return 1
    print('\nEVERY CLAIM IN THIS REPOSITORY IS SUPPORTED BY EVIDENCE ON DISK.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
