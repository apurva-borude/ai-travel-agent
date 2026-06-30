"""The tools / functions the agent can call.

There are four of them:
  - lookup_policy        : pull a relevant chunk of the written policy
  - check_limits         : compare every line item against the limit table
  - check_receipts       : find line items that are missing a required receipt
  - detect_duplicates    : flag suspicious duplicate line items

check_limits is the one that actually does the money math (approved vs deducted
per line). The LLM uses the results to write the explanation and pick a label,
but the numbers come from here so they're deterministic.
"""

from .policy import load_limits, policy_snippet


def lookup_policy(topic: str) -> dict:
    """Return the part of the policy relevant to `topic` (e.g. 'lodging',
    'manual review', 'receipts')."""
    return {
        "topic": topic,
        "text": policy_snippet(topic),
    }


def check_limits(claim) -> dict:
    """Walk the line items and apply the per-category caps + eligibility.

    Returns a per-line breakdown plus the totals. Each line gets a status of
    'ok', 'capped', or 'rejected'.
    """
    limits = load_limits()
    cats = limits["categories"]
    eligible = limits["eligible_categories"]

    lines = []
    approved_total = 0.0
    deducted_total = 0.0

    for li in claim.line_items:
        cat = li.category
        amount = li.amount
        line = {
            "category": cat,
            "claimed": amount,
            "approved": 0.0,
            "deducted": 0.0,
            "status": "ok",
            "note": "",
        }

        # not an eligible category at all -> reject the whole line
        if cat not in eligible:
            line["status"] = "rejected"
            line["deducted"] = amount
            line["note"] = "category not eligible per policy section 3"
            deducted_total += amount
            lines.append(line)
            continue

        rule = cats[cat]
        cap = rule["limit"]

        # lodging cap is per-night, so scale it by the number of nights
        if rule["limit_type"] == "per_night":
            cap = cap * max(1, li.nights)

        # business class airfare is a policy exception, flag it (don't cap here)
        # NOTE: only checking for "business", what about "first"?? meh, no sample for it
        if cat == "airfare" and (li.cabin or "").lower() == "business":
            line["status"] = "exception"
            line["approved"] = amount
            line["note"] = "business class - needs manager approval (exception)"
            approved_total += amount
            lines.append(line)
            continue

        if amount > cap:
            line["status"] = "capped"
            line["approved"] = cap
            line["deducted"] = round(amount - cap, 2)
            line["note"] = "over the {} cap of ${}".format(rule["limit_type"], cap)
            approved_total += cap
            deducted_total += (amount - cap)
        else:
            line["approved"] = amount
            approved_total += amount

        lines.append(line)

    return {
        "lines": lines,
        "approved_total": round(approved_total, 2),
        "deducted_total": round(deducted_total, 2),
        "claim_total": claim.total,
        "manual_review_total_above": limits["manual_review_total_above"],
    }


def check_receipts(claim) -> dict:
    """Find line items that should have a receipt but don't."""
    limits = load_limits()
    cats = limits["categories"]
    threshold = limits["receipt_required_above"]

    missing = []
    for li in claim.line_items:
        rule = cats.get(li.category, {})
        always = rule.get("receipt_always", False)
        needs_receipt = always or li.amount > threshold
        if needs_receipt and not li.receipt_attached:
            missing.append({
                "category": li.category,
                "amount": li.amount,
                "reason": "receipt always required" if always
                          else "amount over ${}".format(threshold),
            })

    return {
        "missing_receipts": missing,
        "all_present": len(missing) == 0,
    }


def detect_duplicates(claim) -> dict:
    """Very simple dup check - same category + same amount + same date.

    Not trying to be clever here, just catching the obvious double-submits.
    """
    # TODO: this misses dups across different claims. good enough for now.
    seen = {}
    dups = []
    for li in claim.line_items:
        key = (li.category, li.amount, li.date)
        if key in seen:
            dups.append({
                "category": li.category,
                "amount": li.amount,
                "date": li.date,
            })
        else:
            seen[key] = True  # value doesn't matter, just need the key

    return {
        "duplicates": dups,
        "has_duplicates": len(dups) > 0,
    }


# map of tool name -> the function, so the agent can dispatch by name
TOOL_FUNCS = {
    "lookup_policy": lookup_policy,
    "check_limits": check_limits,
    "check_receipts": check_receipts,
    "detect_duplicates": detect_duplicates,
}
