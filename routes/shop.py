"""Shop routes."""
from __future__ import annotations

import re
import html as html_lib
from datetime import datetime, timezone
from urllib.parse import urljoin

from flask import Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from models.db import get_conn, is_postgres, ph
from models.support import get_support_subscription_for_billing
from email_service import email_configured, send_email
from security import rate_limit

try:
    import stripe
except ImportError:  # pragma: no cover - handled at runtime when dependencies are installed
    stripe = None

shop_bp = Blueprint("shop", __name__)

_PULSE_QUESTION_PRODUCT_KEY = "pulse_question"
_PULSE_QUESTION_AMOUNT_CENTS = 1000
_PULSE_QUESTION_CURRENCY = "cad"
_SUPPORT_RONPON_PRODUCT_KEY = "support_ronpon_productions"
_SUPPORT_RONPON_BRONZE_PRODUCT_KEY = "support_ronpon_recurring_bronze"
_SUPPORT_RONPON_SILVER_PRODUCT_KEY = "support_ronpon_recurring_silver"
_SUPPORT_RONPON_GOLD_PRODUCT_KEY = "support_ronpon_recurring_gold"
_SHOP_CATEGORY_ORDER = ("Ronpon Books", "The Pulse", "Support Ronpon Productions")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_SUPPORT_PRODUCTS = (
    {
        "slug": "one-time",
        "product_key": _SUPPORT_RONPON_PRODUCT_KEY,
        "kind": "One-time Support",
        "title": "Support Ronpon Productions",
        "description": (
            "Make a one-time pay-what-you-want contribution to help fund "
            "Ronpon games, videos, and new projects."
        ),
        "price": "Pay what you want",
        "image_filename": "Shop/Support Ronpon Productions.png",
        "action_label": "Choose Amount",
        "mode": "payment",
        "price_config": "STRIPE_SUPPORT_RONPON_PRICE_ID",
        "submit_type": "donate",
        "tier": "",
        "card_class": "shop-card-support shop-card-pay-what-you-want",
    },
    {
        "slug": "bronze",
        "product_key": _SUPPORT_RONPON_BRONZE_PRODUCT_KEY,
        "kind": "Recurring Support",
        "title": "Support Ronpon Productions - Bronze",
        "description": (
            "A monthly $5 contribution for keeping the whole Ronpon machine humming."
        ),
        "price": "$5/month",
        "image_filename": "Shop/Bronze Recurring.jpg",
        "action_label": "Join Bronze",
        "mode": "subscription",
        "price_config": "STRIPE_SUPPORT_RONPON_BRONZE_PRICE_ID",
        "tier": "bronze",
        "card_class": "shop-card-support shop-card-recurring shop-card-bronze",
    },
    {
        "slug": "silver",
        "product_key": _SUPPORT_RONPON_SILVER_PRODUCT_KEY,
        "kind": "Recurring Support",
        "title": "Support Ronpon Productions - Silver",
        "description": (
            "A monthly $10 contribution for backing bigger games, videos, and experiments."
        ),
        "price": "$10/month",
        "image_filename": "Shop/Silver Recurring.jpg",
        "action_label": "Join Silver",
        "mode": "subscription",
        "price_config": "STRIPE_SUPPORT_RONPON_SILVER_PRICE_ID",
        "tier": "silver",
        "card_class": "shop-card-support shop-card-recurring shop-card-silver",
    },
    {
        "slug": "gold",
        "product_key": _SUPPORT_RONPON_GOLD_PRODUCT_KEY,
        "kind": "Recurring Support",
        "title": "Support Ronpon Productions - Gold",
        "description": (
            "A monthly $20 contribution for giving Ronpon Productions extra room to grow."
        ),
        "price": "$20/month",
        "image_filename": "Shop/Gold Recurring.jpg",
        "action_label": "Join Gold",
        "mode": "subscription",
        "price_config": "STRIPE_SUPPORT_RONPON_GOLD_PRICE_ID",
        "tier": "gold",
        "card_class": "shop-card-support shop-card-recurring shop-card-gold",
    },
)
_SUPPORT_PRODUCTS_BY_SLUG = {product["slug"]: product for product in _SUPPORT_PRODUCTS}
_SUPPORT_PRODUCTS_BY_KEY = {product["product_key"]: product for product in _SUPPORT_PRODUCTS}
_SUPPORT_PRODUCT_KEYS = set(_SUPPORT_PRODUCTS_BY_KEY)
_SUPPORT_CURRENT_STATUSES = ("active", "trialing")
_SUPPORT_ATTENTION_STATUSES = ("past_due", "unpaid", "incomplete", "paused")
_SUPPORT_CANCELED_STATUSES = ("canceled", "incomplete_expired")
_PULSE_SUBMISSION_STATUSES = ("paid", "pending", "expired", "failed", "all")
_SUPPORT_STATUS_FILTERS = {
    "current": {"label": "Current", "statuses": _SUPPORT_CURRENT_STATUSES},
    "attention": {"label": "Needs Attention", "statuses": _SUPPORT_ATTENTION_STATUSES},
    "canceled": {"label": "Canceled", "statuses": _SUPPORT_CANCELED_STATUSES},
    "all": {"label": "All", "statuses": None},
}


def _support_product_cards():
    """Return display cards for Stripe-backed support products."""
    cards = []
    for product in _SUPPORT_PRODUCTS:
        cards.append(
            {
                "category": "Support Ronpon Productions",
                "kind": product["kind"],
                "title": product["title"],
                "description": product["description"],
                "price": product["price"],
                "image_url": url_for("serve_site_image", filename=product["image_filename"]),
                "image_alt": product["title"],
                "placeholder": "SUPPORT",
                "action_label": product["action_label"],
                "action_url": url_for("shop.support_checkout", support_slug=product["slug"]),
                "action_method": "post",
                "external": False,
                "card_class": product["card_class"],
            }
        )
    return cards


def _shop_products():
    """Return display data for the shop."""
    return [
        {
            "category": "Ronpon Books",
            "kind": "Picture Book",
            "title": "Make Someone Read You This Book",
            "description": (
                "A hilariously frustrating book to read aloud, that will have the "
                "kids rolling with laughter as you struggle."
            ),
            "price": "",
            "image_url": url_for("serve_site_image", filename="Shop/Make Someone Cover.jpg"),
            "placeholder": "READ",
            "action_label": "View on Amazon",
            "action_url": "https://www.amazon.ca/Make-Someone-Read-This-Book/dp/B0F4MTNYD5",
            "external": True,
        },
        {
            "category": "Ronpon Books",
            "kind": "Picture Book",
            "title": "Ronpon's Nursery Rhymes for Sarcastic A**holes",
            "description": (
                "Nursery rhymes for cynics who like to poke holes in things. "
                "For children of all ages."
            ),
            "price": "",
            "image_url": url_for("serve_site_image", filename="Shop/Nursery Rhymes Cover.jpg"),
            "placeholder": "RHYMES",
            "action_label": "View on Amazon",
            "action_url": "https://www.amazon.ca/Ronpons-Nursery-Rhymes-Sarcastic-holes/dp/B0C9SBMF8N",
            "external": True,
        },
        {
            "category": "The Pulse",
            "kind": "The Pulse",
            "title": "Write Your Own Question for The Pulse*",
            "description": (
                "Submit a multiple-choice poll question for possible use in The Pulse, "
                "the man-on-the-street game show segment where people predict poll answers."
            ),
            "price": "$10.00 CAD",
            "image_url": url_for("serve_site_image", filename="Shop/Pulse Question.png"),
            "placeholder": "PULSE",
            "action_label": "Write a Question",
            "action_url": url_for("shop.pulse_question"),
            "external": False,
            "featured": True,
        },
        *_support_product_cards(),
    ]


def _shop_categories():
    """Return shop products grouped in display order."""
    products_by_category = {category: [] for category in _SHOP_CATEGORY_ORDER}
    for product in _shop_products():
        products_by_category.setdefault(product["category"], []).append(product)

    categories = []
    for category in _SHOP_CATEGORY_ORDER:
        products = products_by_category.get(category, [])
        if products:
            categories.append({"name": category, "products": products})
    return categories


def _is_admin() -> bool:
    return current_user.is_authenticated and current_user.is_admin


def _stripe_configured() -> bool:
    return bool(stripe and current_app.config.get("STRIPE_SECRET_KEY"))


def _set_stripe_key() -> None:
    if not stripe:
        raise RuntimeError("Stripe Python package is not installed.")
    stripe.api_key = current_app.config["STRIPE_SECRET_KEY"]


def _external_url(endpoint: str, **values) -> str:
    public_origin = current_app.config.get("PUBLIC_ORIGIN", "")
    if public_origin:
        return urljoin(f"{public_origin}/", url_for(endpoint, **values).lstrip("/"))
    scheme = current_app.config.get("PREFERRED_URL_SCHEME") or request.scheme
    return url_for(endpoint, _external=True, _scheme=scheme, **values)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _row_to_dict(row) -> dict:
    if not row:
        return {}
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    return dict(row)


def _field(name: str, max_length: int) -> str:
    return request.form.get(name, "").strip()[:max_length]


def _pulse_question_payload() -> tuple[dict, list[str]]:
    payload = {
        "question": _field("question", 500),
        "option_a": _field("option_a", 160),
        "option_b": _field("option_b", 160),
        "option_c": _field("option_c", 160),
        "option_d": _field("option_d", 160),
        "display_name": _field("display_name", 100),
        "anonymous": bool(request.form.get("anonymous")),
        "customer_email": _field("customer_email", 254).lower(),
        "notes": _field("notes", 700),
    }
    errors = []
    if not payload["question"]:
        errors.append("Poll question is required.")
    required_options = [payload["option_a"], payload["option_b"]]
    if any(not option for option in required_options):
        errors.append("At least options A and B are required.")
    if not payload["customer_email"] or not _EMAIL_RE.fullmatch(payload["customer_email"]):
        errors.append("Enter a valid email address.")
    return payload, errors


def _insert_pulse_question_order(payload: dict) -> int:
    user_id = current_user.id if current_user.is_authenticated else None
    with get_conn() as conn:
        cur = conn.cursor()
        insert_sql = f"""
            INSERT INTO shop_orders (
                user_id, product_key, status, amount_cents, currency, customer_email,
                question, option_a, option_b, option_c, option_d, display_name, anonymous, notes
            ) VALUES ({ph(14)})
            """
        params = (
            user_id,
            _PULSE_QUESTION_PRODUCT_KEY,
            "pending",
            _PULSE_QUESTION_AMOUNT_CENTS,
            _PULSE_QUESTION_CURRENCY,
            payload["customer_email"],
            payload["question"],
            payload["option_a"],
            payload["option_b"],
            payload["option_c"],
            payload["option_d"],
            payload["display_name"],
            payload["anonymous"],
            payload["notes"],
        )
        if is_postgres():
            cur.execute(f"{insert_sql} RETURNING id", params)
            return cur.fetchone()[0]
        cur.execute(insert_sql, params)
        return cur.lastrowid


def _update_order_checkout_session(order_id: int, session_id: str) -> None:
    with get_conn() as conn:
        conn.cursor().execute(
            f"UPDATE shop_orders SET stripe_checkout_session_id = {ph()} WHERE id = {ph()}",
            (session_id, order_id),
        )


def _fetch_order_by_id(order_id: int):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT * FROM shop_orders WHERE id = {ph()}",
            (order_id,),
        )
        return cur.fetchone()


def _mark_order_paid(session):
    metadata = session.get("metadata") or {}
    order_id = session.get("client_reference_id") or metadata.get("order_id")
    if not order_id:
        return None
    try:
        order_id = int(order_id)
    except (TypeError, ValueError):
        return None

    customer_details = session.get("customer_details") or {}
    email = customer_details.get("email") or session.get("customer_email") or ""
    payment_intent_id = session.get("payment_intent") or ""
    paid_at = _utc_now_iso()

    with get_conn() as conn:
        conn.cursor().execute(
            f"""
            UPDATE shop_orders
            SET status = {ph()},
                stripe_checkout_session_id = {ph()},
                stripe_payment_intent_id = {ph()},
                customer_email = COALESCE(NULLIF({ph()}, ''), customer_email),
                paid_at = COALESCE(paid_at, {ph()})
            WHERE id = {ph()} AND product_key = {ph()}
            """,
            (
                "paid",
                session.get("id", ""),
                payment_intent_id,
                email,
                paid_at,
                order_id,
                _PULSE_QUESTION_PRODUCT_KEY,
            ),
        )
    return _fetch_order_by_id(order_id)


def _set_order_email_sent_at(order_id: int, column: str) -> None:
    if column not in {"customer_email_sent_at", "admin_email_sent_at"}:
        raise ValueError("Invalid email timestamp column.")
    with get_conn() as conn:
        conn.cursor().execute(
            f"UPDATE shop_orders SET {column} = {ph()} WHERE id = {ph()}",
            (_utc_now_iso(), order_id),
        )


def _order_option_lines(order: dict) -> list[str]:
    options = [
        ("A", order.get("option_a", "")),
        ("B", order.get("option_b", "")),
        ("C", order.get("option_c", "")),
        ("D", order.get("option_d", "")),
    ]
    return [f"{label}. {value}" for label, value in options if value]


def _paragraph_html(*paragraphs: str) -> str:
    return "\n".join(
        f"<p>{html_lib.escape(paragraph).replace(chr(10), '<br>')}</p>"
        for paragraph in paragraphs
        if paragraph
    )


def _send_paid_pulse_question_emails(order) -> None:
    if not order or not email_configured():
        return

    order_data = _row_to_dict(order)
    order_id = int(order_data["id"])
    question = order_data.get("question", "")
    option_text = "\n".join(_order_option_lines(order_data))

    if order_data.get("customer_email") and not order_data.get("customer_email_sent_at"):
        text = (
            "Thanks for submitting a question for The Pulse.\n\n"
            "Your payment went through, and your question is queued for review.\n\n"
            f"Question:\n{question}\n\n"
            f"Options:\n{option_text}\n\n"
            "Submissions may be edited for clarity or conciseness before use."
        )
        html_body = _paragraph_html(
            "Thanks for submitting a question for The Pulse.",
            "Your payment went through, and your question is queued for review.",
            f"Question:\n{question}",
            f"Options:\n{option_text}",
            "Submissions may be edited for clarity or conciseness before use.",
        )
        try:
            if send_email(
                order_data["customer_email"],
                "Your Pulse question is queued for review",
                text,
                html_body,
            ):
                _set_order_email_sent_at(order_id, "customer_email_sent_at")
        except Exception:
            current_app.logger.exception("Pulse question customer email failed.")

    admin_email = current_app.config.get("ADMIN_EMAIL", "")
    if admin_email and not order_data.get("admin_email_sent_at"):
        submissions_url = _external_url("shop.pulse_question_submissions")
        display_name = order_data.get("display_name", "") or "Not provided"
        notes = order_data.get("notes", "") or "None"
        text = (
            "New paid Pulse question submission.\n\n"
            f"Order ID: {order_id}\n"
            f"Customer email: {order_data.get('customer_email', '')}\n"
            f"Display name: {display_name}\n\n"
            f"Question:\n{question}\n\n"
            f"Options:\n{option_text}\n\n"
            f"Notes:\n{notes}\n\n"
            f"Review submissions:\n{submissions_url}"
        )
        html_body = _paragraph_html(
            "New paid Pulse question submission.",
            (
                f"Order ID: {order_id}\n"
                f"Customer email: {order_data.get('customer_email', '')}\n"
                f"Display name: {display_name}"
            ),
            f"Question:\n{question}",
            f"Options:\n{option_text}",
            f"Notes:\n{notes}",
            f"Review submissions:\n{submissions_url}",
        )
        try:
            if send_email(admin_email, "New paid Pulse question submission", text, html_body):
                _set_order_email_sent_at(order_id, "admin_email_sent_at")
        except Exception:
            current_app.logger.exception("Pulse question admin email failed.")


def _set_order_status_by_session(session_id: str, status: str) -> None:
    if not session_id:
        return
    with get_conn() as conn:
        conn.cursor().execute(
            f"""
            UPDATE shop_orders
            SET status = {ph()}
            WHERE stripe_checkout_session_id = {ph()} AND status != {ph()}
            """,
            (status, session_id, "paid"),
        )


def _fetch_order_by_session(session_id: str):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT * FROM shop_orders WHERE stripe_checkout_session_id = {ph()}",
            (session_id,),
        )
        return cur.fetchone()


def _safe_fetch_order_by_session(session_id: str):
    try:
        return _fetch_order_by_session(session_id)
    except Exception:
        current_app.logger.exception(
            "Pulse question order lookup failed for session %s",
            session_id,
        )
        return None


def _sync_pending_pulse_question_orders(limit: int = 25) -> int:
    try:
        if not _stripe_configured():
            return 0

        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                f"""
                SELECT id, stripe_checkout_session_id
                FROM shop_orders
                WHERE product_key = {ph()}
                  AND status = {ph()}
                  AND stripe_checkout_session_id != ''
                ORDER BY created_at DESC
                LIMIT {ph()}
                """,
                (_PULSE_QUESTION_PRODUCT_KEY, "pending", limit),
            )
            pending_orders = cur.fetchall()

        synced = 0
        _set_stripe_key()
        for order in pending_orders:
            session_id = order["stripe_checkout_session_id"]
            try:
                checkout_session = stripe.checkout.Session.retrieve(session_id)
                metadata = _stripe_value(checkout_session, "metadata", {}) or {}
                if metadata.get("product_key") != _PULSE_QUESTION_PRODUCT_KEY:
                    continue

                payment_status = _stripe_value(checkout_session, "payment_status", "")
                session_status = _stripe_value(checkout_session, "status", "")
                if payment_status in {"paid", "no_payment_required"}:
                    paid_order = _mark_order_paid(checkout_session)
                    _send_paid_pulse_question_emails(paid_order)
                    synced += 1
                elif session_status == "expired":
                    _set_order_status_by_session(session_id, "expired")
            except Exception:
                current_app.logger.exception(
                    "Pending Pulse question Stripe sync failed for session %s",
                    session_id,
                )
        return synced
    except Exception:
        current_app.logger.exception("Pending Pulse question sync could not run.")
        return 0


def _pulse_submission_status_tabs(active_status: str):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT status, COUNT(*)
            FROM shop_orders
            WHERE product_key = {ph()}
            GROUP BY status
            """,
            (_PULSE_QUESTION_PRODUCT_KEY,),
        )
        status_counts = {row[0]: row[1] for row in cur.fetchall()}

    total = sum(status_counts.values())
    return [
        {
            "key": status,
            "label": status.title(),
            "count": total if status == "all" else status_counts.get(status, 0),
            "active": status == active_status,
        }
        for status in _PULSE_SUBMISSION_STATUSES
    ]


def _line_item() -> dict:
    price_id = current_app.config.get("STRIPE_PULSE_QUESTION_PRICE_ID", "")
    if price_id:
        return {"price": price_id, "quantity": 1}
    return {
        "price_data": {
            "currency": _PULSE_QUESTION_CURRENCY,
            "unit_amount": _PULSE_QUESTION_AMOUNT_CENTS,
            "product_data": {
                "name": "Write Your Own Question for The Pulse",
                "description": "Paid multiple-choice question submission for The Pulse.",
            },
        },
        "quantity": 1,
    }


def _support_price_id(product: dict) -> str:
    return current_app.config.get(product["price_config"], "").strip()


def _support_product_by_price_id(price_id: str):
    if not price_id:
        return None
    for product in _SUPPORT_PRODUCTS:
        if _support_price_id(product) == price_id:
            return product
    return None


def _stripe_value(obj, key: str, default=None):
    if not obj:
        return default
    if hasattr(obj, "get"):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _stripe_id(value) -> str:
    if not value:
        return ""
    if isinstance(value, str):
        return value
    return str(_stripe_value(value, "id", "") or "")


def _stripe_timestamp(value):
    if not value:
        return None
    try:
        return datetime.fromtimestamp(int(value), timezone.utc).isoformat(timespec="seconds")
    except (TypeError, ValueError, OSError):
        return None


def _format_money(amount_cents: int | str | None, currency: str = "cad") -> str:
    try:
        cents = int(amount_cents or 0)
    except (TypeError, ValueError):
        cents = 0
    return f"${cents / 100:.2f} {(currency or 'cad').upper()}"


def _support_product_from_metadata(metadata: dict):
    return _SUPPORT_PRODUCTS_BY_KEY.get((metadata or {}).get("product_key", ""))


def _support_product_from_session(session):
    metadata = _stripe_value(session, "metadata", {}) or {}
    return _support_product_from_metadata(metadata)


def _support_subscription_price(subscription):
    items = _stripe_value(_stripe_value(subscription, "items", {}), "data", []) or []
    if not items:
        return {}
    return _stripe_value(items[0], "price", {}) or {}


def _retrieve_stripe_subscription(subscription_id: str):
    if not subscription_id or not stripe:
        return None
    _set_stripe_key()
    return stripe.Subscription.retrieve(subscription_id)


def _retrieve_stripe_customer(customer_id: str):
    if not customer_id or not stripe:
        return None
    _set_stripe_key()
    return stripe.Customer.retrieve(customer_id)


def _resolve_support_user_id(user_id_value, email: str):
    try:
        user_id = int(user_id_value) if user_id_value else None
    except (TypeError, ValueError):
        user_id = None

    with get_conn() as conn:
        cur = conn.cursor()
        if user_id:
            cur.execute(f"SELECT id FROM users WHERE id = {ph()}", (user_id,))
            row = cur.fetchone()
            if row:
                return int(row["id"] if hasattr(row, "keys") else row[0])

        email = (email or "").strip().lower()
        if email:
            cur.execute(f"SELECT id FROM users WHERE lower(email) = lower({ph()})", (email,))
            row = cur.fetchone()
            if row:
                return int(row["id"] if hasattr(row, "keys") else row[0])
    return None


def _build_support_subscription_record(session=None, subscription=None):
    session_metadata = _stripe_value(session, "metadata", {}) or {}
    subscription_metadata = _stripe_value(subscription, "metadata", {}) or {}
    metadata = {**session_metadata, **subscription_metadata}

    price = _support_subscription_price(subscription) if subscription else {}
    price_id = _stripe_id(price)
    product = _support_product_by_price_id(price_id)
    if not product:
        product = _SUPPORT_PRODUCTS_BY_KEY.get(metadata.get("product_key", ""))
    if not product or product["mode"] != "subscription":
        return None

    subscription_id = _stripe_id(subscription) or _stripe_id(_stripe_value(session, "subscription", ""))
    if not subscription_id:
        return None

    customer_id = _stripe_id(_stripe_value(subscription, "customer", "")) or _stripe_id(_stripe_value(session, "customer", ""))
    customer_details = _stripe_value(session, "customer_details", {}) or {}
    customer = None
    email = (
        _stripe_value(customer_details, "email", "")
        or _stripe_value(session, "customer_email", "")
        or metadata.get("customer_email", "")
    )
    name = _stripe_value(customer_details, "name", "") or metadata.get("customer_name", "")
    if customer_id and (not email or not name):
        try:
            customer = _retrieve_stripe_customer(customer_id)
        except Exception:
            current_app.logger.exception("Stripe Customer lookup failed for support subscription.")
        if customer:
            email = email or _stripe_value(customer, "email", "")
            name = name or _stripe_value(customer, "name", "")

    user_id = _resolve_support_user_id(
        _stripe_value(session, "client_reference_id", "") or metadata.get("user_id", ""),
        email,
    )

    amount_cents = _stripe_value(price, "unit_amount", 0) or 0
    try:
        amount_cents = int(amount_cents)
    except (TypeError, ValueError):
        amount_cents = 0

    return {
        "user_id": user_id,
        "tier": product.get("tier", ""),
        "status": _stripe_value(subscription, "status", "") if subscription else "active",
        "customer_email": (email or "").strip().lower(),
        "customer_name": name or "",
        "stripe_customer_id": customer_id,
        "stripe_subscription_id": subscription_id,
        "stripe_checkout_session_id": _stripe_id(session),
        "stripe_price_id": price_id or _support_price_id(product),
        "amount_cents": amount_cents,
        "currency": (_stripe_value(price, "currency", "") or "cad").lower(),
        "current_period_start": _stripe_timestamp(_stripe_value(subscription, "current_period_start", "")),
        "current_period_end": _stripe_timestamp(_stripe_value(subscription, "current_period_end", "")),
        "cancel_at_period_end": bool(_stripe_value(subscription, "cancel_at_period_end", False)),
        "canceled_at": _stripe_timestamp(_stripe_value(subscription, "canceled_at", "")),
        "updated_at": _utc_now_iso(),
    }


def _fetch_support_subscription_by_stripe_id(subscription_id: str):
    if not subscription_id:
        return None
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT * FROM support_subscriptions WHERE stripe_subscription_id = {ph()}",
            (subscription_id,),
        )
        return cur.fetchone()


def _set_support_subscription_admin_email_sent_at(subscription_id: str) -> None:
    if not subscription_id:
        return
    with get_conn() as conn:
        conn.cursor().execute(
            f"UPDATE support_subscriptions SET admin_email_sent_at = {ph()} WHERE stripe_subscription_id = {ph()}",
            (_utc_now_iso(), subscription_id),
        )


def _upsert_support_subscription(record: dict):
    if not record or not record.get("stripe_subscription_id"):
        return None

    columns = (
        "user_id",
        "tier",
        "status",
        "customer_email",
        "customer_name",
        "stripe_customer_id",
        "stripe_subscription_id",
        "stripe_checkout_session_id",
        "stripe_price_id",
        "amount_cents",
        "currency",
        "current_period_start",
        "current_period_end",
        "cancel_at_period_end",
        "canceled_at",
        "updated_at",
    )
    values = tuple(record.get(column) for column in columns)
    with get_conn() as conn:
        conn.cursor().execute(
            f"""
            INSERT INTO support_subscriptions ({", ".join(columns)})
            VALUES ({ph(len(columns))})
            ON CONFLICT (stripe_subscription_id) DO UPDATE SET
                user_id = COALESCE(excluded.user_id, support_subscriptions.user_id),
                tier = COALESCE(NULLIF(excluded.tier, ''), support_subscriptions.tier),
                status = COALESCE(NULLIF(excluded.status, ''), support_subscriptions.status),
                customer_email = COALESCE(NULLIF(excluded.customer_email, ''), support_subscriptions.customer_email),
                customer_name = COALESCE(NULLIF(excluded.customer_name, ''), support_subscriptions.customer_name),
                stripe_customer_id = COALESCE(NULLIF(excluded.stripe_customer_id, ''), support_subscriptions.stripe_customer_id),
                stripe_checkout_session_id = COALESCE(NULLIF(excluded.stripe_checkout_session_id, ''), support_subscriptions.stripe_checkout_session_id),
                stripe_price_id = COALESCE(NULLIF(excluded.stripe_price_id, ''), support_subscriptions.stripe_price_id),
                amount_cents = CASE
                    WHEN excluded.amount_cents > 0 THEN excluded.amount_cents
                    ELSE support_subscriptions.amount_cents
                END,
                currency = COALESCE(NULLIF(excluded.currency, ''), support_subscriptions.currency),
                current_period_start = COALESCE(excluded.current_period_start, support_subscriptions.current_period_start),
                current_period_end = COALESCE(excluded.current_period_end, support_subscriptions.current_period_end),
                cancel_at_period_end = excluded.cancel_at_period_end,
                canceled_at = excluded.canceled_at,
                updated_at = excluded.updated_at
            """,
            values,
        )
    return _fetch_support_subscription_by_stripe_id(record["stripe_subscription_id"])


def _support_payment_price_id(session, product: dict) -> str:
    return _stripe_id(_stripe_value(session, "price", "")) or _support_price_id(product)


def _build_support_payment_record(session, product: dict):
    if not session or not product or product["mode"] != "payment":
        return None

    metadata = _stripe_value(session, "metadata", {}) or {}
    customer_details = _stripe_value(session, "customer_details", {}) or {}
    email = (
        _stripe_value(customer_details, "email", "")
        or _stripe_value(session, "customer_email", "")
        or metadata.get("customer_email", "")
    )
    name = _stripe_value(customer_details, "name", "") or metadata.get("customer_name", "")
    customer_id = _stripe_id(_stripe_value(session, "customer", ""))
    user_id = _resolve_support_user_id(
        _stripe_value(session, "client_reference_id", "") or metadata.get("user_id", ""),
        email,
    )
    amount_cents = _stripe_value(session, "amount_total", 0) or 0
    try:
        amount_cents = int(amount_cents)
    except (TypeError, ValueError):
        amount_cents = 0

    status = _stripe_value(session, "payment_status", "") or _stripe_value(session, "status", "")
    paid_at = _utc_now_iso() if status in {"paid", "complete", "no_payment_required"} else None

    return {
        "user_id": user_id,
        "product_key": product["product_key"],
        "support_slug": product["slug"],
        "customer_email": (email or "").strip().lower(),
        "customer_name": name or "",
        "stripe_customer_id": customer_id,
        "stripe_checkout_session_id": _stripe_id(session),
        "stripe_payment_intent_id": _stripe_id(_stripe_value(session, "payment_intent", "")),
        "stripe_price_id": _support_payment_price_id(session, product),
        "amount_cents": amount_cents,
        "currency": (_stripe_value(session, "currency", "") or "cad").lower(),
        "status": status,
        "paid_at": paid_at,
        "updated_at": _utc_now_iso(),
    }


def _fetch_support_payment_by_session(session_id: str):
    if not session_id:
        return None
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT * FROM support_payments WHERE stripe_checkout_session_id = {ph()}",
            (session_id,),
        )
        return cur.fetchone()


def _safe_fetch_support_payment_by_session(session_id: str):
    try:
        return _fetch_support_payment_by_session(session_id)
    except Exception:
        current_app.logger.exception(
            "Support payment lookup failed for session %s",
            session_id,
        )
        return None


def _set_support_payment_admin_email_sent_at(session_id: str) -> None:
    if not session_id:
        return
    with get_conn() as conn:
        conn.cursor().execute(
            f"UPDATE support_payments SET admin_email_sent_at = {ph()} WHERE stripe_checkout_session_id = {ph()}",
            (_utc_now_iso(), session_id),
        )


def _upsert_support_payment(record: dict):
    if not record or not record.get("stripe_checkout_session_id"):
        return None

    columns = (
        "user_id",
        "product_key",
        "support_slug",
        "customer_email",
        "customer_name",
        "stripe_customer_id",
        "stripe_checkout_session_id",
        "stripe_payment_intent_id",
        "stripe_price_id",
        "amount_cents",
        "currency",
        "status",
        "paid_at",
        "updated_at",
    )
    values = tuple(record.get(column) for column in columns)
    with get_conn() as conn:
        conn.cursor().execute(
            f"""
            INSERT INTO support_payments ({", ".join(columns)})
            VALUES ({ph(len(columns))})
            ON CONFLICT (stripe_checkout_session_id) DO UPDATE SET
                user_id = COALESCE(excluded.user_id, support_payments.user_id),
                product_key = COALESCE(NULLIF(excluded.product_key, ''), support_payments.product_key),
                support_slug = COALESCE(NULLIF(excluded.support_slug, ''), support_payments.support_slug),
                customer_email = COALESCE(NULLIF(excluded.customer_email, ''), support_payments.customer_email),
                customer_name = COALESCE(NULLIF(excluded.customer_name, ''), support_payments.customer_name),
                stripe_customer_id = COALESCE(NULLIF(excluded.stripe_customer_id, ''), support_payments.stripe_customer_id),
                stripe_payment_intent_id = COALESCE(NULLIF(excluded.stripe_payment_intent_id, ''), support_payments.stripe_payment_intent_id),
                stripe_price_id = COALESCE(NULLIF(excluded.stripe_price_id, ''), support_payments.stripe_price_id),
                amount_cents = CASE
                    WHEN excluded.amount_cents > 0 THEN excluded.amount_cents
                    ELSE support_payments.amount_cents
                END,
                currency = COALESCE(NULLIF(excluded.currency, ''), support_payments.currency),
                status = COALESCE(NULLIF(excluded.status, ''), support_payments.status),
                paid_at = COALESCE(excluded.paid_at, support_payments.paid_at),
                updated_at = excluded.updated_at
            """,
            values,
        )
    return _fetch_support_payment_by_session(record["stripe_checkout_session_id"])


def _support_admin_customer_label(record: dict) -> str:
    name = record.get("customer_name", "")
    email = record.get("customer_email", "")
    if name and email:
        return f"{name} <{email}>"
    return name or email or "Not provided"


def _send_support_payment_admin_email(payment, product: dict) -> None:
    if not payment or not product or not email_configured():
        return

    payment_data = _row_to_dict(payment)
    admin_email = current_app.config.get("ADMIN_EMAIL", "")
    if not admin_email or payment_data.get("admin_email_sent_at"):
        return

    supporters_url = _external_url("shop.supporters")
    amount = _format_money(payment_data.get("amount_cents"), payment_data.get("currency", "cad"))
    text = (
        "New one-time support payment.\n\n"
        f"Product: {product['title']}\n"
        f"Amount: {amount}\n"
        f"Customer: {_support_admin_customer_label(payment_data)}\n"
        f"Status: {payment_data.get('status', '') or 'unknown'}\n\n"
        f"Stripe session: {payment_data.get('stripe_checkout_session_id', '')}\n"
        f"Stripe payment intent: {payment_data.get('stripe_payment_intent_id', '')}\n\n"
        f"View support records:\n{supporters_url}"
    )
    html_body = _paragraph_html(
        "New one-time support payment.",
        (
            f"Product: {product['title']}\n"
            f"Amount: {amount}\n"
            f"Customer: {_support_admin_customer_label(payment_data)}\n"
            f"Status: {payment_data.get('status', '') or 'unknown'}"
        ),
        (
            f"Stripe session: {payment_data.get('stripe_checkout_session_id', '')}\n"
            f"Stripe payment intent: {payment_data.get('stripe_payment_intent_id', '')}"
        ),
        f"View support records:\n{supporters_url}",
    )
    try:
        if send_email(admin_email, "New support payment", text, html_body):
            _set_support_payment_admin_email_sent_at(payment_data.get("stripe_checkout_session_id", ""))
    except Exception:
        current_app.logger.exception("Support payment admin email failed.")


def _send_support_subscription_admin_email(subscription, product: dict) -> None:
    if not subscription or not product or not email_configured():
        return

    subscription_data = _row_to_dict(subscription)
    admin_email = current_app.config.get("ADMIN_EMAIL", "")
    if not admin_email or subscription_data.get("admin_email_sent_at"):
        return

    supporters_url = _external_url("shop.supporters")
    amount = _format_money(subscription_data.get("amount_cents"), subscription_data.get("currency", "cad"))
    text = (
        "New recurring supporter.\n\n"
        f"Tier: {product['title']}\n"
        f"Amount: {amount}/month\n"
        f"Customer: {_support_admin_customer_label(subscription_data)}\n"
        f"Status: {subscription_data.get('status', '') or 'unknown'}\n\n"
        f"Stripe subscription: {subscription_data.get('stripe_subscription_id', '')}\n"
        f"Stripe customer: {subscription_data.get('stripe_customer_id', '')}\n\n"
        f"View supporters:\n{supporters_url}"
    )
    html_body = _paragraph_html(
        "New recurring supporter.",
        (
            f"Tier: {product['title']}\n"
            f"Amount: {amount}/month\n"
            f"Customer: {_support_admin_customer_label(subscription_data)}\n"
            f"Status: {subscription_data.get('status', '') or 'unknown'}"
        ),
        (
            f"Stripe subscription: {subscription_data.get('stripe_subscription_id', '')}\n"
            f"Stripe customer: {subscription_data.get('stripe_customer_id', '')}"
        ),
        f"View supporters:\n{supporters_url}",
    )
    try:
        if send_email(admin_email, "New recurring supporter", text, html_body):
            _set_support_subscription_admin_email_sent_at(subscription_data.get("stripe_subscription_id", ""))
    except Exception:
        current_app.logger.exception("Support subscription admin email failed.")


def _record_support_checkout(session):
    product = _support_product_from_session(session)
    if product and product["mode"] == "payment":
        payment_record = _build_support_payment_record(session, product)
        payment = _upsert_support_payment(payment_record)
        _send_support_payment_admin_email(payment, product)
        return payment

    subscription_id = _stripe_id(_stripe_value(session, "subscription", ""))
    subscription = None
    if subscription_id:
        try:
            subscription = _retrieve_stripe_subscription(subscription_id)
        except Exception:
            current_app.logger.exception("Stripe Subscription lookup failed after support checkout.")
    record = _build_support_subscription_record(session=session, subscription=subscription)
    subscription_row = _upsert_support_subscription(record)
    if subscription_row:
        product = product or _support_product_by_price_id(subscription_row["stripe_price_id"])
        _send_support_subscription_admin_email(subscription_row, product)
    return subscription_row


def _record_support_subscription(subscription):
    record = _build_support_subscription_record(subscription=subscription)
    subscription_row = _upsert_support_subscription(record)
    if subscription_row:
        product = _support_product_by_price_id(subscription_row["stripe_price_id"])
        _send_support_subscription_admin_email(subscription_row, product)
    return subscription_row


def _record_support_invoice_subscription(invoice):
    subscription_id = _stripe_id(_stripe_value(invoice, "subscription", ""))
    if not subscription_id:
        return None
    subscription = _retrieve_stripe_subscription(subscription_id)
    return _record_support_subscription(subscription)


def _support_status_filter_counts(status_counts: dict[str, int]) -> dict[str, int]:
    return {
        "current": sum(status_counts.get(status, 0) for status in _SUPPORT_CURRENT_STATUSES),
        "attention": sum(status_counts.get(status, 0) for status in _SUPPORT_ATTENTION_STATUSES),
        "canceled": sum(status_counts.get(status, 0) for status in _SUPPORT_CANCELED_STATUSES),
        "all": sum(status_counts.values()),
    }


def _support_status_filter_tabs(active_filter: str):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT status, COUNT(*) FROM support_subscriptions GROUP BY status")
        status_counts = {row["status"] if hasattr(row, "keys") else row[0]: row[1] for row in cur.fetchall()}
    filter_counts = _support_status_filter_counts(status_counts)
    return [
        {
            "key": key,
            "label": config["label"],
            "count": filter_counts.get(key, 0),
            "active": key == active_filter,
        }
        for key, config in _SUPPORT_STATUS_FILTERS.items()
    ]


def _create_checkout_session(order_id: int, customer_email: str):
    _set_stripe_key()
    metadata = {
        "order_id": str(order_id),
        "product_key": _PULSE_QUESTION_PRODUCT_KEY,
    }
    return stripe.checkout.Session.create(
        mode="payment",
        line_items=[_line_item()],
        success_url=(
            f"{_external_url('shop.payment_success')}"
            f"?session_id={{CHECKOUT_SESSION_ID}}&product={_PULSE_QUESTION_PRODUCT_KEY}"
        ),
        cancel_url=f"{_external_url('shop.pulse_question')}?canceled=1",
        client_reference_id=str(order_id),
        customer_email=customer_email,
        metadata=metadata,
        payment_intent_data={"metadata": metadata},
    )


def _create_support_checkout_session(product: dict):
    _set_stripe_key()
    price_id = _support_price_id(product)
    if not price_id:
        raise ValueError(f"{product['price_config']} is not configured.")

    metadata = {
        "product_key": product["product_key"],
        "support_slug": product["slug"],
        "support_name": product["title"],
    }
    if current_user.is_authenticated:
        metadata["user_id"] = str(current_user.id)
        metadata["customer_email"] = current_user.email
        metadata["customer_name"] = current_user.display_name or current_user.username

    checkout_params = dict(
        mode=product["mode"],
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=(
            f"{_external_url('shop.payment_success')}"
            f"?session_id={{CHECKOUT_SESSION_ID}}&product={product['product_key']}"
        ),
        cancel_url=_external_url("shop.index"),
        metadata=metadata,
    )
    if current_user.is_authenticated:
        checkout_params["client_reference_id"] = str(current_user.id)
        checkout_params["customer_email"] = current_user.email
    if product["mode"] == "subscription":
        checkout_params["subscription_data"] = {"metadata": metadata}
    else:
        checkout_params["payment_intent_data"] = {"metadata": metadata}
        if product.get("submit_type"):
            checkout_params["submit_type"] = product["submit_type"]
    return stripe.checkout.Session.create(**checkout_params)


@shop_bp.route("/shop")
@shop_bp.route("/shop/")
def index():
    return render_template(
        "shop/index.html",
        shop_categories=_shop_categories(),
        is_admin=_is_admin(),
    )


@shop_bp.route("/shop/support", methods=["GET"])
@shop_bp.route("/shop/support/<support_slug>", methods=["GET"])
def support_checkout_get(support_slug="one-time"):
    return redirect(url_for("shop.index"))


@shop_bp.route("/shop/support", methods=["POST"])
@rate_limit("shop.support_checkout", 10, 60 * 60)
def support():
    return _start_support_checkout("one-time")


@shop_bp.route("/shop/support/<support_slug>", methods=["POST"])
@rate_limit("shop.support_checkout", 10, 60 * 60)
def support_checkout(support_slug):
    return _start_support_checkout(support_slug)


def _start_support_checkout(support_slug: str):
    product = _SUPPORT_PRODUCTS_BY_SLUG.get(support_slug)
    if not product:
        abort(404)

    if not _stripe_configured():
        flash("Stripe checkout is not configured yet.", "error")
        return redirect(url_for("shop.index"))
    if not _support_price_id(product):
        current_app.logger.warning(
            "Support checkout missing Stripe price config: %s",
            product["price_config"],
        )
        flash(f"{product['title']} checkout is not configured yet.", "error")
        return redirect(url_for("shop.index"))

    try:
        checkout_session = _create_support_checkout_session(product)
    except Exception:
        current_app.logger.exception(
            "Support checkout session creation failed for %s",
            product["product_key"],
        )
        flash("Support checkout could not be started. Please try again in a moment.", "error")
        return redirect(url_for("shop.index"))
    return redirect(checkout_session.url, code=303)


@shop_bp.route("/shop/billing-portal", methods=["POST"])
@login_required
@rate_limit("shop.billing_portal", 10, 60 * 60)
def billing_portal():
    subscription = get_support_subscription_for_billing(current_user.id, current_user.email)
    if not subscription:
        flash("No Stripe support subscription was found for your account.", "error")
        return redirect(url_for("auth.profile"))
    if not _stripe_configured():
        flash("Stripe billing management is not configured yet.", "error")
        return redirect(url_for("auth.profile"))

    customer_id = subscription["stripe_customer_id"]
    try:
        _set_stripe_key()
        portal_session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=_external_url("auth.profile"),
        )
    except Exception:
        current_app.logger.exception("Stripe billing portal session creation failed.")
        flash("Billing management could not be opened. Please try again in a moment.", "error")
        return redirect(url_for("auth.profile"))

    return redirect(portal_session.url, code=303)


@shop_bp.route("/shop/pulse-question")
def pulse_question():
    if request.args.get("canceled"):
        flash("Checkout was canceled. Your card was not charged.", "info")
    return render_template(
        "shop/pulse_question.html",
        form_data={},
        is_admin=_is_admin(),
        stripe_configured=_stripe_configured(),
    )


@shop_bp.route("/shop/pulse-question/checkout", methods=["POST"])
@rate_limit("shop.pulse_question_checkout", 5, 60 * 60)
def pulse_question_checkout():
    payload, errors = _pulse_question_payload()
    if errors:
        for error in errors[:3]:
            flash(error, "error")
        return render_template(
            "shop/pulse_question.html",
            form_data=payload,
            is_admin=_is_admin(),
            stripe_configured=_stripe_configured(),
        ), 400

    if not _stripe_configured():
        flash("Stripe checkout is not configured yet.", "error")
        return render_template(
            "shop/pulse_question.html",
            form_data=payload,
            is_admin=_is_admin(),
            stripe_configured=False,
        ), 503

    order_id = _insert_pulse_question_order(payload)
    try:
        checkout_session = _create_checkout_session(order_id, payload["customer_email"])
    except Exception:
        current_app.logger.exception("Stripe Checkout Session creation failed")
        flash("Checkout could not be started. Please try again in a moment.", "error")
        return redirect(url_for("shop.pulse_question"))

    _update_order_checkout_session(order_id, checkout_session.id)
    return redirect(checkout_session.url, code=303)


@shop_bp.route("/shop/payment-success")
@rate_limit("shop.payment_success", 60, 60 * 60)
def payment_success():
    session_id = request.args.get("session_id", "").strip()
    expected_product_key = request.args.get("product", "").strip()
    expected_support_product = _SUPPORT_PRODUCTS_BY_KEY.get(expected_product_key)
    if not session_id:
        flash("Payment session not found.", "error")
        return redirect(url_for("shop.index"))
    if not _stripe_configured():
        flash("Stripe checkout is not configured yet.", "error")
        return redirect(url_for("shop.index"))

    checkout_session = None
    is_support_payment = False
    support_product = None
    status_check_failed = False
    try:
        _set_stripe_key()
        checkout_session = stripe.checkout.Session.retrieve(session_id)
        metadata = _stripe_value(checkout_session, "metadata", {}) or {}
        support_product = _support_product_from_metadata(metadata) or expected_support_product
        is_support_payment = support_product is not None
        if (
            metadata.get("product_key") == _PULSE_QUESTION_PRODUCT_KEY
            and _stripe_value(checkout_session, "payment_status", "") == "paid"
        ):
            order = _mark_order_paid(checkout_session)
            _send_paid_pulse_question_emails(order)
        elif (
            is_support_payment
            and support_product
            and (
                _stripe_value(checkout_session, "status", "") == "complete"
                or _stripe_value(checkout_session, "payment_status", "") in {"paid", "no_payment_required"}
            )
        ):
            _record_support_checkout(checkout_session)
    except Exception:
        current_app.logger.exception("Stripe Checkout Session lookup failed")
        status_check_failed = True
        support_product = support_product or expected_support_product
        is_support_payment = support_product is not None

    order = _safe_fetch_order_by_session(session_id)
    support_payment = _safe_fetch_support_payment_by_session(session_id) if is_support_payment else None
    return render_template(
        "shop/payment_success.html",
        order=order,
        checkout_session=checkout_session,
        is_support_payment=is_support_payment,
        support_product=support_product,
        expected_product_key=expected_product_key,
        expected_support_product=expected_support_product,
        status_check_failed=status_check_failed,
        support_payment=support_payment,
    )


@shop_bp.route("/shop/supporters")
def supporters():
    if not _is_admin():
        abort(404)

    status_filter = request.args.get("status", "current")
    if status_filter not in _SUPPORT_STATUS_FILTERS:
        status_filter = "current"
    statuses = _SUPPORT_STATUS_FILTERS[status_filter]["statuses"]

    with get_conn() as conn:
        cur = conn.cursor()
        if statuses:
            cur.execute(
                f"""
                SELECT
                    s.*,
                    u.username AS account_username,
                    u.email AS account_email,
                    u.display_name AS account_display_name
                FROM support_subscriptions s
                LEFT JOIN users u ON u.id = s.user_id
                WHERE s.status IN ({ph(len(statuses))})
                ORDER BY
                    CASE lower(s.tier)
                        WHEN 'gold' THEN 1
                        WHEN 'silver' THEN 2
                        WHEN 'bronze' THEN 3
                        ELSE 4
                    END,
                    s.updated_at DESC
                """,
                statuses,
            )
        else:
            cur.execute(
                """
                SELECT
                    s.*,
                    u.username AS account_username,
                    u.email AS account_email,
                    u.display_name AS account_display_name
                FROM support_subscriptions s
                LEFT JOIN users u ON u.id = s.user_id
                ORDER BY
                    CASE lower(s.tier)
                        WHEN 'gold' THEN 1
                        WHEN 'silver' THEN 2
                        WHEN 'bronze' THEN 3
                        ELSE 4
                    END,
                    s.updated_at DESC
                """
            )
        subscriptions = cur.fetchall()
        cur.execute(
            """
            SELECT *
            FROM support_payments
            ORDER BY COALESCE(paid_at, created_at) DESC, created_at DESC
            LIMIT 100
            """
        )
        one_time_payments = cur.fetchall()

    return render_template(
        "shop/supporters.html",
        subscriptions=subscriptions,
        one_time_payments=one_time_payments,
        status_filter=status_filter,
        status_tabs=_support_status_filter_tabs(status_filter),
    )


@shop_bp.route("/shop/pulse-question/submissions")
def pulse_question_submissions():
    if not _is_admin():
        flash("Admin access required.", "error")
        return redirect(url_for("shop.index"))

    status = request.args.get("status", "all")
    allowed_statuses = set(_PULSE_SUBMISSION_STATUSES)
    if status not in allowed_statuses:
        status = "all"

    _sync_pending_pulse_question_orders()

    with get_conn() as conn:
        cur = conn.cursor()
        if status == "all":
            cur.execute(
                f"SELECT * FROM shop_orders WHERE product_key = {ph()} ORDER BY created_at DESC",
                (_PULSE_QUESTION_PRODUCT_KEY,),
            )
        else:
            cur.execute(
                f"""
                SELECT * FROM shop_orders
                WHERE product_key = {ph()} AND status = {ph()}
                ORDER BY created_at DESC
                """,
                (_PULSE_QUESTION_PRODUCT_KEY, status),
            )
        orders = cur.fetchall()

    return render_template(
        "shop/pulse_submissions.html",
        orders=orders,
        status=status,
        status_tabs=_pulse_submission_status_tabs(status),
    )


@shop_bp.route("/stripe/webhook", methods=["POST"])
def stripe_webhook():
    if not stripe:
        abort(400)
    endpoint_secret = current_app.config.get("STRIPE_WEBHOOK_SECRET", "")
    if not endpoint_secret:
        abort(400, description="Stripe webhook secret is not configured.")

    payload = request.get_data()
    sig_header = request.headers.get("Stripe-Signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except Exception:
        current_app.logger.exception("Invalid Stripe webhook payload")
        abort(400)

    event_type = event.get("type")
    data_object = event.get("data", {}).get("object", {})
    if event_type in {"checkout.session.completed", "checkout.session.async_payment_succeeded"}:
        if data_object.get("metadata", {}).get("product_key") == _PULSE_QUESTION_PRODUCT_KEY:
            try:
                if data_object.get("payment_status") in {"paid", "no_payment_required"}:
                    order = _mark_order_paid(data_object)
                    _send_paid_pulse_question_emails(order)
            except Exception:
                current_app.logger.exception("Pulse question checkout webhook processing failed.")
        elif data_object.get("metadata", {}).get("product_key") in _SUPPORT_PRODUCT_KEYS:
            try:
                _record_support_checkout(data_object)
            except Exception:
                current_app.logger.exception("Support checkout webhook processing failed.")
    elif event_type in {
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
        "customer.subscription.paused",
        "customer.subscription.resumed",
    }:
        try:
            _record_support_subscription(data_object)
        except Exception:
            current_app.logger.exception("Support subscription webhook processing failed.")
    elif event_type in {"invoice.paid", "invoice.payment_failed"}:
        try:
            _record_support_invoice_subscription(data_object)
        except Exception:
            current_app.logger.exception("Support invoice webhook processing failed.")
    elif event_type == "checkout.session.expired":
        try:
            _set_order_status_by_session(data_object.get("id", ""), "expired")
        except Exception:
            current_app.logger.exception("Checkout expiration webhook processing failed.")
    elif event_type == "checkout.session.async_payment_failed":
        try:
            _set_order_status_by_session(data_object.get("id", ""), "failed")
        except Exception:
            current_app.logger.exception("Checkout failure webhook processing failed.")

    return jsonify({"received": True})
