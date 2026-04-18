"""Games section routes."""
from flask import Blueprint, render_template

games_bp = Blueprint("games", __name__)

# Registry of available games — add new ones here
GAMES = [
    {
        "id": "battle-chess",
        "title": "Battle Chess",
        "description": "Chess with minigame battles. Capture a piece, win the fight!",
        "thumbnail": "games/thumbnails/battle-chess.png",
        "type": "static",  # served as static files in an iframe
    },
    {
        "id": "werblers",
        "title": "Werblers",
        "description": "A board game adventure with heroes, monsters, and loot.",
        "thumbnail": "games/thumbnails/werblers.png",
        "type": "flask",  # has its own backend routes
    },
]


@games_bp.route("/")
def index():
    return render_template("games/index.html", games=GAMES)


@games_bp.route("/battle-chess")
def battle_chess():
    return render_template("games/play.html",
                           game_title="Battle Chess",
                           iframe_src="/static/games/battle-chess/index.html")


@games_bp.route("/werblers")
def werblers():
    return render_template("games/werblers.html")
