"""Plant known bugs in a copy of an arm and check that each suite catches them.

This measures the strength of the acceptance suite (the audit's oracle)
and of the arm's own suite. It is not part of any gate.

    uv run python checks/planted_bugs.py            # from m1/
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

M1 = Path(__file__).resolve().parent.parent
PROJECT = M1.parent

S = "checkout/service.py"
ARM_A = {
    "charged_at_local_time": (S, "order.charged_at = outcome.at", "order.charged_at = self.clock.now"),
    "no_idempotency": (S, "record = self.store.get_request(request_id)", "record = None"),
    "no_hold_check_on_pay": (S, "order.status == OrderStatus.RESERVED and hold_lapsed(order, self.clock.now)",
                             "False"),
    "expiry_keeps_stock": (S, "self.store.release_stock(order)", "pass"),
    "window_exclusive": ("checkout/policies.py", "<= REFUND_WINDOW_SECONDS", "< REFUND_WINDOW_SECONDS"),
    "window_ignored": (S, "if not refund_window_open(order, self.clock.now):", "if False:"),
    "reconcile_in_flight": (
        S,
        'for payment in self.store.payments_in_state("unknown"):\n'
        '            if payment.state != "unknown":  # settled by a job run during an earlier retry\n'
        "                continue\n",
        'for payment in [p for p in self.store.payments.values() if p.state in ("unknown", "in_flight")]:\n'),
    "declined_refund_stays_refunding": (S, "        else:\n            order.status = OrderStatus.PAID",
                                        "        else:\n            pass"),
    "same_charge_key_every_attempt": (S, 'attempt = len(self.store.payments_for(order.id, "charge")) + 1',
                                      "attempt = 1"),
    "in_progress_reexecutes": (S, 'return record.response or rejected("in_progress")',
                               "if record.response: return record.response"),
    "pricing_discount_3plus": ("checkout/pricing.py", "prices[sku] * qty", "prices[sku] * qty - (qty > 2)"),
    "refund_not_scoped_to_customer": (
        S,
        "    def _refund(self, customer: str, order_id: str) -> Response:\n"
        "        order = self.store.find_order(order_id, customer)",
        "    def _refund(self, customer: str, order_id: str) -> Response:\n"
        "        order = self.store.orders.get(order_id)"),
    "expire_paying_orders": (S, "if order.status == OrderStatus.RESERVED and hold_lapsed(order, now):",
                             "if order.status in (OrderStatus.RESERVED, OrderStatus.PAYING) "
                             "and hold_lapsed(order, now):"),
}
# Not a bug under world.py's fault model: a lost request never arrives
# later, so retrying with a new key cannot double-charge. Kept to show it.
NOT_A_BUG_HERE = {
    "retry_with_new_key": (S, 'payment.state = "in_flight"\n                outcome = self.gateway.send(payment)',
                           'payment.state = "in_flight"\n                payment.key += "r"\n'
                           "                outcome = self.gateway.send(payment)"),
}


def pytest_fails(args, cwd) -> tuple[bool, str]:
    out = subprocess.run(["uv", "run", "--project", str(PROJECT), "pytest", "-q", "-x", *args],
                         cwd=cwd, capture_output=True, text=True)
    first = next((line.split(" - ")[0].removeprefix("FAILED ") for line in out.stdout.splitlines()
                  if line.startswith("FAILED")), "")
    return out.returncode != 0, first


def main(arm="arm_a", mutants=None):
    mutants = mutants or {**ARM_A, **NOT_A_BUG_HERE}
    print(f"{'planted bug':34} {'acceptance':11} {'own suite':10} first failing own test")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for name in ("spec.py", "world.py", "pytest.ini", "acceptance"):
            src = M1 / name
            (shutil.copytree if src.is_dir() else shutil.copy)(src, tmp / name)
        for name, (path, old, new) in mutants.items():
            copy = tmp / arm
            if copy.exists():
                shutil.rmtree(copy)
            shutil.copytree(M1 / arm, copy,
                            ignore=shutil.ignore_patterns("__pycache__", ".testmondata*", ".pytest_cache"))
            target = copy / path
            source = target.read_text()
            if old not in source:
                sys.exit(f"{name}: anchor text not found in {path}")
            target.write_text(source.replace(old, new, 1))
            acc, _ = pytest_fails(["acceptance", "--arm", arm.removeprefix("arm_")], tmp)
            own, first = pytest_fails([], copy)
            print(f"{name:34} {'caught' if acc else 'MISSED':11} {'caught' if own else 'MISSED':10} {first}")


if __name__ == "__main__":
    main()
