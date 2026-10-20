#!/usr/bin/env python3
"""Exercise every offline CLI command from an installed wheel, outside the checkout."""
import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import resource
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    denied = {'network': 0, 'credential_reads': 0}

    def audit(event, values):
        if event.startswith('socket.'):
            denied['network'] += 1
            raise RuntimeError('offline acceptance attempted network access')
        if event == 'open' and isinstance(values[0], (str, bytes, os.PathLike)):
            name = Path(os.fsdecode(values[0])).name.lower()
            if name in ('credentials', '.netrc', 'id_rsa', 'id_ed25519') or name == '.env' or name.startswith('.env.'):
                denied['credential_reads'] += 1
                raise RuntimeError('offline acceptance attempted a credential-file read')

    sys.addaudithook(audit)
    import smb_voice_bench
    from smb_voice_bench.canonical import atomic_output, digest, read_json, write_json
    from smb_voice_bench.cli import main as cli
    from smb_voice_bench.import_runs import read_bundle
    from smb_voice_bench.scenarios import IDS

    installed = Path(smb_voice_bench.__file__).resolve().parent
    checkout = Path(__file__).resolve().parents[1]
    if installed.is_relative_to(checkout / 'src'):
        raise RuntimeError('use an installed wheel without PYTHONPATH, outside the source checkout')
    started = time.monotonic()
    commands = []
    with atomic_output(args.output) as output:
        def run(expected, *arguments):
            stdout, stderr = io.StringIO(), io.StringIO()
            before = time.monotonic()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = cli([*map(str, arguments), '--json'])
            if code != expected:
                raise AssertionError('unexpected exit for ' + str(arguments[0]) + ': ' + stderr.getvalue())
            value = json.loads(stdout.getvalue()) if stdout.getvalue() else None
            commands.append(dict(command=str(arguments[0]), expected_exit=expected, actual_exit=code,
                                 elapsed_seconds=round(time.monotonic() - before, 3)))
            return value

        run(0, 'doctor')
        assert len(run(0, 'catalog')['scenarios']) == 7
        demo = run(0, 'demo', '--output', output / 'demo')
        assert demo['expected_failure_detected'] and demo['corrected_functional_pass']
        (output / 'sources').mkdir(mode=0o700)
        (output / 'evaluations').mkdir(mode=0o700)
        arms = {'baseline': [], 'candidate': []}
        outcomes = []
        for scenario in IDS:
            for arm, agent, expected in [('baseline', 'reference-bad', 1), ('candidate', 'reference-good', 0)]:
                source = output / 'sources' / (scenario + '_' + agent)
                target = output / 'evaluations' / source.name
                run(0, 'simulate', '--scenario', scenario, '--agent', agent, '--output', source)
                run(0, 'validate', '--input', source)
                result = run(expected, 'evaluate', '--input', source, '--output', target)
                arms[arm].append(source.relative_to(output).as_posix())
                outcomes.append(dict(scenario_id=scenario, agent=agent, dimensions=result['dimensions']))
        for arm, paths in arms.items():
            write_json(output, arm + '.json', dict(kind='run_list', schema_version='0.1.0', paths=paths))
        comparison = run(0, 'compare', '--baseline', output / 'baseline.json', '--candidate', output / 'candidate.json',
                         '--change', 'Correct all seven deliberately faulty reference controls.', '--output', output / 'comparison')
        assert comparison['assessment'] == 'eligible_for_review'
        run(0, 'report', '--input', output / 'comparison', '--output', output / 'regenerated-comparison')
        before = read_json(output / 'comparison', 'comparison.json')
        assert before == read_json(output / 'regenerated-comparison', 'comparison.json')
        source = output / arms['candidate'][0]
        hashes = {p.name: digest(p.read_bytes()) for p in source.iterdir()}
        run(0, 'import', '--input', source, '--output', output / 'imported')
        assert hashes == {p.name: digest(p.read_bytes()) for p in source.iterdir()}
        run(0, 'review-template', '--input', source, '--output', output / 'unfilled-review.json')
        review = read_json(output, 'unfilled-review.json')
        assert review['status'] == 'draft' and all(v is None for v in review['ratings'].values())
        run(2, 'evaluate', '--input', source, '--scope', 'audio-release', '--output', output / 'audio-insufficient')
        first_evaluation = output / 'evaluations' / source.name
        run(0, 'report', '--input', first_evaluation, '--output', output / 'regenerated-run')
        assert read_json(first_evaluation, 'result.json') == read_json(output / 'regenerated-run', 'result.json')
        # Destructive controls touch only new copies, never the original evidence.
        run(0, 'import', '--input', source, '--output', output / 'missing-copy')
        (output / 'missing-copy/events.jsonl').unlink()
        run(2, 'validate', '--input', output / 'missing-copy')
        run(2, 'evaluate', '--input', output / 'missing-copy', '--output', output / 'missing-evaluation')
        run(0, 'import', '--input', source, '--output', output / 'corrupt-copy')
        (output / 'corrupt-copy/events.jsonl').write_bytes(b'{}\n')
        run(3, 'validate', '--input', output / 'corrupt-copy')
        run(3, 'demo', '--output', output / 'demo')
        assert read_bundle(source).missing == []
        assert denied == {'network': 0, 'credential_reads': 0}
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        peak_bytes = peak if sys.platform == 'darwin' else peak * 1024
        receipt = dict(kind='installed_acceptance_receipt', schema_version='0.1.0',
                       version=smb_voice_bench.__version__, python=sys.version.split()[0],
                       installed_package=str(installed), package_bytes=sum(p.stat().st_size for p in installed.rglob('*') if p.is_file()),
                       elapsed_seconds=round(time.monotonic() - started, 3), peak_rss_bytes=peak_bytes,
                       denied_access_attempts=denied, commands=commands, outcomes=outcomes,
                       claim='Offline scripted reference software checks; no real-agent or speech-quality claim.')
        write_json(output, 'acceptance.json', receipt)
    print(json.dumps({k: receipt[k] for k in ('version', 'python', 'elapsed_seconds', 'peak_rss_bytes', 'denied_access_attempts')}))


if __name__ == '__main__':
    main()
