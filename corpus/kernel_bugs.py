"""Kernel bug variants for E1. Each overrides one behaviour of Kernel.

IDs and predicted detection layers are pre-registered in
backlog/failure_corpus.md.
"""

from app.kernel import TTL, Effect, Kernel


class KB01_TrustPlannerStock(Kernel):
    """Skips the commit-time stock check: 'the planner already checked'."""
    version = "kernel@KB01"

    def check_stock(self, wanted):
        return True


class KB02_RetryWithNewOpId(Kernel):
    """Reconciles unknown effects by retrying under a fresh op_id, no lookup."""
    version = "kernel@KB02"

    def reconcile_one(self, effect):
        effect.status = "abandoned"
        op_id = self.next_id("op")
        self.effects[op_id] = Effect(op_id, effect.kind, effect.order_id,
                                     effect.amount, effect.recipient)


class KB03_RefundTimeoutIsFailure(Kernel):
    """Treats a refund timeout as a failure, returning the order to paid."""
    version = "kernel@KB03"

    def on_timeout(self, effect):
        if effect.kind == "refund":
            self.fail(effect)
        else:
            super().on_timeout(effect)


class KB04_ExpirePaying(Kernel):
    """Expiry also expires orders whose charge is in flight."""
    version = "kernel@KB04"

    def should_expire(self, order):
        return (order.status in ("reserved", "paying")
                and self.clock.now - order.reserved_at >= TTL)


class KB05_GrantNotConsumed(Kernel):
    """Grants are never marked used, so a duplicated commit applies twice."""
    version = "kernel@KB05"

    def consume(self, grant):
        pass


class KB06_ExpiryOffByOne(Kernel):
    """Expiry fires one tick period late (TTL + 60)."""
    version = "kernel@KB06"

    def should_expire(self, order):
        return order.status == "reserved" and self.clock.now - order.reserved_at >= TTL + 60


class KB08_DeclineLeavesPaying(Kernel):
    """A declined charge leaves the order stuck in 'paying'."""
    version = "kernel@KB08"

    def restore_after_failed_charge(self, order):
        pass


KERNEL_BUGS = {
    "KB01": KB01_TrustPlannerStock,
    "KB02": KB02_RetryWithNewOpId,
    "KB03": KB03_RefundTimeoutIsFailure,
    "KB04": KB04_ExpirePaying,
    "KB05": KB05_GrantNotConsumed,
    "KB06": KB06_ExpiryOffByOne,
    "KB08": KB08_DeclineLeavesPaying,
}
