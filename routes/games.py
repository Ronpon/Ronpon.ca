"""Games section routes."""
from flask import Blueprint, render_template, request

games_bp = Blueprint("games", __name__)

# Platform categories
PLATFORMS = ["PC", "Mobile"]

# Registry of available games — add new ones here
GAMES = [
    {
        "id": "battle-chess",
        "title": "Battle Chess",
        "description": "Chess with minigame battles. Capture a piece, win the fight!",
        "thumbnail": "games/thumbnails/Battle Chess Thumbnail.jpg",
        "type": "static",
        "platform": "PC",
    },
    {
        "id": "werblers",
        "title": "Werblers",
        "description": "A board game adventure with heroes, monsters, and loot.",
        "thumbnail": "games/thumbnails/Werblers Thumbnail.png",
        "type": "flask",
        "platform": "PC",
    },
    {
        "id": "werblers-mobile",
        "title": "Werblers Mobile",
        "description": "The mobile edition of Werblers — play on any device.",
        "thumbnail": "games/thumbnails/Werblers Thumbnail.png",
        "type": "flask",
        "platform": "Mobile",
    },
]


@games_bp.route("/")
def index():
    pc_games = [g for g in GAMES if g["platform"] == "PC"]
    mobile_games = [g for g in GAMES if g["platform"] == "Mobile"]
    return render_template("games/index.html",
                           pc_games=pc_games, mobile_games=mobile_games)


@games_bp.route("/battle-chess")
def battle_chess():
    return render_template("games/play.html",
                           game_title="Battle Chess",
                           iframe_src="/static/games/battle-chess/index.html")


@games_bp.route("/werblers")
def werblers():
    return render_template("games/werblers.html")


@games_bp.route("/werblers-mobile")
def werblers_mobile():
    return render_template("games/werblers_mobile.html")
