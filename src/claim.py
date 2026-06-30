"""Claim data model + a small builder to construct claims.

We use a Builder here mostly because claims can come from different shapes
(JSON file, an API body, or being typed in by hand in a test) and the builder
gives us one place to validate + normalise instead of repeating it everywhere.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class LineItem:
    category: str
    amount: float
    date: str = ""
    vendor: str = ""
    receipt_attached: bool = False
    nights: int = 1            # only really used for lodging
    cabin: Optional[str] = None  # only for airfare

    def __post_init__(self):
        # category is matched against the policy in lowercase, so normalise it
        self.category = str(self.category).strip().lower()


@dataclass
class Claim:
    claim_id: str
    employee_id: str = ""
    employee_name: str = ""
    purpose: str = ""
    destination: str = ""
    trip_start: str = ""
    trip_end: str = ""
    submitted_on: str = ""
    currency: str = "USD"
    line_items: List[LineItem] = field(default_factory=list)

    @property
    def total(self) -> float:
        return round(sum(li.amount for li in self.line_items), 2)


class ClaimBuilder:
    """Fluent builder for a Claim.

    Usage:
        claim = (ClaimBuilder("CLM-1")
                    .employee("E-1", "Jordan")
                    .trip("Chicago", "2026-06-10", "2026-06-12")
                    .add_item("meals", 48, receipt=True)
                    .build())
    """

    def __init__(self, claim_id: str):
        self._claim_id = claim_id
        self._employee_id = ""
        self._employee_name = ""
        self._purpose = ""
        self._destination = ""
        self._trip_start = ""
        self._trip_end = ""
        self._submitted_on = ""
        self._currency = "USD"
        self._items: List[LineItem] = []

    def employee(self, emp_id, name=""):
        self._employee_id = emp_id
        self._employee_name = name
        return self

    def purpose(self, text):
        self._purpose = text
        return self

    def trip(self, destination, start, end):
        self._destination = destination
        self._trip_start = start
        self._trip_end = end
        return self

    def submitted_on(self, date):
        self._submitted_on = date
        return self

    def currency(self, code):
        self._currency = code
        return self

    def add_item(self, category, amount, date="", vendor="", receipt=False,
                 nights=1, cabin=None):
        self._items.append(LineItem(
            category=category,
            amount=float(amount),
            date=date,
            vendor=vendor,
            receipt_attached=bool(receipt),
            nights=nights,
            cabin=cabin,
        ))
        return self

    def build(self) -> Claim:
        if not self._claim_id:
            raise ValueError("claim_id is required")
        # a claim with no line items is almost certainly a mistake upstream
        if not self._items:
            raise ValueError("claim has no line items")
        # NOTE: not validating dates here. probably should. later.
        return Claim(
            claim_id=self._claim_id,
            employee_id=self._employee_id,
            employee_name=self._employee_name,
            purpose=self._purpose,
            destination=self._destination,
            trip_start=self._trip_start,
            trip_end=self._trip_end,
            submitted_on=self._submitted_on,
            currency=self._currency,
            line_items=self._items,
        )

    @classmethod
    def from_dict(cls, data: dict) -> "ClaimBuilder":
        """Build straight from a parsed JSON claim (file or API body)."""
        b = cls(data.get("claim_id", ""))
        b.employee(data.get("employee_id", ""), data.get("employee_name", ""))
        b.purpose(data.get("purpose", ""))
        b.trip(data.get("destination", ""),
               data.get("trip_start", ""),
               data.get("trip_end", ""))
        b.submitted_on(data.get("submitted_on", ""))
        b.currency(data.get("currency", "USD"))
        for it in data.get("line_items", []):
            b.add_item(
                category=it.get("category", "misc"),
                amount=it.get("amount", 0),
                date=it.get("date", ""),
                vendor=it.get("vendor", ""),
                receipt=it.get("receipt_attached", False),
                nights=it.get("nights", 1),
                cabin=it.get("cabin"),
            )
        return b
