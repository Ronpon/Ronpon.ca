"""Ronpon.com — Main Flask application."""
from __future__ import annotations

import os
from flask import Flask, render_template, send_from_directory
from flask_login import LoginManager
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
from models.db import init_db
init_db(Config)

# ---------------------------------------------------------------------------
# Flask-Login
# ---------------------------------------------------------------------------
login_manager = LoginManager(app)
login_manager.login_view = "auth.login"
login_manager.login_message_category = "error"

from models.user import User

@login_manager.user_loader
def load_user(user_id):
    return User.get_by_id(int(user_id))

# ---------------------------------------------------------------------------
# Blueprints
# ---------------------------------------------------------------------------
from routes.main import main_bp
from routes.auth import auth_bp
from routes.games import games_bp
from routes.videos import videos_bp
from routes.pulse import pulse_bp
from routes.scores import scores_bp

app.register_blueprint(main_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(games_bp, url_prefix="/games")
app.register_blueprint(videos_bp, url_prefix="/videos")
app.register_blueprint(pulse_bp, url_prefix="/the-pulse")
app.register_blueprint(scores_bp, url_prefix="/scores")

# ── Werblers game blueprints (API routes under /games/werblers) ──
from werblers_engine import database as werblers_db
werblers_db.init_db()

from werblers_web.routes.game_routes import game_bp as werblers_game_bp
from werblers_web.routes.combat_routes import combat_bp as werblers_combat_bp
from werblers_web.routes.mystery_routes import mystery_bp as werblers_mystery_bp
from werblers_web.routes.inventory_routes import inventory_bp as werblers_inventory_bp
from werblers_web.routes.save_routes import save_bp as werblers_save_bp

app.register_blueprint(werblers_game_bp, url_prefix="/games/werblers")
app.register_blueprint(werblers_combat_bp, url_prefix="/games/werblers")
app.register_blueprint(werblers_mystery_bp, url_prefix="/games/werblers")
app.register_blueprint(werblers_inventory_bp, url_prefix="/games/werblers")
app.register_blueprint(werblers_save_bp, url_prefix="/games/werblers")

# ── Werblers media serving ───────────────────────────────────────
_WERBLERS_MEDIA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "werblers_media")

@app.route("/games/werblers/images/<path:filename>")
def werblers_serve_image(filename: str):
    return send_from_directory(os.path.join(_WERBLERS_MEDIA, "Images"), filename)

@app.route("/games/werblers/music/<path:filename>")
def werblers_serve_music(filename: str):
    return send_from_directory(os.path.join(_WERBLERS_MEDIA, "Music"), filename)

@app.route("/games/werblers/videos/<path:filename>")
def werblers_serve_video(filename: str):
    return send_from_directory(os.path.join(_WERBLERS_MEDIA, "Videos"), filename)

# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------
@app.errorhandler(404)
def page_not_found(e):
    return render_template("errors/404.html"), 404


@app.errorhandler(500)
def internal_error(e):
    return render_template("errors/500.html"), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
