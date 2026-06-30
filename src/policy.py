"""Loads the policy text + limits table. This is the 'context grounding' bit -
the agent reads these before deciding anything.
"""

import json
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def load_limits():
    path = os.path.join(DATA_DIR, "limits.json")
    with open(path, "r") as f:
        return json.load(f)


def load_policy_text():
    path = os.path.join(DATA_DIR, "travel_policy.md")
    with open(path, "r") as f:
        return f.read()


# tiny keyword index so the policy lookup tool can return a relevant chunk
# instead of dumping the whole document into the prompt every time.
def policy_snippet(topic: str) -> str:
    text = load_policy_text()
    topic = (topic or "").lower()
    sections = text.split("## ")
    hits = []
    for sec in sections:
        # dumb substring match, not real search but works for the demo topics
        if topic and topic in sec.lower():
            hits.append("## " + sec.strip())
    if not hits:
        # fall back to the general rules section so we always return something
        return _section_starting_with(text, "1. General Rules")
    return "\n\n".join(hits)


def _section_starting_with(text, heading):
    for sec in text.split("## "):
        if sec.strip().startswith(heading):
            return "## " + sec.strip()
    return text[:500]
