"""Closed local Draft 2020-12 registry, plus document semantics."""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
import re
from importlib.resources import files
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from jsonschema import Draft202012Validator, FormatChecker
from .canonical import Invalid, canonical, parse, relative, MAX_EXTENSIONS

SCHEMA = parse(files("smb_voice_bench").joinpath("schemas/contracts.schema.json").read_bytes())
# The bundled registry uses only fragment references. Reject any accidental expansion.
def _local_refs(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "$ref" and not item.startswith("#/$defs/"):
                raise Invalid("nonlocal schema reference")
            _local_refs(item)
    elif isinstance(value, list):
        for item in value:
            _local_refs(item)
_local_refs(SCHEMA)
Draft202012Validator.check_schema(SCHEMA)
FORMATS=FormatChecker()
def timestamp_key(value):
    """Compare exact fractional seconds consistently on Python 3.10 and later."""
    if not isinstance(value,str):raise ValueError('timestamp must be text')
    match=re.fullmatch(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d+))?(Z|[+-]\d{2}:\d{2})',value)
    if not match:raise ValueError('invalid timestamp')
    whole,fraction,zone=match.groups()
    return (datetime.fromisoformat(whole+zone.replace('Z','+00:00')),Decimal('0.'+(fraction or '0')))

@FORMATS.checks('date-time')
def timestamp(value):
    try:return timestamp_key(value)[0].utcoffset() is not None
    except ValueError:return False

VALIDATORS = {key: Draft202012Validator({"$ref": "#/$defs/" + key, "$defs": SCHEMA["$defs"]},
               format_checker=FORMATS) for key in SCHEMA["$defs"]}

def validate(value, kind=None):
    kind = kind or (value.get("kind") if isinstance(value, dict) else None)
    if kind not in VALIDATORS:
        raise Invalid("unknown document kind")
    if next(VALIDATORS[kind].iter_errors(value), None) is not None:
        raise Invalid("document violates " + kind + " contract")
    canonical(value)
    if isinstance(value, dict):
        if len(canonical(value.get("extensions", {}))) > MAX_EXTENSIONS:
            raise Invalid("extensions exceed limit")
        if kind == "tool_request" and value["tool"] == "create_booking" and any(not value["args"][k].strip() for k in ("caller_name","service")):
            raise Invalid("live create requires nonblank intake")
        if kind == "artifact":
            relative(value["path"])
        if kind in ("run_list", "review_list"):
            for path in value["paths"]:
                relative(path)
        if kind == 'manifest':
            import math
            costs=value['cost'];total=costs['total_observed_usd'];observed=sum(x['observed_usd'] for x in costs['components'])
            if total is not None and not math.isclose(total,observed,abs_tol=1e-9): raise Invalid('cost total differs from observed components')
            if costs['completeness']=='complete' and total is None: raise Invalid('complete costs require a known total')
            if costs['completeness']=='not_applicable' and (costs['components'] or total is not None): raise Invalid('inapplicable costs cannot contain charges')
        if kind == "manifest":
            if timestamp_key(value["ended_at"]) < timestamp_key(value["started_at"]):
                raise Invalid("run end precedes start")
            for artifact in value["artifacts"]:
                validate(artifact, "artifact")
        if kind == "scenario":
            ids = [x["check_id"] for x in value["assertions"]]
            turns = [x["turn_id"] for x in value["caller_turns"]]
            slots = [x["slot_id"] for x in value["business_context"]["slots"]]
            if len(ids) != len(set(ids)) or len(turns) != len(set(turns)) or len(slots) != len(set(slots)):
                raise Invalid("duplicate scenario IDs")
            try:
                zone = ZoneInfo(value["timezone"])
            except ZoneInfoNotFoundError as exc:
                raise Invalid("unsupported timezone") from exc
            for slot in value["business_context"]["slots"]:
                instant = datetime.fromisoformat(slot["starts_at"])
                if instant.utcoffset() != instant.astimezone(zone).utcoffset():
                    raise Invalid("slot offset disagrees with timezone")
            for permission in value["permissions"]:
                if permission["turn_id"] not in turns or permission["slot_id"] not in slots + [None]:
                    raise Invalid("unknown permission target")
        if kind == "event":
            payload = value["payload"]
            if value["type"] == "speech.segment" and payload["end_ms"] < payload["start_ms"]:
                raise Invalid("negative speech span")
    return value
