"""The reimbursement agent.

Two ways it can run:
  1. LLM mode (default, when a Cerebras key is set) - we hand the model the
     claim + a set of tools and let it decide which tools to call, then it
     returns the final decision as JSON.
  2. Rules mode (fallback) - if there's no key / the SDK isn't installed / the
     model output can't be parsed, we fall back to a plain deterministic engine
     so the demo always produces *something* sensible.

Either way the output is the same Decision shape, assembled with DecisionBuilder.
"""

import json
import os   # noqa  (had it for debug logging, leaving it)

from .decision import DecisionBuilder
from .llm import CerebrasLLM
from . import tools as toolbox

# bump this if the model starts looping forever on a weird claim
DEBUG = False


# --- tool schemas the model sees (OpenAI-style function defs) ----------------
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_policy",
            "description": "Get the part of the written travel policy relevant "
                           "to a topic, e.g. 'lodging', 'receipts', "
                           "'manual review', 'eligibility'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "what to look up"}
                },
                "required": ["topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_limits",
            "description": "Apply per-category caps and eligibility to every "
                           "line item. Returns approved/deducted per line and "
                           "the totals. Call this once.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_receipts",
            "description": "List line items missing a required receipt.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "detect_duplicates",
            "description": "Flag duplicate line items (same category, amount, date).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


SYSTEM_PROMPT = """You are a travel reimbursement approval agent for Acme Corp.

You decide one of: Approve, Partially Approve, Reject, Manual Review.

How to work:
- Use the tools to ground your decision. Call check_limits to get the money
  numbers, check_receipts for missing docs, detect_duplicates for double
  submits, and lookup_policy when you need the actual policy wording.
- Trust the numbers from check_limits for approved_amount and deducted_amount.
- Route to "Manual Review" when: claim total is above the manual_review
  threshold, a business-class airfare exception shows up, required receipts are
  missing for a material amount, or the case is ambiguous / not covered.
- "Partially Approve" when some lines are capped or rejected but the rest is ok.
- "Reject" when basically the whole claim is ineligible.
- Don't invent rules that aren't in the policy. If unsure, prefer Manual Review.

When you are done calling tools, reply with ONLY a JSON object, no prose:
{
  "decision": "...",
  "approved_amount": 0,
  "deducted_amount": 0,
  "missing_documents": ["..."],
  "policy_references": ["..."],
  "confidence": 0.0,
  "explanation": "one short paragraph"
}
"""


class ReimbursementAgent:
    def __init__(self, llm=None, max_steps=6):
        self.llm = llm or CerebrasLLM()
        self.max_steps = max_steps

    def evaluate(self, claim):
        if self.llm.available:
            try:
                return self._run_with_llm(claim)
            except Exception as e:
                # if anything goes sideways with the model, don't fail the run -
                # fall back to the rules engine and note it in the trail.
                print("[warn] LLM path failed ({}), using rules fallback".format(e))
                return self._run_with_rules(claim, note="llm_error: %s" % e)
        return self._run_with_rules(claim)

    # ------------------------------------------------------------------ LLM
    def _dispatch(self, name, args, claim):
        """Run a tool by name. Most tools just need the claim; lookup_policy
        takes a topic arg from the model."""
        if name == "lookup_policy":
            return toolbox.lookup_policy(args.get("topic", ""))
        fn = toolbox.TOOL_FUNCS.get(name)
        if not fn:
            return {"error": "unknown tool: %s" % name}
        return fn(claim)

    def _run_with_llm(self, claim):
        builder = DecisionBuilder(claim.claim_id, claim.currency)
        builder.log("intake", detail="claim %s, total %s" % (claim.claim_id, claim.total))

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "Evaluate this claim:\n" + _claim_as_text(claim)},
        ]

        final_json = None
        for _ in range(self.max_steps):
            msg = self.llm.chat(messages, tools=TOOL_SCHEMAS)
            if DEBUG:
                print("MSG ->", msg)
            # print(messages)   # uncomment when the tool loop misbehaves

            calls = getattr(msg, "tool_calls", None)
            if not calls:
                # no more tool calls -> this should be the final answer
                final_json = _extract_json(msg.content or "")
                builder.log("final", detail="model returned decision")
                break

            # we have to echo the assistant message back before the tool results
            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": c.id,
                        "type": "function",
                        "function": {"name": c.function.name,
                                     "arguments": c.function.arguments},
                    } for c in calls
                ],
            })

            for c in calls:
                name = c.function.name
                try:
                    args = json.loads(c.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                result = self._dispatch(name, args, claim)
                builder.log("tool_call", tool=name, detail=_short(result))
                messages.append({
                    "role": "tool",
                    "tool_call_id": c.id,
                    "content": json.dumps(result, default=str),
                })

        if not final_json:
            # model never gave us clean JSON - safest thing is manual review
            return (builder
                    .decision("Manual Review")
                    .confidence(0.3)
                    .explanation("Could not get a clean decision from the model.")
                    .build())

        return self._apply_model_decision(builder, claim, final_json)

    def _apply_model_decision(self, builder, claim, data):
        builder.decision(data.get("decision", "Manual Review"))
        # we still recompute the limits to make sure the model's numbers are
        # grounded - if they drift a lot we trust the tool, not the model.
        limit_res = toolbox.check_limits(claim)
        approved = data.get("approved_amount", limit_res["approved_total"])
        deducted = data.get("deducted_amount", limit_res["deducted_total"])
        builder.amounts(approved, deducted)
        builder.confidence(data.get("confidence", 0.7))
        builder.explanation(data.get("explanation", ""))
        # sometimes the model sends these as a string instead of a list, ugh.
        # wrapping in try so one bad field doesn't kill the whole decision
        try:
            for d in data.get("missing_documents", []) or []:
                builder.add_missing(d)
            for r in data.get("policy_references", []) or []:
                builder.add_policy_ref(r)
        except Exception:
            pass
        return builder.build()

    # ---------------------------------------------------------------- rules
    def _run_with_rules(self, claim, note=None):
        """Deterministic fallback. Mirrors the same logic we ask the LLM to
        follow, just without the language model."""
        builder = DecisionBuilder(claim.claim_id, claim.currency)
        builder.log("intake", detail="rules engine (no LLM)")
        if note:
            builder.log("note", detail=note)

        limit_res = toolbox.check_limits(claim)
        receipt_res = toolbox.check_receipts(claim)
        dup_res = toolbox.detect_duplicates(claim)
        builder.log("tool_call", tool="check_limits", detail=_short(limit_res))
        builder.log("tool_call", tool="check_receipts", detail=_short(receipt_res))
        builder.log("tool_call", tool="detect_duplicates", detail=_short(dup_res))

        approved = limit_res["approved_total"]
        deducted = limit_res["deducted_total"]
        builder.amounts(approved, deducted)

        statuses = [l["status"] for l in limit_res["lines"]]
        has_exception = "exception" in statuses
        all_rejected = all(s == "rejected" for s in statuses)
        any_rejected_or_capped = any(s in ("rejected", "capped") for s in statuses)

        # receipts missing on a material amount -> human
        # 100 is a bit arbitrary tbh, finance said "anything big" so... 100 it is
        material_missing = any(m["amount"] > 100 for m in receipt_res["missing_receipts"])

        reasons = []
        if claim.total > limit_res["manual_review_total_above"]:
            reasons.append("claim total over manual-review threshold")
        if has_exception:
            reasons.append("business-class airfare exception")
        if material_missing:
            reasons.append("missing receipt on a material amount")
        if dup_res["has_duplicates"]:
            reasons.append("possible duplicate line items")

        if reasons:
            builder.decision("Manual Review").confidence(0.6)
            builder.explanation("Routed to manual review: " + "; ".join(reasons) + ".")
            builder.add_policy_ref("Travel Policy section 4 (manual review triggers)")
        elif all_rejected:
            builder.decision("Reject").confidence(0.8)
            builder.explanation("All line items are ineligible under the policy.")
            builder.add_policy_ref("Travel Policy section 3 (eligibility)")
        elif any_rejected_or_capped:
            builder.decision("Partially Approve").confidence(0.75)
            builder.explanation(
                "Some items were capped or rejected; the remainder is within policy. "
                "Approved ${}, deducted ${}.".format(approved, deducted))
            builder.add_policy_ref("Travel Policy section 2 (per-category limits)")
        else:
            builder.decision("Approve").confidence(0.85)
            builder.explanation("All items within policy and receipts present.")

        for m in receipt_res["missing_receipts"]:
            builder.add_missing("{} receipt (${})".format(m["category"], m["amount"]))

        return builder.build()


# --- little formatting helpers ----------------------------------------------
def _claim_as_text(claim):
    rows = []
    for li in claim.line_items:
        extra = ""
        if li.cabin:
            extra = " cabin=%s" % li.cabin
        rows.append("- {} ${} on {} (receipt={}){}".format(
            li.category, li.amount, li.date or "?", li.receipt_attached, extra))
    return ("claim_id: {}\npurpose: {}\ndestination: {}\ndates: {} -> {}\n"
            "currency: {}\ntotal: {}\nline_items:\n{}").format(
        claim.claim_id, claim.purpose, claim.destination,
        claim.trip_start, claim.trip_end, claim.currency, claim.total,
        "\n".join(rows))


def _extract_json(text):
    """Pull the first {...} blob out of the model reply and parse it."""
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None


def _short(obj, n=240):
    s = json.dumps(obj, default=str)
    return s if len(s) <= n else s[:n] + "..."
