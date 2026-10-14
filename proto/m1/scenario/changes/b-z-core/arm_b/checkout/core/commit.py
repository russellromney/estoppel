"""Commit: check a plan against the facts and its grant, then apply all of it or none of it."""

from pydantic import BaseModel, ValidationError

from checkout.core.facts import Grant, Order, Payment, Receipt
from checkout.core.moves import OpenOrder, Plan, Release, StartCharge, StartRefund


class State(BaseModel):
    """The core's mutable state. Only `commit` and the runtime's `settle` change it."""

    stock: dict[str, int]
    budgets: dict[str, int] = {}     # budget name -> units available
    orders: dict[str, Order] = {}
    payment_orders: dict[str, str] = {}  # payment key -> order id
    opened: int = 0


class PlanRejected(Exception):
    """The periphery proposed something the core does not allow. This is a bug, not a user error."""

    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


def commit(plan: Plan, grant: Grant, state: State, now: int) -> Receipt:
    plan = revalidate(plan)
    problems = check(plan, grant, state, now)
    if problems:
        raise PlanRejected(problems)
    opened, started = [], []
    for move in plan.moves:
        match move:
            case OpenOrder():
                opened.append(_open(move, grant, state, now))
            case StartCharge():
                started.append(_start_charge(move, state, now))
            case StartRefund():
                started.append(_start_refund(move, state, now))
            case Release():
                _release(move, state)
    return Receipt(opened=tuple(opened), payments=tuple(started))


def revalidate(plan) -> Plan:
    """Rebuild the plan from plain data, so no unchecked object reaches the checks."""
    try:
        return Plan.model_validate(plan.model_dump())
    except (AttributeError, ValidationError) as e:
        raise PlanRejected([f"malformed plan: {e}"]) from None


def check(plan: Plan, grant: Grant, state: State, now: int) -> list[str]:
    problems = []
    targets = [m.order_id for m in plan.moves if not isinstance(m, OpenOrder)]
    if len(set(targets)) != len(targets):
        problems.append("a plan may touch each order once")
    if sum(isinstance(m, OpenOrder) for m in plan.moves) > 1:
        problems.append("a plan may open one order")
    for move in plan.moves:
        if move.kind not in grant.moves:
            problems.append(f"{move.kind} is not granted to {grant.kind}")
        elif isinstance(move, OpenOrder):
            problems += _check_open(move, state, now)
        else:
            problems += _check_target(move, grant, state, now)
    return problems


def _check_open(move: OpenOrder, state: State, now: int) -> list[str]:
    problems = []
    if move.hold_until <= now:
        problems.append("a hold must end in the future")
    for line in move.quote.lines:
        if line.sku not in state.stock:
            problems.append(f"unknown resource {line.sku}")
        elif state.stock[line.sku] < line.qty:
            problems.append(f"only {state.stock[line.sku]} {line.sku} available")
    if len(set(move.budgets)) != len(move.budgets):
        problems.append("an order draws from each budget once")
    for name in move.budgets:
        if name not in state.budgets:
            problems.append(f"unknown budget {name}")
        elif state.budgets[name] < 1:
            problems.append(f"budget {name} is used up")
    return problems


def _check_target(move, grant: Grant, state: State, now: int) -> list[str]:
    order = state.orders.get(move.order_id)
    if order is None:
        return [f"no order {move.order_id}"]
    if grant.scope == "subject" and move.order_id != grant.subject:
        return [f"order {move.order_id} is outside the grant"]
    match move:
        case StartCharge():
            return _check_charge(order, now)
        case StartRefund():
            return _check_refund(move, order)
        case Release():
            return _check_release(order)


def _check_charge(order: Order, now: int) -> list[str]:
    problems = []
    if order.hold != "held":
        problems.append(f"order {order.id} holds no stock")
    elif now >= order.hold_until:
        problems.append(f"order {order.id}'s hold has lapsed")
    if any(p.kind == "charge" and p.state != "declined" for p in order.payments):
        problems.append(f"order {order.id} is already charged or being charged")
    return problems


def _check_refund(move: StartRefund, order: Order) -> list[str]:
    if order.charge is None:
        return [f"order {order.id} has not been charged"]
    if len(move.per_line) != len(order.quote.lines):
        return ["a refund names an amount for every line"]
    problems = []
    if any(amount < 0 for amount in move.per_line) or sum(move.per_line) < 1:
        problems.append("a refund is positive and has no negative lines")
    for i, (amount, left) in enumerate(zip(move.per_line, order.refundable_per_line)):
        if amount > left:
            problems.append(f"line {i} refund {amount} exceeds the {left} left to refund")
    return problems


def _check_release(order: Order) -> list[str]:
    if order.hold != "held":
        return [f"order {order.id} holds no stock"]
    if order.open_charge is not None:
        return [f"order {order.id} has a charge in flight"]
    return []


def _open(move: OpenOrder, grant: Grant, state: State, now: int) -> str:
    state.opened += 1
    order = Order(id=f"o{state.opened}", customer=grant.principal, quote=move.quote,
                  opened_at=now, hold_until=move.hold_until, budgets=move.budgets)
    for line in move.quote.lines:
        state.stock[line.sku] -= line.qty
    for name in move.budgets:
        state.budgets[name] -= 1
    state.orders[order.id] = order
    return order.id


def _add_payment(state: State, order: Order, payment: Payment) -> Payment:
    state.orders[order.id] = order.model_copy(update={"payments": order.payments + (payment,)})
    state.payment_orders[payment.key] = order.id
    return payment


def _start_charge(move: StartCharge, state: State, now: int) -> Payment:
    order = state.orders[move.order_id]
    attempt = sum(p.kind == "charge" for p in order.payments) + 1
    return _add_payment(state, order, Payment(
        key=f"charge-{order.id}-{attempt}", kind="charge", order_id=order.id,
        amount=order.quote.total, per_line=order.quote.line_totals(), created_at=now))


def _start_refund(move: StartRefund, state: State, now: int) -> Payment:
    order = state.orders[move.order_id]
    number = sum(p.kind == "refund" for p in order.payments) + 1
    return _add_payment(state, order, Payment(
        key=f"refund-{order.id}-{number}", kind="refund", order_id=order.id,
        amount=sum(move.per_line), per_line=move.per_line, created_at=now))


def _release(move: Release, state: State):
    order = state.orders[move.order_id]
    for line in order.quote.lines:
        state.stock[line.sku] += line.qty
    for name in order.budgets:
        state.budgets[name] += 1
    state.orders[order.id] = order.model_copy(update={"hold": "released"})


def settle(state: State, key: str, outcome: str, at: int | None = None) -> Payment:
    """Record what the provider did with a call. A charge that applies consumes the order's stock."""
    order = state.orders[state.payment_orders[key]]
    payment = next(p for p in order.payments if p.key == key)
    settled = payment.model_copy(update={"state": outcome, "at": at})
    update = {"payments": tuple(settled if p.key == key else p for p in order.payments)}
    if outcome == "applied" and payment.kind == "charge":
        if order.hold != "held":
            raise AssertionError(f"charge applied for {order.id}, whose stock is {order.hold}")
        update["hold"] = "consumed"
    state.orders[order.id] = order.model_copy(update=update)
    return settled

