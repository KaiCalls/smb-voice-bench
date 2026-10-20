"""Export captured external evidence without dispatching tools or inventing outcomes."""
from .canonical import (
    Invalid, MAX_EVENT, MAX_EVENTS, MAX_EVENTS_BYTES, MAX_JSON, MAX_RUN, MAX_WAV,
    atomic_output, canonical, digest, parse, write_bytes,
)
from .contracts import validate
from .evaluate import POLICY_ID
from .import_runs import read_bundle
from .reference_agents import implementation_identity
from .scenarios import load, suite_identity


def _document(value, kind):
    raw = canonical(value)
    if len(raw) + 1 > MAX_JSON:
        raise Invalid('export document exceeds size limit')
    frozen = parse(raw)
    validate(frozen, kind)
    return frozen, raw + b'\n'


def write_external_bundle(
    destination, *, scenario, configuration, state, events, execution_mode,
    conditions, sandbox_sha256, started_at, ended_at, completion, seed=0,
    cost=None, audio=None, measurement=None,
):
    """Write a new private directory from an external harness's captured snapshots.

    Required metadata describes the actual capture, including its fault/sandbox
    implementation hash and sanitized conditions. Cost defaults to unknown.
    Audio is optional immutable original WAV bytes; absence never changes mode.
    This function never runs an agent, closes a capability, repairs audit gaps,
    fetches media, converts audio, fills reviews or evaluates a result.

    Cross-file contradictions leave only an explicitly incomplete staging
    directory. Structurally valid but incomplete evidence is preserved as such.
    The return value is the written manifest; use read_bundle for missing details.
    """
    scenario, scenario_raw = _document(scenario, 'scenario')
    configuration, config_raw = _document(configuration, 'configuration')
    state, state_raw = _document(state, 'state')
    if execution_mode not in ('text', 'audio') or configuration['agent_kind'] != 'external':
        raise Invalid('external export requires external configuration and text/audio mode')
    if digest(scenario) != digest(load(scenario['scenario_id'])):
        raise Invalid('external export requires an unchanged installed scenario')
    if type(conditions) is not dict or not conditions:
        raise Invalid('export requires explicit sanitized conditions')
    # Snapshot metadata before filesystem writes; later caller edits cannot change it.
    conditions = parse(canonical(conditions))
    if type(events) is not list or len(events) > MAX_EVENTS:
        raise Invalid('export requires a bounded captured event list')
    lines = []
    event_bytes = 0
    for event in events:
        raw = canonical(event)
        if len(raw) > MAX_EVENT:
            raise Invalid('export event exceeds size limit')
        captured = validate(parse(raw), 'event')
        if (captured['type'] == 'speech.segment'
                and captured['payload']['transcript_origin'] == 'scripted_reference'):
            raise Invalid('scripted reference speech cannot be exported as external capture')
        event_bytes += len(raw) + 1
        if event_bytes > MAX_EVENTS_BYTES:
            raise Invalid('export event stream exceeds size limit')
        lines.append(raw + b'\n')
    files = [
        ('scenario', 'scenario.json', 'scenario', scenario_raw),
        ('configuration', 'configuration.json', 'configuration', config_raw),
        ('state', 'sandbox-state.json', 'state', state_raw),
        ('events', 'events.jsonl', 'events', b''.join(lines)),
    ]
    if audio is not None:
        if execution_mode != 'audio' or type(audio) is not bytes or len(audio) > MAX_WAV:
            raise Invalid('original audio requires audio mode and bounded bytes')
        files.append(('audio', 'original.wav', 'audio', audio))
    if measurement is not None:
        if execution_mode != 'audio':
            raise Invalid('audio measurement requires audio mode')
        measurement, raw = _document(measurement, 'measurement')
        if audio is not None and measurement['audio_sha256'] != digest(audio):
            raise Invalid('measurement does not bind the supplied original audio')
        files.append(('measurement', 'measurement.json', 'measurement', raw))
    manifest = dict(
        kind='manifest', schema_version='0.1.0', run_id=state['run_id'],
        journey_id=state['journey_id'], scenario_id=scenario['scenario_id'],
        execution_mode=execution_mode, evidence_origin='external_self_attested',
        candidate_id=configuration['candidate_id'], seed=seed,
        started_at=started_at, ended_at=ended_at, completion=completion,
        identities=dict(
            scenario=digest(scenario), suite=suite_identity(),
            configuration=digest(configuration), sandbox=sandbox_sha256,
            evaluator=implementation_identity('evaluate'),
            conditions=digest(conditions), policy=digest(POLICY_ID),
        ),
        artifacts=[dict(artifact_id=aid, path=name, artifact_kind=kind,
                        bytes=len(raw), sha256=digest(raw))
                   for aid, name, kind, raw in files],
        cost=cost if cost is not None else dict(
            completeness='unknown', components=[], total_observed_usd=None),
        extensions={'bench:conditions': conditions,
                    'bench:writer_sha256': implementation_identity('bundle_writer')},
    )
    manifest, manifest_raw = _document(manifest, 'manifest')
    if sum(len(raw) for _, _, _, raw in files) + len(manifest_raw) > MAX_RUN:
        raise Invalid('export exceeds run size limit')
    with atomic_output(destination) as output:
        for _, name, _, raw in files:
            write_bytes(output, name, raw)
        write_bytes(output, 'manifest.json', manifest_raw)
        # Reuse all importer integrity checks before publishing the final directory.
        # Missing audio/receipts stay missing; validation never synthesizes them.
        read_bundle(output)
    return manifest
