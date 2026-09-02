"""WalletService: the GREEN/YELLOW/RED classification (section 42) that
feeds every proposed spend through `PolicyEngine` before a single cent
moves — the model never calls `WalletStore.execute()` directly (section
43: "the LLM does not directly control wallet transactions").
"""
from __future__ import annotations

import logging
import uuid

from app.events.bus import EventBus
from app.events.models import Event, EventType
from app.policy.engine import PolicyEngine
from app.policy.models import Decision, PolicyRequest
from app.wallet.models import PolicyColor, WalletTransaction, WalletTransactionResult
from app.wallet.store import WalletStore

logger = logging.getLogger(__name__)

# Weekly/monthly spend at or above this fraction of the limit triggers a
# wallet.limit.warning even on an otherwise-approved transaction.
WARNING_FRACTION = 0.8


class WalletService:
    def __init__(self, store: WalletStore, policy_engine: PolicyEngine, event_bus: EventBus) -> None:
        self._store = store
        self._policy = policy_engine
        self._event_bus = event_bus

    async def propose_transaction(
        self, *, amount_usd: float, vendor: str, category: str, purpose: str, task_id: str | None = None
    ) -> WalletTransactionResult:
        account = await self._store.get_or_create_account()
        category_l, vendor_l = category.strip().lower(), vendor.strip().lower()

        blocked = category_l in {c.lower() for c in account.blocked_categories}
        approved = category_l in {c.lower() for c in account.approved_categories} or vendor_l in {
            v.lower() for v in account.approved_vendors
        }

        weekly_spent = await self._store.weekly_spent(account.id)
        monthly_spent = await self._store.monthly_spent(account.id)
        exceeds_limit = (
            amount_usd > account.per_transaction_limit_usd
            or weekly_spent + amount_usd > account.weekly_limit_usd
            or monthly_spent + amount_usd > account.monthly_limit_usd
        )

        if blocked:
            color = PolicyColor.RED
        elif exceeds_limit:
            color = PolicyColor.YELLOW  # section 41: may exceed ONLY with explicit approval
        elif approved:
            color = PolicyColor.GREEN
        else:
            color = PolicyColor.YELLOW  # new/unclear vendor or category

        tx_id = str(uuid.uuid4())

        if color == PolicyColor.RED:
            await self._store.create_transaction(
                WalletTransaction(
                    id=tx_id, wallet_id=account.id, amount_usd=amount_usd, vendor=vendor, category=category,
                    purpose=purpose, task_id=task_id, policy_decision=color, status="REJECTED",
                )
            )
            await self._event_bus.publish(
                Event(
                    type=EventType.WALLET_LIMIT_BLOCKED,
                    task_id=task_id,
                    payload={"transaction_id": tx_id, "vendor": vendor, "category": category, "amount_usd": amount_usd, "reason": "blocked category"},
                )
            )
            return WalletTransactionResult(approved=False, transaction_id=tx_id, reason="blocked category — never automatically executed", balance_usd=account.balance_usd, policy_decision=color)

        request = PolicyRequest(
            kind="wallet_transaction",
            title=f"${amount_usd:.2f} to {vendor} ({category})",
            description=purpose,
            risk="low" if color == PolicyColor.GREEN else "medium",
            reversible=True,
            hard_block=False,
            task_id=task_id,
            cost_usd=amount_usd,
            payload={"vendor": vendor, "category": category, "amount_usd": amount_usd, "transaction_id": tx_id},
            preapproval_key=f"wallet:{category_l}",
        )
        decision = await self._policy.evaluate(request)

        if decision.decision != Decision.ALLOW:
            await self._store.create_transaction(
                WalletTransaction(
                    id=tx_id, wallet_id=account.id, amount_usd=amount_usd, vendor=vendor, category=category,
                    purpose=purpose, task_id=task_id, policy_decision=color, status="REJECTED", approval_id=decision.approval_id,
                )
            )
            if exceeds_limit:
                await self._event_bus.publish(
                    Event(type=EventType.WALLET_LIMIT_BLOCKED, task_id=task_id, payload={"transaction_id": tx_id, "reason": decision.reason})
                )
            return WalletTransactionResult(approved=False, transaction_id=tx_id, reason=decision.reason, balance_usd=account.balance_usd, policy_decision=color)

        await self._store.create_transaction(
            WalletTransaction(
                id=tx_id, wallet_id=account.id, amount_usd=amount_usd, vendor=vendor, category=category,
                purpose=purpose, task_id=task_id, policy_decision=color, status="APPROVED", approval_id=decision.approval_id,
            )
        )
        new_balance = await self._store.execute(tx_id, account.id, amount_usd)

        await self._event_bus.publish(
            Event(
                type=EventType.WALLET_TRANSACTION_CREATED,
                task_id=task_id,
                payload={"transaction_id": tx_id, "vendor": vendor, "category": category, "amount_usd": amount_usd, "balance_usd": new_balance},
            )
        )

        new_weekly = weekly_spent + amount_usd
        new_monthly = monthly_spent + amount_usd
        if new_weekly >= account.weekly_limit_usd * WARNING_FRACTION or new_monthly >= account.monthly_limit_usd * WARNING_FRACTION:
            await self._event_bus.publish(
                Event(
                    type=EventType.WALLET_LIMIT_WARNING,
                    task_id=task_id,
                    payload={
                        "weekly_spent": new_weekly, "weekly_limit": account.weekly_limit_usd,
                        "monthly_spent": new_monthly, "monthly_limit": account.monthly_limit_usd,
                    },
                )
            )

        return WalletTransactionResult(approved=True, transaction_id=tx_id, reason=decision.reason, balance_usd=new_balance, policy_decision=color)
