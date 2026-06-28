"""Transactional email helpers."""
from __future__ import annotations

import html
from typing import Iterable

from flask import current_app

try:
    import resend
except ImportError:  # pragma: no cover - handled at runtime when dependencies are installed
    resend = None


def email_configured() -> bool:
    return bool(
        resend
        and current_app.config.get("RESEND_API_KEY")
        and current_app.config.get("EMAIL_FROM")
    )


def email_configuration_status() -> dict:
    return {
        "resend_package": resend is not None,
        "resend_api_key": bool(current_app.config.get("RESEND_API_KEY")),
        "email_from": bool(current_app.config.get("EMAIL_FROM")),
        "email_from_value": current_app.config.get("EMAIL_FROM", ""),
        "admin_email": bool(current_app.config.get("ADMIN_EMAIL")),
        "admin_email_value": current_app.config.get("ADMIN_EMAIL", ""),
        "configured": email_configured(),
    }


def _recipients(to: str | Iterable[str]) -> list[str]:
    if isinstance(to, str):
        return [to]
    return [recipient for recipient in to if recipient]


def send_email(to: str | Iterable[str], subject: str, text: str, html_body: str = "") -> bool:
    """Send one transactional email through Resend."""
    if not email_configured():
        current_app.logger.info("Email not sent because Resend is not configured.")
        return False

    recipients = _recipients(to)
    if not recipients:
        return False

    resend.api_key = current_app.config["RESEND_API_KEY"]
    params = {
        "from": current_app.config["EMAIL_FROM"],
        "to": recipients,
        "subject": subject,
        "text": text,
        "html": html_body or text_to_html(text),
    }
    resend.Emails.send(params)
    return True


def text_to_html(text: str) -> str:
    escaped = html.escape(text).replace("\n", "<br>")
    return f"<p>{escaped}</p>"
