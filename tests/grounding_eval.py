"""Grounding check for the voice agent.

Does the agent answer from its lookup tool, or from its own out-of-date
training data? This script asks the agent ten questions in text mode,
several times each, and an automated script scores every answer with fixed
rules. A human reviewer should then read the failures in grounding_results.jsonl.

Run it from the project folder:

    uv run python tests/grounding_eval.py --repeats 1 --limit 1 --verbose
    uv run python tests/grounding_eval.py
    uv run python tests/grounding_eval.py --agent-file old_agent.py --out before.jsonl
    uv run python tests/grounding_eval.py --conversation --repeats 10

Each answer is one call to the language model through LiveKit Inference,
so the full run (10 questions x 3 repeats) makes about 30 calls.
"""

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from livekit.agents import AgentSession  # noqa: E402

import importlib.util  # noqa: E402

agent = None  # loaded in main(), so --agent-file can swap in an older version

# Phrases that mean the agent doubted a model the table lists as released.
DOUBT = [
    r"unreleased", r"not (yet )?released", r"hasn'?t been released",
    r"not out yet", r"isn'?t out", r"not available yet", r"upcoming",
    r"doesn'?t exist", r"does not exist", r"no such model", r"not aware of",
]
SOURCE = r"deprecations page"
NOT_FOUND = r"(can'?t|cannot|couldn'?t|could not|unable to|not able to) (confirm|find|verify)"

# Each case: the question, the tool the agent should call, phrases the answer
# must contain (each item is a regex), and phrases it must not contain.
CASES = [
    {"id": "Q01", "ask": "Is Claude Opus 4.8 available?",
     "tool": "check_claude_model", "must": [r"available", SOURCE], "must_not": DOUBT},
    {"id": "Q02", "ask": "Is Claude Opus four point eight out yet?",
     "tool": "check_claude_model", "must": [r"available", SOURCE], "must_not": DOUBT},
    {"id": "Q03", "ask": "Is Claude Fable 5.2 released?",
     "tool": "check_claude_model", "must": [r"(available|released)", SOURCE], "must_not": DOUBT},
    {"id": "Q04", "ask": "Can I still use Claude Sonnet 5.5?",
     "tool": "check_claude_model", "must": [r"available", SOURCE], "must_not": DOUBT},
    {"id": "Q05", "ask": "Is Claude Sonnet 4.5 still available?",
     "tool": "check_claude_model",
     "must": [r"november (30|thirtieth)", r"(5\.5|five point five)", SOURCE], "must_not": []},
    {"id": "Q06", "ask": "What happened to Claude Opus 4.1?",
     "tool": "check_claude_model",
     "must": [r"retired", r"(4\.8|four point eight)", SOURCE], "must_not": []},
    {"id": "Q07", "ask": "Is Claude Haiku 3.5 still working?",
     "tool": "check_claude_model", "must": [r"retired", SOURCE], "must_not": []},
    {"id": "Q08", "ask": "Should I switch off Claude 3 Haiku?",
     "tool": "check_claude_model",
     "must": [r"retired", r"(4\.5|four point five)", SOURCE], "must_not": []},
    {"id": "Q09", "ask": "Is Claude Opus 6 out?",
     "tool": "check_claude_model", "must": [NOT_FOUND],
     # "I can't confirm if Claude Opus six is out" is a correct answer, so only
     # an answer that opens with "yes" counts as claiming the model exists.
     "must_not": [r"^yes\b"]},
    {"id": "Q10", "ask": "Which Claude models are retiring soon?",
     "tool": "list_retiring_models",
     "must": [r"sonnet", r"november (30|thirtieth)", SOURCE], "must_not": []},
]


def clean(text: str) -> str:
    """Drop expressive-mode tags like <expr ... /> and lowercase the text."""
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", text).strip().lower()


def read_events(result) -> tuple[list[str], str]:
    """Return the tools the agent called and the text it said."""
    tools, words = [], []
    for ev in getattr(result, "events", []):
        item = getattr(ev, "item", None)
        kind = getattr(ev, "type", type(ev).__name__).lower()
        if "function_call" in kind and "output" not in kind:
            tools.append(getattr(item, "name", "?"))
        elif "message" in kind and getattr(item, "role", "") == "assistant":
            text = getattr(item, "text_content", None)
            if text is None:
                text = " ".join(c for c in getattr(item, "content", []) if isinstance(c, str))
            words.append(text)
    return tools, " ".join(words)


def score(case: dict, tools: list[str], said: str) -> dict:
    text = clean(said)
    rules = {
        "called_tool": case["tool"] in tools,
        "has_required": all(re.search(p, text) for p in case["must"]),
        "avoids_forbidden": not any(re.search(p, text) for p in case["must_not"]),
    }
    missing = [p for p in case["must"] if not re.search(p, text)]
    found = [p for p in case["must_not"] if re.search(p, text)]
    return {"rules": rules, "passed": all(rules.values()), "missing": missing, "forbidden_found": found}


async def ask(case: dict, verbose: bool) -> dict:
    async with AgentSession() as session:  # uses the agent's own language model
        await session.start(agent.Assistant())
        result = await session.run(user_input=case["ask"])
    if verbose:
        for ev in getattr(result, "events", []):
            print("   event:", ev)
    tools, said = read_events(result)
    return {"tools": tools, "said": said, **score(case, tools, said)}


# The original failure happened mid-conversation, on a follow-up question.
# --conversation replays that order in one session, so earlier turns are in context.
CONVERSATION = ["Is Claude Sonnet 4.5 still available?", "What about Opus 4.8?", "Is Claude Opus 6 out?"]


async def replay(repeats: int) -> None:
    trap = CASES[0]  # same rules as the Opus 4.8 question
    doubted = 0
    rows = []
    for n in range(1, repeats + 1):
        async with AgentSession() as session:
            await session.start(agent.Assistant())
            for turn in CONVERSATION:
                result = await session.run(user_input=turn)
                if "4.8" in turn:
                    tools, said = read_events(result)
                    row = score(trap, tools, said)
                    doubted += not row["rules"]["avoids_forbidden"]
                    rows.append({"run": n, "said": said, **row})
                    print(f"{'PASS' if row['rules']['avoids_forbidden'] else 'DOUBT'} run {n}: {clean(said)[:110]}")
    Path("conversation_results.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    print(f"\nFollow-up answers that doubted Opus 4.8: {doubted} of {repeats}")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--limit", type=int, default=len(CASES))
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--out", default="grounding_results.jsonl")
    parser.add_argument("--conversation", action="store_true",
                        help="Replay the three-question conversation from the demo instead of single questions")
    parser.add_argument("--agent-file", default=str(Path(__file__).resolve().parent.parent / "src" / "agent.py"),
                        help="Agent code to test, for example an older version to compare before and after a fix")
    args = parser.parse_args()

    global agent
    spec = importlib.util.spec_from_file_location("agent_under_test", args.agent_file)
    agent = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(agent)  # also loads .env.local
    print(f"Testing {args.agent_file}\n")
    if args.conversation:
        await replay(args.repeats)
        return

    cases = CASES[: args.limit]
    rows = []
    for case in cases:
        for n in range(1, args.repeats + 1):
            try:
                row = await ask(case, args.verbose)
            except Exception as e:  # record the failure and keep going
                row = {"tools": [], "said": "", "rules": {}, "passed": False, "error": repr(e)}
            row.update({"id": case["id"], "ask": case["ask"], "run": n})
            rows.append(row)
            mark = "PASS" if row["passed"] else "FAIL"
            print(f"{mark} {case['id']} run {n}: {clean(row['said'])[:110]}")

    Path(args.out).write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

    total = len(rows)
    passed = sum(r["passed"] for r in rows)
    print(f"\nPassed all rules: {passed} of {total}")
    for rule in ["called_tool", "has_required", "avoids_forbidden"]:
        ok = sum(r["rules"].get(rule, False) for r in rows)
        print(f"  {rule:18} {ok} of {total}")
    grounding = [r for r in rows if r["id"] in {"Q01", "Q02", "Q03", "Q04"}]
    if grounding:
        doubted = sum(not r["rules"].get("avoids_forbidden", False) for r in grounding)
        print(f"\nAnswers that doubted a released model: {doubted} of {len(grounding)}")
    print(f"Saved every answer to {args.out}. Read the FAIL lines there before trusting the number.")


if __name__ == "__main__":
    asyncio.run(main())
