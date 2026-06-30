"""CLI for the travel reimbursement agent.

Examples:
    python main.py data/claims/claim_partial.json
    python main.py data/claims/claim_approve.json --audit
    python main.py --all            # run every sample claim in data/claims
"""

import argparse
import glob
import json
import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional, env vars still work without it

from src.claim import ClaimBuilder
from src.agent import ReimbursementAgent


def run_one(agent, path, show_audit=False):
    with open(path, "r") as f:
        data = json.load(f)

    claim = ClaimBuilder.from_dict(data).build()
    decision = agent.evaluate(claim)

    out = decision.to_dict()
    if not show_audit:
        out.pop("audit_trail", None)

    # print(claim)   # left this in while testing, harmless
    print("=" * 60)
    print("Claim: {}   ({})".format(claim.claim_id, os.path.basename(path)))
    print("=" * 60)
    print(json.dumps(out, indent=2))
    print()   # spacing


def main():
    parser = argparse.ArgumentParser(description="Travel reimbursement approval agent")
    parser.add_argument("claim", nargs="?", help="path to a claim JSON file")
    parser.add_argument("--all", action="store_true", help="run all sample claims")
    parser.add_argument("--audit", action="store_true", help="include the audit trail")
    args = parser.parse_args()

    agent = ReimbursementAgent()
    if not agent.llm.available:
        print("[info] No Cerebras key found - running in deterministic rules mode.\n")

    if args.all:
        files = sorted(glob.glob("data/claims/*.json"))
        for fp in files:
            run_one(agent, fp, args.audit)
        return

    if not args.claim:
        parser.print_help()
        sys.exit(1)

    run_one(agent, args.claim, args.audit)


if __name__ == "__main__":
    main()
