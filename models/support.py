"""Support subscription lookup helpers."""
from __future__ import annotations

from models.db import get_conn, ph

ACTIVE_SUPPORT_STATUSES = ("active", "trialing")


def _identity_clause(user_id: int | None, email: str):
    email = (email or "").strip().lower()
    if user_id and email:
        return f"(user_id = {ph()} OR lower(customer_email) = lower({ph()}))", (user_id, email)
    if user_id:
        return f"user_id = {ph()}", (user_id,)
    if email:
        return f"lower(customer_email) = lower({ph()})", (email,)
    return "1 = 0", ()


def get_active_support_subscription(user_id: int | None, email: str):
    """Return the best active monthly support subscription for a user identity."""
    identity_sql, identity_params = _identity_clause(user_id, email)
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT *
            FROM support_subscriptions
            WHERE {identity_sql}
              AND status IN ({ph(len(ACTIVE_SUPPORT_STATUSES))})
            ORDER BY
                CASE lower(tier)
                    WHEN 'gold' THEN 1
                    WHEN 'silver' THEN 2
                    WHEN 'bronze' THEN 3
                    ELSE 4
                END,
                updated_at DESC
            LIMIT 1
            """,
            (*identity_params, *ACTIVE_SUPPORT_STATUSES),
        )
        return cur.fetchone()


def get_support_subscription_for_billing(user_id: int | None, email: str):
    """Return the newest known support subscription with a Stripe customer id."""
    identity_sql, identity_params = _identity_clause(user_id, email)
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT *
            FROM support_subscriptions
            WHERE {identity_sql}
              AND stripe_customer_id != ''
            ORDER BY
                CASE
                    WHEN status IN ({ph(len(ACTIVE_SUPPORT_STATUSES))}) THEN 1
                    ELSE 2
                END,
                updated_at DESC
            LIMIT 1
            """,
            (*identity_params, *ACTIVE_SUPPORT_STATUSES),
        )
        return cur.fetchone()
