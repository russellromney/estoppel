"""Payment provider client: sends charges and refunds, maps results to outcomes."""

from checkout.models import Outcome, Payment
from world import Applied, PaymentDeclined, PaymentTimeout, Provider


class PaymentGateway:
    def __init__(self, provider: Provider):
        self.provider = provider

    def send(self, payment: Payment) -> Outcome:
        call = self.provider.charge if payment.kind == "charge" else self.provider.refund
        try:
            receipt = call(payment.key, payment.customer, payment.order_id, payment.amount)
        except PaymentDeclined:
            return Outcome(status="declined")
        except PaymentTimeout:
            return Outcome(status="unknown")
        return Outcome(status="applied", at=receipt.at)

    def lookup(self, key: str) -> Outcome | None:
        """Outcome of an earlier call, or None if it never reached the provider."""
        found = self.provider.lookup(key)
        if isinstance(found, Applied):
            return Outcome(status="applied", at=found.at)
        if found == "declined":
            return Outcome(status="declined")
        return None
