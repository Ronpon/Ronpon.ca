"""Shop routes."""
from __future__ import annotations

import re
import html as html_lib
from datetime import datetime, timezone
from urllib.parse import urljoin

from flask import Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user

from models.db import get_conn, is_postgres, ph
from email_service import email_configured, send_email

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
        "card_class": "shop-card-support shop-card-recurring shop-card-gold",
    },
)
_SUPPORT_PRODUCTS_BY_SLUG = {product["slug"]: product for product in _SUPPORT_PRODUCTS}
_SUPPORT_PRODUCTS_BY_KEY = {product["product_key"]: product for product in _SUPPORT_PRODUCTS}
_SUPPORT_PRODUCT_KEYS = set(_SUPPORT_PRODUCTS_BY_KEY)


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

    order_data = dict(order)
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


def _create_checkout_session(order_id: int, customer_email: str):
    _set_stripe_key()
    metadata = {
        "order_id": str(order_id),
        "product_key": _PULSE_QUESTION_PRODUCT_KEY,
    }
    return stripe.checkout.Session.create(
        mode="payment",
        line_items=[_line_item()],
        success_url=f"{_external_url('shop.payment_success')}?session_id={{CHECKOUT_SESSION_ID}}",
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
    checkout_params = dict(
        mode=product["mode"],
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{_external_url('shop.payment_success')}?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=_external_url("shop.index"),
        metadata=metadata,
    )
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
    return render_template("shop/index.html", shop_categories=_shop_categories())


@shop_bp.route("/shop/support")
def support():
    return _start_support_checkout("one-time")


@shop_bp.route("/shop/support/<support_slug>")
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
def payment_success():
    session_id = request.args.get("session_id", "").strip()
    if not session_id:
        flash("Payment session not found.", "error")
        return redirect(url_for("shop.index"))
    if not _stripe_configured():
        flash("Stripe checkout is not configured yet.", "error")
        return redirect(url_for("shop.index"))

    checkout_session = None
    is_support_payment = False
    support_product = None
    try:
        _set_stripe_key()
        checkout_session = stripe.checkout.Session.retrieve(session_id)
        metadata = checkout_session.get("metadata") or {}
        support_product = _SUPPORT_PRODUCTS_BY_KEY.get(metadata.get("product_key", ""))
        is_support_payment = support_product is not None
        if (
            metadata.get("product_key") == _PULSE_QUESTION_PRODUCT_KEY
            and checkout_session.get("payment_status") == "paid"
        ):
            order = _mark_order_paid(checkout_session)
            _send_paid_pulse_question_emails(order)
    except Exception:
        current_app.logger.exception("Stripe Checkout Session lookup failed")
        flash("Payment status could not be checked. We will confirm it by webhook.", "info")

    order = _fetch_order_by_session(session_id)
    return render_template(
        "shop/payment_success.html",
        order=order,
        checkout_session=checkout_session,
        is_support_payment=is_support_payment,
        support_product=support_product,
    )


@shop_bp.route("/shop/pulse-question/submissions")
def pulse_question_submissions():
    if not _is_admin():
        flash("Admin access required.", "error")
        return redirect(url_for("shop.index"))

    status = request.args.get("status", "paid")
    allowed_statuses = {"paid", "pending", "expired", "failed", "all"}
    if status not in allowed_statuses:
        status = "paid"

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

    return render_template("shop/pulse_submissions.html", orders=orders, status=status)


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
            if data_object.get("payment_status") in {"paid", "no_payment_required"}:
                order = _mark_order_paid(data_object)
                _send_paid_pulse_question_emails(order)
        elif data_object.get("metadata", {}).get("product_key") in _SUPPORT_PRODUCT_KEYS:
            current_app.logger.info(
                "Support checkout completed: %s",
                data_object.get("metadata", {}).get("product_key"),
            )
    elif event_type == "checkout.session.expired":
        _set_order_status_by_session(data_object.get("id", ""), "expired")
    elif event_type == "checkout.session.async_payment_failed":
        _set_order_status_by_session(data_object.get("id", ""), "failed")

    return jsonify({"received": True})
