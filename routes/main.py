"""Main / home routes."""
from flask import Blueprint, render_template

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def home():
    return render_template("main/home.html")


@main_bp.route("/contact")
def contact():
    return render_template("main/contact.html")
