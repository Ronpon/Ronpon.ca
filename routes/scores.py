"""High scores / leaderboard routes."""
from flask import Blueprint, render_template, request, jsonify
from flask_login import current_user, login_required
from models.db import get_conn, ph

scores_bp = Blueprint("scores", __name__)

# Games that support scores — display name + DB key
SCORED_GAMES = [
    {"key": "battle-chess", "title": "Battle Chess"},
    {"key": "werblers", "title": "Werblers"},
]


@scores_bp.route("/")
def index():
    game_filter = request.args.get("game", "").strip()
    valid_keys = [g["key"] for g in SCORED_GAMES]
    if game_filter not in valid_keys:
        game_filter = ""

    with get_conn() as conn:
        cur = conn.cursor()

        if game_filter:
            cur.execute(
                f"""SELECT hs.id, u.username, hs.game, hs.score, hs.detail, hs.achieved_at
                    FROM high_scores hs
                    JOIN users u ON u.id = hs.user_id
                    WHERE hs.game = {ph()}
                    ORDER BY hs.score DESC, hs.achieved_at ASC
                    LIMIT 100""",
                (game_filter,),
            )
        else:
            cur.execute(
                """SELECT hs.id, u.username, hs.game, hs.score, hs.detail, hs.achieved_at
                   FROM high_scores hs
                   JOIN users u ON u.id = hs.user_id
                   ORDER BY hs.score DESC, hs.achieved_at ASC
                   LIMIT 100"""
            )

        rows = cur.fetchall()

    scores = []
    for r in rows:
        scores.append({
            "id": r[0], "username": r[1], "game": r[2],
            "score": r[3], "detail": r[4], "achieved_at": r[5],
        })

    return render_template(
        "scores/index.html",
        scores=scores,
        games=SCORED_GAMES,
        active_game=game_filter,
    )


# ── JSON API for games to submit scores ──────────────────────────

@scores_bp.route("/api/submit", methods=["POST"])
@login_required
def api_submit():
    data = request.get_json(silent=True) or {}
    game = (data.get("game") or "").strip()
    score = data.get("score")
    detail = (data.get("detail") or "").strip()

    valid_keys = [g["key"] for g in SCORED_GAMES]
    if game not in valid_keys:
        return jsonify(ok=False, error="Invalid game."), 400
    if not isinstance(score, (int, float)) or score < 0:
        return jsonify(ok=False, error="Invalid score."), 400

    score = int(score)

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"INSERT INTO high_scores (user_id, game, score, detail) VALUES ({ph(4)})",
            (current_user.id, game, score, detail[:200]),
        )

    return jsonify(ok=True)
