# Acme Corp - Travel & Expense Reimbursement Policy (MOCK)

_This is mock policy data for a demo. Not a real company policy._

## 1. General Rules

- All claims must be submitted within 30 days of the trip end date.
- Reimbursements are paid in USD. Foreign currency should be converted at the
  rate on the receipt date (employee responsibility).
- Itemised receipts are required for any single expense above $25.
- Lodging and airfare always require a receipt regardless of amount.

## 2. Per-category limits

See `limits.json` for the exact numbers. In summary:

- **Lodging** is capped at $200 per night. Anything above is the employee's
  own cost (we still pay the capped portion).
- **Meals** are capped at $75 per day (all meals combined for that day).
- **Airfare** must be Economy class for any flight under 6 hours. Business
  class needs prior manager approval (treated as a policy exception here).
- **Ground transport** (taxi / rideshare / train) capped at $50 per day.
- **Misc** (parking, wifi, baggage) capped at $100 per claim.

## 3. Eligibility

Eligible categories: lodging, meals, airfare, ground_transport, misc.
Anything else (e.g. "entertainment", "minibar", "personal") is NOT eligible
and should be rejected for that line item.

## 4. Manual review triggers

A claim should go to **Manual Review** (not auto-decided) when:

- The total claim amount is above $5,000.
- A business-class airfare is claimed (policy exception, needs a human).
- The claim is missing required receipts AND the amount is material (> $100).
- Tools disagree or the situation is ambiguous / not covered by this policy.

## 5. Decisions

- **Approve** - everything within policy, receipts present.
- **Partially Approve** - some lines capped or rejected, the rest is fine.
- **Reject** - the whole claim is ineligible or clearly violates policy.
- **Manual Review** - see section 4.
