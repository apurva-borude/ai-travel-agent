"""A few quick sanity checks for the tools + the rules fallback.

Run with:  python -m pytest tests/   (or just `python tests/test_tools.py`)
These don't hit the network, so they run anywhere.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.claim import ClaimBuilder
from src.tools import check_limits, check_receipts, detect_duplicates
from src.agent import ReimbursementAgent


def _meals_over_cap():
    return (ClaimBuilder("T-1")
            .employee("E-1", "Test")
            .add_item("meals", 95, date="2026-01-01", receipt=True)  # cap is 75
            .build())


def test_limit_caps_meals():
    res = check_limits(_meals_over_cap())
    line = res["lines"][0]
    assert line["status"] == "capped"
    assert line["approved"] == 75
    assert line["deducted"] == 20


def test_ineligible_category_rejected():
    claim = (ClaimBuilder("T-2")
             .add_item("entertainment", 100, receipt=True)
             .build())
    res = check_limits(claim)
    assert res["lines"][0]["status"] == "rejected"
    assert res["approved_total"] == 0


def test_missing_receipt_flagged():
    claim = (ClaimBuilder("T-3")
             .add_item("lodging", 150, receipt=False, nights=1)  # lodging always needs one
             .build())
    res = check_receipts(claim)
    assert res["all_present"] is False


def test_duplicate_detected():
    claim = (ClaimBuilder("T-4")
             .add_item("meals", 30, date="2026-01-01", receipt=True)
             .add_item("meals", 30, date="2026-01-01", receipt=True)
             .build())
    assert detect_duplicates(claim)["has_duplicates"] is True


def test_rules_partial_approve():
    # no LLM key in test env -> agent uses the rules engine
    agent = ReimbursementAgent()
    decision = agent._run_with_rules(_meals_over_cap())
    assert decision.decision == "Partially Approve"
    assert decision.approved_amount == 75


if __name__ == "__main__":
    # poor man's test runner so you don't strictly need pytest installed
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok -", name)
    print("all good")
