# Checkout requirements (M1)

This document defines what every M1 implementation must do. It is written before any implementation exists. Arms A, B and C implement it, and the held-out acceptance suite in `acceptance/` tests it.

The base requirements are R0. Two later changes add a feature each:
- **`b2g1`** (change C1): buy two, get one free.
- **`partial_refunds`** (change C2).

Each change starts from the base. The acceptance suite takes `--features` to select which features are in force.

## 1. Catalog and constants

| Name | Value |
|---|---|
| SKUs and list prices (integer cents) | A 1000, B 2500, C 400, D 9900 |
| Initial stock | 6 units of each SKU |
| Reservation hold | 900 seconds (15 minutes) |
| Refund window | 2,592,000 seconds (30 days) |

Time is an integer number of seconds from a shared clock. Implementations read time only from that clock.

## 2. Orders

An order has these fields:
- an id;
- a customer;
- items: one `(sku, qty)` pair per SKU, sorted by SKU;
- a price in cents;
- a status;
- `reserved_at`;
- `charged_at`: the time the payment provider applied the charge, or none;
- `refunded`: the total amount refunded, in cents.

Statuses:

| Status | Meaning |
|---|---|
| `reserved` | Stock is held, and the order is not yet charged |
| `paying` | A charge has been started, and its outcome is not yet known |
| `paid` | The charge was applied |
| `refunding` | A refund has been started, and its outcome is not yet known |
| `refunded` | Fully refunded |
| `expired` | The hold lapsed before payment, and the stock was released |

Stock is held by orders in `reserved`, `paying`, `paid`, `refunding` and `refunded`. Refunds do not return goods to stock.

## 3. Requests

Every request carries a `request_id` and a `customer`.

**Rejections.** A rejected request changes nothing and returns `ok = false` with one of these reasons:

| Reason | When |
|---|---|
| `bad_items` | Items are empty, or contain an unknown SKU, a quantity that is not an int, a bool, or a quantity below 1 |
| `out_of_stock` | Some SKU has less stock than requested |
| `not_found` | The order does not exist or belongs to another customer. The two cases are indistinguishable. |
| `expired` | The order's hold has lapsed |
| `not_payable` | The order is in a status other than `reserved` |
| `not_refundable` | The order is in a status other than `paid` |
| `window_closed` | The refund window has passed |
| `declined` | The provider declined the payment |
| `in_progress` | A request with the same `request_id` is still being processed |
| `bad_amount` | `partial_refunds` only: the amount is out of range |

**Idempotency.** A request whose `request_id` was already processed returns the stored response and has no other effect. A repeat that arrives while the original is still being processed has no effect. It may return `in_progress`.

### 3.1 `place_order(request_id, customer, items)`

1. Validate the items. On failure, reject with `bad_items`.
2. Combine lines for the same SKU.
3. If any SKU has less stock than the combined quantity, reject with `out_of_stock`. Nothing is reserved; reservation is all or nothing.
4. Otherwise:
   - take the stock;
   - create an order with status `reserved`, `reserved_at = now`, and the price from the pricing rule (section 4);
   - respond with `ok`, the order id, the price and the status.

### 3.2 `pay(request_id, customer, order_id)`

The checks run in this order:
1. Not found, or another customer's order: `not_found`.
2. Status `expired`, or status `reserved` with `now − reserved_at ≥ 900`: `expired`. This applies even if the expiry job has not run yet.
3. Any status other than `reserved`: `not_payable`.

Otherwise, charge exactly the order's price to the customer through the provider.
- The order is `paying` until the outcome is known.
- If the charge is applied, the order becomes `paid`, and `charged_at` is the time the provider reports.
- If the charge is declined, the order returns to `reserved`.
- If the outcome is unknown (the call timed out), the order stays `paying` until a job reconciles it.

A provider must never apply more than one charge for an order. A new charge attempt may start only after the previous one was declined.

**The response.** If the outcome is known by the time `pay` returns, it may report it: `ok` with status `paid`, or `declined`. Otherwise it returns `ok` with status `paying`. Callers learn the final outcome from the order's status after jobs run.

### 3.3 `refund(request_id, customer, order_id)`

The checks run in this order:
1. `not_found`, as for `pay`.
2. Any status other than `paid`: `not_refundable`.
3. `now − charged_at > 2,592,000`: `window_closed`. A refund at exactly 30 days is allowed.

Otherwise, refund the full price to the customer through the provider.
- The order is `refunding` until the outcome is known.
- Then it becomes `refunded`, with `refunded` equal to the price.
- If declined, it returns to `paid`.
- If the outcome is unknown, it stays `refunding` until a job reconciles it.

The response follows the same rules as for `pay`.

### 3.4 `run_jobs()`

This runs background work:
- **Expiry.** Every `reserved` order with `now − reserved_at ≥ 900` becomes `expired`, and its stock is released.
- **Reconciliation.** Every charge or refund with an unknown outcome is looked up at the provider by its key:
  - applied: complete it;
  - declined: fail it;
  - absent (it never reached the provider): retry it with the same key.
- **Delivery.** Implementations that call the provider asynchronously deliver their pending calls here.

With provider faults off, a few calls to `run_jobs` (at most 5) must settle every order. No order may then be left `paying` or `refunding`.

`run_jobs` may be called while a provider call is in flight. For example, a job runner can run alongside a request.

### 3.5 Views

These are for operators and tests. They have no tenant scoping.
- `order(order_id)`: the order, or none.
- `orders()`: all orders.
- `stock()`: the current stock for each SKU.

## 4. Pricing

**Base:** the price is the sum of list price × quantity over the combined items.

**`b2g1` (C1):** buy two, get one free. For each SKU, after combining lines, every third unit is free:

```
line price = list price × (qty − qty // 3)
```

## 5. Payment provider

The provider is an external service. Tests use the fake in `world/`.

| Call | Behaviour |
|---|---|
| `charge(key, customer, order_id, amount)` | Returns a receipt with the time applied. Raises `PaymentDeclined` or `PaymentTimeout`. |
| `refund(key, customer, order_id, amount)` | The same. |
| `lookup(key)` | Returns the applied record, `"declined"`, or none if the key never reached the provider. |

- **Idempotent by key.** Repeating a key returns the first outcome and applies nothing new.
- **A timeout is ambiguous.** The call may have been applied with its response lost, or never have arrived.
- **The provider's ledger is the ground truth for money.**

## 6. Properties that must always hold

These must hold at every point, including while a provider call is in flight.

| ID | Property |
|---|---|
| S1 | Stock is never negative. |
| S2 | For each SKU, stock plus the units held by orders (section 2) equals the initial stock. |
| S3 | The provider applied at most one charge per order, for exactly the order's price. |
| S4 | Refunds applied for an order total no more than the charge applied for it. |
| S5 | Every applied charge and refund names the order's customer. |
| S6 | No `expired` order has an applied charge. |
| B1 | Every order's price follows the pricing rule in force. |
| B2 | Every applied refund was applied within the refund window of its order's charge. |

These must hold after settling with faults off:

| ID | Property |
|---|---|
| P1 | No order is `paying` or `refunding`. |
| P2 | An order is `paid` or `refunded` exactly when the ledger has its charge. `charged_at` equals the ledger's charge time, and `refunded` equals the ledger's refund total. |
| P3 | No order is `reserved` past its hold. |

## 7. `partial_refunds` (C2)

- `refund` takes an optional `amount` in cents. If it is omitted, the amount is the remaining refundable amount, `price − refunded`.
- The amount must be an int, not a bool, with `1 ≤ amount ≤ price − refunded`. Otherwise the request is rejected with `bad_amount`.
- Several refunds may be made within the window, one at a time. While a refund is in flight, the order is `refunding`, and further refunds are `not_refundable`.
- When a refund completes, `refunded` increases by its amount. The status becomes `refunded` if `refunded` equals the price, and `paid` otherwise.
- A declined refund returns the order to `paid` with `refunded` unchanged.
- The check order is `not_found`, `not_refundable`, `window_closed`, then `bad_amount`.
- S4 must still hold under concurrent requests and faults.
