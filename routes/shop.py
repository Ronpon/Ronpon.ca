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
                "A Ronpon book listing with room for a proper blurb, cover art, "
                "and the final Amazon product link."
            ),
            "price": "",
            "image_url": "",
            "placeholder": "READ",
            "action_label": "View on Amazon",
            "action_url": "https://www.amazon.com/s?k=Make+Someone+Read+You+This+Book",
            "external": True,
        },
        {
            "kind": "Amazon book",
            "title": "Ronpon's Nursery Rhymes",
            "description": (
                "A playful nursery-rhyme book listing with space ready for the "
                "finished cover, description, and Amazon link."
            ),
            "price": "",
            "image_url": "",
            "placeholder": "RHYMES",
            "action_label": "View on Amazon",
            "action_url": "https://www.amazon.com/s?k=Ronpon%27s+Nursery+Rhymes",
            "external": True,
        },
        {
            "kind": "The Pulse",
            "title": "Write Your Own Question for The Pulse*",
            "description": (
                "Submit a multiple-choice poll question for possible use in The Pulse, "
                "the man-on-the-street game show segment where people predict poll answers. "
                "This is a paid submission option only, not paid entry into a contest or game."
            ),
            "price": "$10.00",
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
