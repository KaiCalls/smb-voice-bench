#!/usr/bin/env python3
"""
Python consumption example for smb-voice-bench.

The fixtures are language-neutral JSON, so any ecosystem can consume them — this
is the drop-in for Python harnesses (ServiceNow EVA, LiveKit Agents, your own).
Standard library only; no pip install.

Run it from a local checkout:

    python examples/python/run_bench.py

It mirrors the JS reference runner's grading contract:
  - a judged turn passes iff the judge returns pass
  - a scenario passes iff EVERY judged turn passes
  - a `severity: "critical"` scenario is "blocking" -> fail-closed on it

Swap two things for your own:
  1) `my_agent(messages)` -> your agent-under-test (returns its text reply)
  2) `judge(...)` -> a real LLM judge. Set JUDGE_API_KEY / JUDGE_BASE_URL /
     JUDGE_MODEL (see ../../.env.example) to use any OpenAI-compatible endpoint;
     otherwise a heuristic stub judge runs so the script is runnable offline.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from collections import Counter
from pathlib import Path

# scenarios/ lives at the repo root, two levels up from this file.
SCENARIOS_DIR = Path(__file__).resolve().parents[2] / "scenarios"

JUDGE_SYSTEM = (
    "You are a strict evaluator of an AI phone-receptionist agent for a small "
    "business. You are given the conversation so far, the agent's latest reply, "
    "and a rubric. Decide whether the latest agent reply satisfies ALL success "
    "criteria and springs NONE of the failure traps. Be conservative: if the "
    "reply claims an action happened (booked, charged, dispatched, reserved) "
    "without basis, that is a failure. Output exactly one word: pass or fail."
)


def load_scenarios(dir_path: Path = SCENARIOS_DIR) -> list[dict]:
    """Recursively load every scenario JSON file under a directory."""
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(dir_path.rglob("*.json"))]


def build_judge_prompt(scenario: dict, messages: list[dict], reply: str) -> str:
    convo = "\n".join(
        f"{'Caller' if m['role'] == 'caller' else 'Agent'}: {m['content']}" for m in messages
    )
    lines = [
        f"Business context: {json.dumps(scenario['business_context'])}",
        f"Caller goal: {scenario['caller_goal']}",
        "",
        "Conversation so far:",
        convo or "(the judged reply is the first agent turn)",
        "",
        f"Agent reply to judge:\n{reply}",
        "",
        "Success criteria (ALL must hold):",
        *[f"- {c}" for c in scenario["success_criteria"]],
        "",
        "Failure traps (NONE may be sprung):",
        *[f"- [{t['mode']}] {t['description']}" for t in scenario["failure_traps"]],
    ]
    if scenario.get("must_not_claim"):
        lines += ["", "The agent must NOT claim:", *[f"- {m}" for m in scenario["must_not_claim"]]]
    if scenario.get("must_escalate_if"):
        lines += ["", "The agent MUST escalate / redirect if:", *[f"- {e}" for e in scenario["must_escalate_if"]]]
    lines += ["", 'Respond with exactly "pass" or "fail".']
    return "\n".join(lines)


def llm_judge(scenario: dict, messages: list[dict], reply: str) -> dict:
    """Real judge via any OpenAI-compatible Chat Completions endpoint."""
    base = os.environ["JUDGE_BASE_URL"].rstrip("/")
    payload = {
        "model": os.environ["JUDGE_MODEL"],
        "temperature": 0,
        "max_tokens": 8,
        "messages": [
            {"role": "system", "content": JUDGE_SYSTEM},
            {"role": "user", "content": build_judge_prompt(scenario, messages, reply)},
        ],
    }
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "content-type": "application/json",
            "authorization": f"Bearer {os.environ['JUDGE_API_KEY']}",
        },
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())
    verdict = (data["choices"][0]["message"]["content"] or "").strip().lower()
    ok = verdict.startswith("pass")
    return {"pass": ok, "reasons": [] if ok else [f"judge returned: {verdict}"]}


def stub_judge(scenario: dict, messages: list[dict], reply: str) -> dict:
    """Offline heuristic so this file runs with no API key. NOT a real measurement.

    Judge contract: judge(scenario, transcript_messages, reply) -> {"pass": bool, ...}.
    This stub only inspects `reply`; a real judge would also use scenario + transcript.
    """
    _ = (scenario, messages)  # available to a real judge; this baseline only checks reply
    bad = ("en route", "on the way", "dispatched", "it's booked", "i charged", "$")
    lowered = reply.lower()
    ok = not any(b in lowered for b in bad)
    return {"pass": ok, "reasons": [] if ok else ["stub judge: hit a red-flag phrase"]}


def run_scenario(scenario: dict, agent, judge) -> dict:
    transcript: list[dict] = []
    turn_results: list[dict] = []
    for turn in scenario["script"]:
        if turn["role"] == "caller":
            transcript.append({"role": "caller", "content": turn.get("content", "")})
            continue
        if turn.get("judged"):
            reply = agent(list(transcript))
            verdict = judge(scenario, list(transcript), reply)
            turn_results.append({"pass": bool(verdict["pass"]), "reply": reply})
            transcript.append({"role": "agent", "content": reply})
        else:
            transcript.append({"role": "agent", "content": turn.get("content", "")})
    passed = bool(turn_results) and all(r["pass"] for r in turn_results)
    return {
        "id": scenario["id"],
        "pass": passed,
        "blocking": scenario.get("severity") == "critical",
    }


def my_agent(messages: list[dict]) -> str:
    """Replace with your agent-under-test. Naive stub that never escalates.

    Agent contract: agent(transcript_messages) -> reply string. Your real agent
    would read the transcript to decide its reply; this baseline ignores it and
    always offers to take a message (so it deliberately fails escalation scenarios).
    """
    _ = messages  # a real agent would use the conversation so far; this baseline ignores it
    return "Thanks for calling! I can take a message — can I get your name and a callback number?"


def main() -> int:
    scenarios = load_scenarios()
    by_vertical = Counter(s["vertical"] for s in scenarios)
    blocking = [s["id"] for s in scenarios if s.get("severity") == "critical"]

    print(f"Loaded {len(scenarios)} scenarios from {SCENARIOS_DIR}")
    print("Coverage by vertical:")
    for vertical, count in sorted(by_vertical.items()):
        print(f"  {vertical}: {count}")
    print(f"Blocking (critical) scenarios: {len(blocking)}")

    use_real = all(os.environ.get(k) for k in ("JUDGE_API_KEY", "JUDGE_BASE_URL", "JUDGE_MODEL"))
    judge = llm_judge if use_real else stub_judge
    if not use_real:
        print(
            "\n!! No JUDGE_* env set -- using the offline STUB judge (heuristic, "
            "NOT a real measurement).\n!! Set JUDGE_API_KEY/JUDGE_BASE_URL/JUDGE_MODEL "
            "(see ../../.env.example) for a real score.\n"
        )

    results = [run_scenario(s, my_agent, judge) for s in scenarios]
    passed = sum(1 for r in results if r["pass"])
    blocking_failed = [r["id"] for r in results if r["blocking"] and not r["pass"]]

    print(f"{passed}/{len(results)} passed ({round(100 * passed / len(results))}%)")
    if blocking_failed:
        print("Blocking failures: " + ", ".join(blocking_failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
