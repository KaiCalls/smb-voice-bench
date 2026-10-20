"""Frozen seven-case suite. Harness expectations are never an agent input."""
from importlib.resources import files
from .canonical import digest, parse, Invalid
from .contracts import validate

IDS = ("booking-and-confirmation", "duplicate-write-prevention", "unknown-write-reconciliation",
       "partial-confirmation-failure", "slow-lookup", "interrupt-and-correct-context", "no-consent-no-write")

def load(scenario_id):
    if scenario_id not in IDS:
        raise Invalid("unknown installed scenario")
    return validate(parse(files("smb_voice_bench").joinpath("scenarios/booking/" + scenario_id + ".json").read_bytes()), "scenario")

def suite_identity():
    suite=validate(parse(files('smb_voice_bench').joinpath('scenarios/suite.json').read_bytes()),'suite')
    if {entry['scenario_id'] for entry in suite['scenarios']}!=set(IDS): raise Invalid('suite inventory differs from frozen seven cases')
    for entry in suite['scenarios']:
        scenario=load(entry['scenario_id'])
        if digest(scenario)!=entry['sha256'] or scenario['revision']!=entry['revision']: raise Invalid('frozen scenario hash differs')
    return digest(suite)

def catalog():
    return [{"scenario_id": key, "outcome": load(key)["outcome"], "coverage": ["scripted reference", "text contract"],
             "audio": "external evidence and human review required"} for key in IDS]

def agent_context(scenario):
    return {key: scenario[key] for key in ("business_context", "synthetic_clock", "timezone")}
