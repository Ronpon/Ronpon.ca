"""Shop routes."""
from __future__ import annotations

from flask import Blueprint, render_template, url_for

shop_bp = Blueprint("shop", __name__)


def _shop_products():
    """Return display data for the shop while payment links are still manual."""
    return [
        {
            "kind": "Amazon book",
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
            "kind": "Amazon book",
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
            "kind": "The Pulse",
            "title": "Write Your Own Question for The Pulse*",
            "description": (
                "Submit a multiple-choice poll question for possible use in The Pulse, "
                "the man-on-the-street game show segment where people predict poll answers."
            ),
            "price": "$10.00 CAD",
            "image_url": "",
            "placeholder": "PULSE",
            "action_label": "Write a Question",
            "action_url": url_for("shop.pulse_question"),
            "external": False,
            "featured": True,
        },
    ]


@shop_bp.route("/shop")
@shop_bp.route("/shop/")
def index():
    return render_template("shop/index.html", products=_shop_products())


@shop_bp.route("/shop/pulse-question")
def pulse_question():
    return render_template("shop/pulse_question.html")
