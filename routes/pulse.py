"""The Pulse — game show, podcast, polls & live stream routes."""
from __future__ import annotations

import re
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user, login_required
from models.db import get_conn, ph

pulse_bp = Blueprint("pulse", __name__)


def _is_admin():
    return current_user.is_authenticated and current_user.is_admin


def _get_setting(cur, key, default=""):
    cur.execute(f"SELECT value FROM pulse_settings WHERE key = {ph()}", (key,))
    row = cur.fetchone()
    return row[0] if row else default


def _set_setting(cur, key, value):
    """Upsert a pulse setting."""
    cur.execute(f"SELECT 1 FROM pulse_settings WHERE key = {ph()}", (key,))
    if cur.fetchone():
        cur.execute(f"UPDATE pulse_settings SET value = {ph()} WHERE key = {ph()}", (value, key))
    else:
        cur.execute(f"INSERT INTO pulse_settings (key, value) VALUES ({ph(2)})", (key, value))


def _extract_youtube_id(url_or_id: str) -> str | None:
    url_or_id = url_or_id.strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", url_or_id):
        return url_or_id
    m = re.search(r"(?:v=|youtu\.be/|embed/)([A-Za-z0-9_-]{11})", url_or_id)
    return m.group(1) if m else None


# ── Public: poll listing / voting ────────────────────────────────

@pulse_bp.route("/")
def index():
    with get_conn() as conn:
        cur = conn.cursor()

        # ── Live Now settings ──
        live_active = _get_setting(cur, "live_active", "0") == "1"
        live_youtube_id = _get_setting(cur, "live_youtube_id")
        live_twitch_channel = _get_setting(cur, "live_twitch_channel")

        # ── Pulse videos ──
        cur.execute(
            "SELECT id, youtube_id, title, section, added_at FROM pulse_videos "
            "WHERE section = 'game-show' ORDER BY added_at DESC"
        )
        game_show_videos = cur.fetchall()

        cur.execute(
            "SELECT id, youtube_id, title, section, added_at FROM pulse_videos "
            "WHERE section = 'podcast' ORDER BY added_at DESC"
        )
        podcast_videos = cur.fetchall()

        # ── Polls ──
        cur.execute(
            "SELECT id, question, created_at FROM polls WHERE is_active ORDER BY created_at DESC"
        )
        active_polls = cur.fetchall()

        # Closed polls
        cur.execute(
            "SELECT id, question, created_at FROM polls WHERE NOT is_active ORDER BY created_at DESC"
        )
        closed_polls = cur.fetchall()

        # Build option + vote data for each poll
        polls_data = []
        for poll in list(active_polls) + list(closed_polls):
            pid = poll[0]
            cur.execute("SELECT id, label FROM poll_options WHERE poll_id = " + ph(), (pid,))
            options = cur.fetchall()

            # Vote counts per option
            counts = {}
            total = 0
            for opt in options:
                cur.execute(
                    "SELECT COUNT(*) FROM poll_votes WHERE option_id = " + ph(),
                    (opt[0],),
                )
                c = cur.fetchone()[0]
                counts[opt[0]] = c
                total += c

            # Current user's vote (if logged in)
            user_vote = None
            if current_user.is_authenticated:
                cur.execute(
                    f"SELECT option_id FROM poll_votes WHERE poll_id = {ph()} AND user_id = {ph()}",
                    (pid, current_user.id),
                )
                row = cur.fetchone()
                if row:
                    user_vote = row[0]

            polls_data.append({
                "id": pid,
                "question": poll[1],
                "created_at": poll[2],
                "is_active": poll in active_polls,
                "options": [{"id": o[0], "label": o[1], "votes": counts.get(o[0], 0)} for o in options],
                "total_votes": total,
                "user_vote": user_vote,
            })

    return render_template(
        "pulse/index.html",
        polls=polls_data,
        is_admin=_is_admin(),
        live_active=live_active,
        live_youtube_id=live_youtube_id,
        live_twitch_channel=live_twitch_channel,
        game_show_videos=game_show_videos,
        podcast_videos=podcast_videos,
    )


@pulse_bp.route("/vote/<int:poll_id>", methods=["POST"])
@login_required
def vote(poll_id):
    option_id = request.form.get("option_id", type=int)
    if not option_id:
        flash("Please select an option.", "error")
        return redirect(url_for("pulse.index"))

    with get_conn() as conn:
        cur = conn.cursor()

        # Verify poll is active
        cur.execute(f"SELECT is_active FROM polls WHERE id = {ph()}", (poll_id,))
        poll = cur.fetchone()
        if not poll or not poll[0]:
            flash("This poll is closed.", "error")
            return redirect(url_for("pulse.index"))

        # Verify option belongs to poll
        cur.execute(
            f"SELECT id FROM poll_options WHERE id = {ph()} AND poll_id = {ph()}",
            (option_id, poll_id),
        )
        if not cur.fetchone():
            flash("Invalid option.", "error")
            return redirect(url_for("pulse.index"))

        # Check for existing vote
        cur.execute(
            f"SELECT id FROM poll_votes WHERE poll_id = {ph()} AND user_id = {ph()}",
            (poll_id, current_user.id),
        )
        if cur.fetchone():
            flash("You already voted on this poll.", "error")
            return redirect(url_for("pulse.index"))

        # Cast vote
        cur.execute(
            f"INSERT INTO poll_votes (poll_id, option_id, user_id) VALUES ({ph(3)})",
            (poll_id, option_id, current_user.id),
        )

    flash("Vote cast!", "success")
    return redirect(url_for("pulse.index"))


# ── Admin: create / close / delete polls ─────────────────────────

@pulse_bp.route("/create", methods=["GET", "POST"])
def create():
    if not _is_admin():
        flash("Admin access required.", "error")
        return redirect(url_for("pulse.index"))

    if request.method == "POST":
        question = request.form.get("question", "").strip()
        options_raw = request.form.get("options", "").strip()

        if not question:
            flash("Question is required.", "error")
            return redirect(url_for("pulse.create"))

        options = [o.strip() for o in options_raw.split("\n") if o.strip()]
        if len(options) < 2:
            flash("At least 2 options are required (one per line).", "error")
            return redirect(url_for("pulse.create"))

        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                f"INSERT INTO polls (question) VALUES ({ph()})", (question,)
            )
            # Get the new poll id
            cur.execute("SELECT MAX(id) FROM polls")
            poll_id = cur.fetchone()[0]

            for label in options:
                cur.execute(
                    f"INSERT INTO poll_options (poll_id, label) VALUES ({ph(2)})",
                    (poll_id, label),
                )

        flash("Poll created!", "success")
        return redirect(url_for("pulse.index"))

    return render_template("pulse/create.html")


@pulse_bp.route("/close/<int:poll_id>", methods=["POST"])
def close(poll_id):
    if not _is_admin():
        flash("Admin access required.", "error")
        return redirect(url_for("pulse.index"))

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE polls SET is_active = {ph()} WHERE id = {ph()}", (False, poll_id))

    flash("Poll closed.", "success")
    return redirect(url_for("pulse.index"))


@pulse_bp.route("/reopen/<int:poll_id>", methods=["POST"])
def reopen(poll_id):
    if not _is_admin():
        flash("Admin access required.", "error")
        return redirect(url_for("pulse.index"))

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE polls SET is_active = {ph()} WHERE id = {ph()}", (True, poll_id))

    flash("Poll reopened.", "success")
    return redirect(url_for("pulse.index"))


@pulse_bp.route("/delete/<int:poll_id>", methods=["POST"])
def delete(poll_id):
    if not _is_admin():
        flash("Admin access required.", "error")
        return redirect(url_for("pulse.index"))

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"DELETE FROM poll_votes WHERE poll_id = {ph()}", (poll_id,))
        cur.execute(f"DELETE FROM poll_options WHERE poll_id = {ph()}", (poll_id,))
        cur.execute(f"DELETE FROM polls WHERE id = {ph()}", (poll_id,))

    flash("Poll deleted.", "success")
    return redirect(url_for("pulse.index"))


# ── Admin: manage Pulse videos (Game Show & Podcast) ─────────────

@pulse_bp.route("/add-video", methods=["POST"])
def add_video():
    if not _is_admin():
        flash("Admin access required.", "error")
        return redirect(url_for("pulse.index"))

    raw_url = request.form.get("youtube_url", "")
    title = request.form.get("title", "").strip()
    section = request.form.get("section", "game-show").strip()

    if section not in ("game-show", "podcast"):
        section = "game-show"

    yt_id = _extract_youtube_id(raw_url)
    if not yt_id:
        flash("Invalid YouTube URL or video ID.", "error")
        return redirect(url_for("pulse.index"))
    if not title:
        flash("Title is required.", "error")
        return redirect(url_for("pulse.index"))

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"INSERT INTO pulse_videos (youtube_id, title, section) VALUES ({ph(3)})",
            (yt_id, title, section),
        )

    flash("Video added!", "success")
    return redirect(url_for("pulse.index"))


@pulse_bp.route("/delete-video/<int:video_id>", methods=["POST"])
def delete_video(video_id):
    if not _is_admin():
        flash("Admin access required.", "error")
        return redirect(url_for("pulse.index"))

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"DELETE FROM pulse_videos WHERE id = {ph()}", (video_id,))

    flash("Video removed.", "success")
    return redirect(url_for("pulse.index"))


# ── Admin: Live Now settings ─────────────────────────────────────

@pulse_bp.route("/live-settings", methods=["POST"])
def live_settings():
    if not _is_admin():
        flash("Admin access required.", "error")
        return redirect(url_for("pulse.index"))

    live_active = "1" if request.form.get("live_active") else "0"
    youtube_id_raw = request.form.get("live_youtube_id", "").strip()
    twitch_channel = request.form.get("live_twitch_channel", "").strip()

    # Extract YouTube video/stream ID if a full URL is given
    yt_id = ""
    if youtube_id_raw:
        extracted = _extract_youtube_id(youtube_id_raw)
        yt_id = extracted if extracted else youtube_id_raw

    with get_conn() as conn:
        cur = conn.cursor()
        _set_setting(cur, "live_active", live_active)
        _set_setting(cur, "live_youtube_id", yt_id)
        _set_setting(cur, "live_twitch_channel", twitch_channel)

    flash("Live settings updated!", "success")
    return redirect(url_for("pulse.index"))
