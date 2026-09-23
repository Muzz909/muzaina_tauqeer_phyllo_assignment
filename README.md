# Product Analyst Intern Assignment: Muzaina Tauqeer

`check_orders.py` reproduces every finding and number below (reads `responses/`). Resume: `Muzaina Tauqeer Product Analyst Resume.pdf`.

## Task 1: What doesn't match?

| # | Docs say | Data does | Does it hurt? |
|---|---|---|---|
| 1 | Check `has_more` to decide whether to fetch the next page | `orders_page1.json`: `has_more: false`, yet `next_cursor` is set and page 2 returns two more orders | Yes. Clients following the docs stop after page 1 and silently lose orders |
| 2 | Money is integer cents (5470 = $54.70) | `orders_page2.json`, ord_1006: every amount is a decimal in dollars (`total: 53.62`) | Yes. Read as cents, $53.62 becomes $0.54. Strict integer parsing may fail |
| 3 | `status` is pending, shipped, delivered or cancelled | `orders_page1.json`, ord_1003: `status: "refunded"` | Yes. Refunds get counted as sales; code handling four statuses may break |
| 4 | `total` always equals subtotal + tax + shipping | `orders_page1.json`, ord_1004: 6200 + 511 + 599 = 7310, but `total` is 6810 | Yes, for reconciliation. Tax is 8.25% of the full 6200, so not a normal pre-tax discount |
| 5 | A missing order returns `404` | `order_ord_9999.json`: `200` with `{"order": null}` | Yes. Clients checking status codes treat a missing order as found, then fail on `null` |
| 6 | Orders are listed most recent first | Both pages run oldest to newest (14 to 16 March) | Moderate. Anything reading page 1 for "latest orders" gets the oldest |
| 7 | Customer `email` is always present | `orders_page2.json`, ord_1005: `email: null` (guest) | Moderate. Breaks receipts and email matching. No money impact |

**Worst: #1.** It's silent, punishes clients for following the docs exactly, and loses whole pages, getting worse the more orders a customer has. #2 is close (a 100× error), but a type check catches a decimal where an integer is promised. A never-requested page leaves nothing to check.

## Task 2: Total revenue

**$225.70** across 5 orders.

Choices I made:
- **Included page 2** despite `has_more: false`. The orders are real.
- **Converted ord_1006 to cents** (53.62 → 5362). The same item costs $45.00 in ord_1001, so 44.0 only makes sense as dollars.
- **Excluded ord_1003 (refunded):** returned money isn't revenue. Assumed a full refund in the same period.
- **Used ord_1004's `total` (6810)**, not its parts (7310), because the docs define `total` as the amount charged.
- **Kept tax and shipping**: `total` includes them, and it's what Priya summed.

| Method | Result |
|---|---|
| Following the docs exactly (page 1 only, refund counted) | $248.94 |
| All pages, cents fixed, refund counted | $328.03 |
| **All pages, cents fixed, refund excluded** | **$225.70** |
| Same, excluding tax | $209.96 |

The first row is probably what Priya did: $23.24 off on six orders; over a month that could reach a few hundred dollars.

**What I couldn't tell, and what I'd ask:**
- What does the dashboard count as revenue (tax? refunds?)? That decides which figure Priya should match.
- Is page 2 really last, given `has_more` was wrong once?
- Was ord_1004 charged 6810 or 7310, and was ord_1003 fully refunded?
- Are these all of March's orders? The data only covers 14 to 16 March.

## Task 3

### Reply to Priya

> **Subject:** Why your revenue report doesn't match the dashboard
>
> Hi Priya,

> Thanks for flagging this. You followed our documentation correctly; our API doesn't always behave as documented. Four things are likely causing the gap:
>
> 1. **Missing orders.** Our API can wrongly signal there are no more orders, so your pull may have stopped early.
> 2. **Refunds counted as sales.** Refunded orders appear in the data; our docs don't mention them.
> 3. **Dollars read as cents.** At least one order is recorded in dollars, so $53.62 counts as about 54 cents.
> 4. **A total that doesn't add up.** One order is $5 below the sum of its parts; we're checking which is right.
>
> Some push your number up, others down, which is why the gap was hard to trace.
>
> I've raised these with our engineers. Does your dashboard figure include tax and refunds? Once I know, I'll send a corrected figure to reconcile against.

> Best Regards,
> Muzaina Tauqeer

### Bug report

**Title:** `GET /v1/orders` returns `has_more: false` when more pages exist, so clients silently miss orders

**Severity:** High. Silent data loss for clients following our docs. Contributes to TICKET-4502.

**Steps to reproduce**
1. `GET /v1/orders` returns ord_1001 to ord_1004 with `has_more: false` and `next_cursor: "cur_8f2a19bd"`.
2. `GET /v1/orders?starting_after=cur_8f2a19bd` returns `200` with ord_1005 and ord_1006.

Evidence: `responses/orders_page1.json`, `responses/orders_page2.json`.

**Expected:** Page 1 has `has_more: true`. `has_more` is `true` exactly when `next_cursor` is non-null.

**Actual:** `has_more: false` alongside a valid cursor that returns more orders.

**Open questions:** Could it hide a page 3? Is it every account, or specific conditions (page 1 held 4 orders; limit is 25)?

**Workaround until fixed:** keep paging while `next_cursor` is non-null.
