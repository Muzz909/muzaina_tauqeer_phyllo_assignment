"""
check_orders.py
Checks the Meridian API responses against what API_DOCS.md promises,
then calculates total revenue.

How to run:  python check_orders.py
(Put this file next to the responses/ folder.)
"""

import json

# What the docs promise
ALLOWED_STATUSES = {"pending", "shipped", "delivered", "cancelled"}
MONEY_FIELDS = ["subtotal", "tax", "shipping", "total"]

problems = []  # every mismatch we find goes in here


def load(filename):
    with open(f"responses/{filename}") as f:
        return json.load(f)


# ---------- 1. Load both pages ----------
page1 = load("orders_page1.json")
page2 = load("orders_page2.json")

# Docs: if has_more is false, there should be no next page.
if page1["has_more"] is False and page1["next_cursor"] is not None:
    problems.append(
        "orders_page1.json: has_more is false, but next_cursor is set "
        "and page 2 exists (following the docs would miss page 2)"
    )

orders = page1["data"] + page2["data"]

# Docs: at most 25 orders per page
for name, page in [("orders_page1.json", page1), ("orders_page2.json", page2)]:
    if len(page["data"]) > 25:
        problems.append(f"{name}: more than 25 orders on one page")

# Check for duplicate orders across pages
ids = [o["id"] for o in orders]
if len(ids) != len(set(ids)):
    problems.append("Duplicate order IDs across pages")


# ---------- 2. Check each order against the docs ----------
def to_cents(value):
    """Docs say amounts are integer cents. If we get a decimal, assume dollars.
    Limitation: a whole-dollar amount sent as an integer (e.g. 44 meaning $44)
    would look like valid cents and can't be detected this way."""
    if isinstance(value, int):
        return value
    return round(value * 100)


for o in orders:
    oid = o["id"]

    # IDs must use the documented prefixes
    if not oid.startswith("ord_"):
        problems.append(f"{oid}: order id doesn't start with ord_")
    if not o["customer"]["id"].startswith("cus_"):
        problems.append(f"{oid}: customer id doesn't start with cus_")

    # Currency must be a three-letter code
    if not (isinstance(o["currency"], str) and len(o["currency"]) == 3):
        problems.append(f"{oid}: currency '{o['currency']}' is not a 3-letter code")

    # Timestamps must be UTC (ending in Z)
    if not o["created_at"].endswith("Z"):
        problems.append(f"{oid}: created_at is not in UTC")

    # subtotal should equal the sum of line items (quantity x unit price)
    items = sum(to_cents(i["unit_price"]) * i["quantity"] for i in o["line_items"])
    if items != to_cents(o["subtotal"]):
        problems.append(f"{oid}: subtotal doesn't match its line items")

    # Status must be one of the documented values
    if o["status"] not in ALLOWED_STATUSES:
        problems.append(f"{oid}: status '{o['status']}' is not in the docs")

    # Money fields must be integers (cents)
    if any(not isinstance(o[f], int) for f in MONEY_FIELDS):
        problems.append(f"{oid}: money fields are decimals (dollars), not integer cents")

    # total must equal subtotal + tax + shipping
    expected = to_cents(o["subtotal"]) + to_cents(o["tax"]) + to_cents(o["shipping"])
    actual = to_cents(o["total"])
    if expected != actual:
        problems.append(
            f"{oid}: total is {actual}, but subtotal+tax+shipping = {expected} "
            f"(difference {expected - actual} cents)"
        )

    # Email must always be present
    if not o["customer"].get("email"):
        problems.append(f"{oid}: customer email is missing")

# Docs: list is "most recent first"
dates = [o["created_at"] for o in orders]
if dates != sorted(dates, reverse=True):
    problems.append("Orders are sorted oldest first, docs say most recent first")


# ---------- 3. Check the single-order request ----------
# README says GET /v1/orders/ord_9999 returned status 200. Docs promise 404.
missing = load("order_ord_9999.json")
if missing.get("order") is None:
    problems.append(
        "order_ord_9999.json: returned 200 with {'order': null}; docs promise 404"
    )


# ---------- 4. Print what we found ----------
print(f"MISMATCHES WITH THE DOCS ({len(problems)} found)")
print("-" * 60)
for p in problems:
    print(" -", p)


# ---------- 5. Revenue ----------
print("\nORDERS")
print("-" * 60)
print(f"{'id':<10}{'status':<11}{'total ($)':>10}  counted?")

revenue = 0
tax_collected = 0
for o in orders:
    total = to_cents(o["total"])
    counted = o["status"] not in ("refunded", "cancelled")  # money kept by the business
    if counted:
        revenue += total
        tax_collected += to_cents(o["tax"])
    print(f"{o['id']:<10}{o['status']:<11}{total / 100:>10.2f}  {'yes' if counted else 'no'}")

# What Priya would get by following the docs exactly:
# stop after page 1 (has_more = false), sum every total as-is.
naive = sum(o["total"] for o in page1["data"])

print("\nREVENUE")
print("-" * 60)
print(f"Following the docs exactly (page 1 only):   ${naive / 100:,.2f}")
print(f"Corrected, refunds excluded (ANSWER):       ${revenue / 100:,.2f}")
print(f"Corrected, refunds excluded, without tax:   ${(revenue - tax_collected) / 100:,.2f}")
