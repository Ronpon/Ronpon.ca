"""The Pulse: game show, podcast, polls, and live stream routes."""
from __future__ import annotations

import re
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user, login_required
from models.db import get_conn, ph

pulse_bp = Blueprint("pulse", __name__)
_MAX_VIDEO_TITLE_LENGTH = 120
_MAX_POLL_TITLE_LENGTH = 140
_MAX_POLL_TEXT_LENGTH = 500
_MAX_POLL_OPTION_LENGTH = 160
_TWITCH_CHANNEL_RE = re.compile(r"^[A-Za-z0-9_]{3,25}$")


def _is_admin():
    return current_user.is_authenticated and current_user.is_admin


def _get_setting(cur, key, default=""):
    cur.execute(f"SELECT value FROM pulse_settings WHERE key = {ph()}", (key,))
    row = cur.fetchone()
    return row[0] if row else default


def _set_setting(cur, key, value):
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


def _last_id(cur, table: str) -> int:
    cur.execute(f"SELECT MAX(id) FROM {table}")
    return cur.fetchone()[0]


def _fetch_poll(cur, poll_id: int):
    cur.execute(f"SELECT id, title, is_active, created_at FROM polls WHERE id = {ph()}", (poll_id,))
    return cur.fetchone()


def _fetch_questions(cur, poll_id: int):
    cur.execute(
        f"SELECT id, question_text, question_order FROM poll_questions "
        f"WHERE poll_id = {ph()} ORDER BY question_order, id",
        (poll_id,),
    )
    return cur.fetchall()


def _fetch_options(cur, question_id: int):
    cur.execute(
        f"SELECT id, label, option_order FROM poll_options "
        f"WHERE question_id = {ph()} ORDER BY option_order, id",
        (question_id,),
    )
    return cur.fetchall()


def _has_submitted(cur, poll_id: int, user_id: int) -> bool:
    cur.execute(
        f"SELECT 1 FROM poll_submissions WHERE poll_id = {ph()} AND user_id = {ph()}",
        (poll_id, user_id),
    )
    return cur.fetchone() is not None


def _question_count_from_form() -> int:
    count = request.form.get("question_count", type=int) or 1
    return max(1, min(count, 50))


def _poll_payload_from_form():
    title = request.form.get("title", "").strip()
    question_count = _question_count_from_form()
    questions = []
    for q_idx in range(1, question_count + 1):
        text = request.form.get(f"question_{q_idx}", "").strip()
        options = [
            request.form.get(f"question_{q_idx}_option_{opt_idx}", "").strip()
            for opt_idx in range(1, 5)
        ]
        questions.append({"text": text, "options": options})
    return title, question_count, questions


def _validate_poll_payload(title: str, questions: list[dict]) -> list[str]:
    errors = []
    if not title:
        errors.append("Poll title is required.")
    elif len(title) > _MAX_POLL_TITLE_LENGTH:
        errors.append(f"Poll title must be {_MAX_POLL_TITLE_LENGTH} characters or fewer.")
    for idx, question in enumerate(questions, start=1):
        if not question["text"]:
            errors.append(f"Question {idx} is required.")
        elif len(question["text"]) > _MAX_POLL_TEXT_LENGTH:
            errors.append(f"Question {idx} is too long.")
        for opt_idx, label in enumerate(question["options"], start=1):
            if not label:
                errors.append(f"Question {idx}, option {opt_idx} is required.")
            elif len(label) > _MAX_POLL_OPTION_LENGTH:
                errors.append(f"Question {idx}, option {opt_idx} is too long.")
    return errors


def _save_poll(cur, title: str, questions: list[dict], poll_id: int | None = None) -> int:
    first_question = questions[0]["text"] if questions else title
    if poll_id is None:
        cur.execute(
            f"INSERT INTO polls (title, question) VALUES ({ph(2)})",
            (title, first_question),
        )
        poll_id = _last_id(cur, "polls")
    else:
        cur.execute(
            f"UPDATE polls SET title = {ph()}, question = {ph()} WHERE id = {ph()}",
            (title, first_question, poll_id),
        )

    for q_order, question in enumerate(questions, start=1):
        q_id_raw = request.form.get(f"question_{q_order}_id", type=int)
        if q_id_raw:
            cur.execute(
                f"UPDATE poll_questions SET question_text = {ph()}, question_order = {ph()} "
                f"WHERE id = {ph()} AND poll_id = {ph()}",
                (question["text"], q_order, q_id_raw, poll_id),
            )
            question_id = q_id_raw
        else:
            cur.execute(
                f"INSERT INTO poll_questions (poll_id, question_text, question_order) VALUES ({ph(3)})",
                (poll_id, question["text"], q_order),
            )
            question_id = _last_id(cur, "poll_questions")

        for opt_order, label in enumerate(question["options"], start=1):
            opt_id_raw = request.form.get(f"question_{q_order}_option_{opt_order}_id", type=int)
            if opt_id_raw:
                cur.execute(
                    f"UPDATE poll_options SET label = {ph()}, option_order = {ph()}, question_id = {ph()} "
                    f"WHERE id = {ph()} AND poll_id = {ph()}",
                    (label, opt_order, question_id, opt_id_raw, poll_id),
                )
            else:
                cur.execute(
                    f"INSERT INTO poll_options (poll_id, question_id, label, option_order) VALUES ({ph(4)})",
                    (poll_id, question_id, label, opt_order),
                )
    cur.execute(
        f"DELETE FROM poll_votes WHERE question_id IN "
        f"(SELECT id FROM poll_questions WHERE poll_id = {ph()} AND question_order > {ph()})",
        (poll_id, len(questions)),
    )
    cur.execute(
        f"DELETE FROM poll_options WHERE question_id IN "
        f"(SELECT id FROM poll_questions WHERE poll_id = {ph()} AND question_order > {ph()})",
        (poll_id, len(questions)),
    )
    cur.execute(
        f"DELETE FROM poll_questions WHERE poll_id = {ph()} AND question_order > {ph()}",
        (poll_id, len(questions)),
    )
    return poll_id


@pulse_bp.route("/")
def index():
    with get_conn() as conn:
        cur = conn.cursor()
        live_active = _get_setting(cur, "live_active", "0") == "1"
        live_youtube_id = _get_setting(cur, "live_youtube_id")
        live_twitch_channel = _get_setting(cur, "live_twitch_channel")

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

        cur.execute("SELECT COUNT(*) FROM polls WHERE is_active")
        available_poll_count = cur.fetchone()[0]

    return render_template(
        "pulse/index.html",
        available_poll_count=available_poll_count,
        is_admin=_is_admin(),
        live_active=live_active,
        live_youtube_id=live_youtube_id,
        live_twitch_channel=live_twitch_channel,
        game_show_videos=game_show_videos,
        podcast_videos=podcast_videos,
    )


@pulse_bp.route("/polls")
def polls():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, title, is_active, created_at FROM polls ORDER BY created_at DESC")
        poll_rows = cur.fetchall()
        polls_data = []
        for poll in poll_rows:
            submitted = False
            answered = 0
            total_questions = len(_fetch_questions(cur, poll[0]))
            if current_user.is_authenticated:
                submitted = _has_submitted(cur, poll[0], current_user.id)
                cur.execute(
                    f"SELECT COUNT(*) FROM poll_votes WHERE poll_id = {ph()} AND user_id = {ph()}",
                    (poll[0], current_user.id),
                )
                answered = cur.fetchone()[0]
            cur.execute(f"SELECT COUNT(*) FROM poll_submissions WHERE poll_id = {ph()}", (poll[0],))
            submissions = cur.fetchone()[0]
            polls_data.append({
                "id": poll[0],
                "title": poll[1],
                "is_active": bool(poll[2]),
                "created_at": poll[3],
                "submitted": submitted,
                "answered": answered,
                "question_count": total_questions,
                "submissions": submissions,
            })
    return render_template("pulse/polls.html", polls=polls_data, is_admin=_is_admin())


@pulse_bp.route("/polls/<int:poll_id>")
@login_required
def take_poll(poll_id):
    with get_conn() as conn:
        cur = conn.cursor()
        poll = _fetch_poll(cur, poll_id)
        if not poll:
            flash("Poll not found.", "error")
            return redirect(url_for("pulse.polls"))
        if not poll[2]:
            flash("This poll is closed.", "error")
            return redirect(url_for("pulse.polls"))
        if _has_submitted(cur, poll_id, current_user.id) and not _is_admin():
            flash("You have already completed that poll.", "error")
            return redirect(url_for("pulse.polls"))

        questions = _fetch_questions(cur, poll_id)
        if not questions:
            flash("This poll has no questions yet.", "error")
            return redirect(url_for("pulse.polls"))

        step = request.args.get("q", type=int) or 1
        step = max(1, min(step, len(questions)))
        question = questions[step - 1]
        options = _fetch_options(cur, question[0])

        cur.execute(
            f"SELECT option_id FROM poll_votes WHERE poll_id = {ph()} AND question_id = {ph()} AND user_id = {ph()}",
            (poll_id, question[0], current_user.id),
        )
        row = cur.fetchone()
        selected_option_id = row[0] if row else None

    return render_template(
        "pulse/take_poll.html",
        poll=poll,
        question=question,
        options=options,
        selected_option_id=selected_option_id,
        step=step,
        total_questions=len(questions),
        remaining=len(questions) - step,
        is_admin=_is_admin(),
    )


@pulse_bp.route("/polls/<int:poll_id>/vote", methods=["POST"])
@login_required
def vote(poll_id):
    step = request.form.get("step", type=int) or 1
    question_id = request.form.get("question_id", type=int)
    option_id = request.form.get("option_id", type=int)
    if not question_id or not option_id:
        flash("Please select an option.", "error")
        return redirect(url_for("pulse.take_poll", poll_id=poll_id, q=step))

    with get_conn() as conn:
        cur = conn.cursor()
        poll = _fetch_poll(cur, poll_id)
        if not poll or not poll[2]:
            flash("This poll is closed.", "error")
            return redirect(url_for("pulse.polls"))
        if _has_submitted(cur, poll_id, current_user.id) and not _is_admin():
            flash("You have already completed that poll.", "error")
            return redirect(url_for("pulse.polls"))

        questions = _fetch_questions(cur, poll_id)
        question_ids = [q[0] for q in questions]
        if question_id not in question_ids:
            flash("Invalid question.", "error")
            return redirect(url_for("pulse.take_poll", poll_id=poll_id, q=step))

        cur.execute(
            f"SELECT 1 FROM poll_options WHERE id = {ph()} AND question_id = {ph()} AND poll_id = {ph()}",
            (option_id, question_id, poll_id),
        )
        if not cur.fetchone():
            flash("Invalid option.", "error")
            return redirect(url_for("pulse.take_poll", poll_id=poll_id, q=step))

        cur.execute(
            f"SELECT id FROM poll_votes WHERE poll_id = {ph()} AND question_id = {ph()} AND user_id = {ph()}",
            (poll_id, question_id, current_user.id),
        )
        existing = cur.fetchone()
        if existing:
            cur.execute(
                f"UPDATE poll_votes SET option_id = {ph()} WHERE id = {ph()}",
                (option_id, existing[0]),
            )
        else:
            cur.execute(
                f"INSERT INTO poll_votes (poll_id, question_id, option_id, user_id) VALUES ({ph(4)})",
                (poll_id, question_id, option_id, current_user.id),
            )

    if step >= len(questions):
        return redirect(url_for("pulse.review_poll", poll_id=poll_id))
    return redirect(url_for("pulse.take_poll", poll_id=poll_id, q=step + 1))


@pulse_bp.route("/polls/<int:poll_id>/review")
@login_required
def review_poll(poll_id):
    with get_conn() as conn:
        cur = conn.cursor()
        poll = _fetch_poll(cur, poll_id)
        if not poll:
            flash("Poll not found.", "error")
            return redirect(url_for("pulse.polls"))
        if _has_submitted(cur, poll_id, current_user.id) and not _is_admin():
            flash("You have already completed that poll.", "error")
            return redirect(url_for("pulse.polls"))
        questions = _fetch_questions(cur, poll_id)
        answered = []
        for idx, question in enumerate(questions, start=1):
            cur.execute(
                f"SELECT o.label FROM poll_votes v JOIN poll_options o ON o.id = v.option_id "
                f"WHERE v.poll_id = {ph()} AND v.question_id = {ph()} AND v.user_id = {ph()}",
                (poll_id, question[0], current_user.id),
            )
            row = cur.fetchone()
            answered.append({"step": idx, "question": question[1], "answer": row[0] if row else None})

    return render_template("pulse/review_poll.html", poll=poll, answered=answered)


@pulse_bp.route("/polls/<int:poll_id>/submit", methods=["POST"])
@login_required
def submit_poll(poll_id):
    with get_conn() as conn:
        cur = conn.cursor()
        poll = _fetch_poll(cur, poll_id)
        if not poll or not poll[2]:
            flash("This poll is closed.", "error")
            return redirect(url_for("pulse.polls"))
        if _has_submitted(cur, poll_id, current_user.id):
            flash("You already completed that poll.", "error")
            return redirect(url_for("pulse.polls"))

        questions = _fetch_questions(cur, poll_id)
        cur.execute(
            f"SELECT COUNT(DISTINCT question_id) FROM poll_votes WHERE poll_id = {ph()} AND user_id = {ph()}",
            (poll_id, current_user.id),
        )
        answered_count = cur.fetchone()[0]
        if answered_count < len(questions):
            flash("Please answer every question before submitting.", "error")
            return redirect(url_for("pulse.take_poll", poll_id=poll_id, q=1))

        cur.execute(
            f"INSERT INTO poll_submissions (poll_id, user_id) VALUES ({ph(2)})",
            (poll_id, current_user.id),
        )

    flash("Poll submitted. Thanks for voting!", "success")
    return redirect(url_for("pulse.polls"))


@pulse_bp.route("/create", methods=["GET", "POST"])
def create():
    if not _is_admin():
        flash("Admin access required.", "error")
        return redirect(url_for("pulse.index"))

    if request.method == "POST":
        title, question_count, questions = _poll_payload_from_form()
        errors = _validate_poll_payload(title, questions)
        if errors:
            for error in errors[:5]:
                flash(error, "error")
            return render_template("pulse/create.html", title=title, question_count=question_count, questions=questions)

        with get_conn() as conn:
            cur = conn.cursor()
            _save_poll(cur, title, questions)

        flash("Poll created!", "success")
        return redirect(url_for("pulse.polls"))

    return render_template("pulse/create.html", title="", question_count=1, questions=[])


@pulse_bp.route("/polls/<int:poll_id>/edit", methods=["GET", "POST"])
def edit_poll(poll_id):
    if not _is_admin():
        flash("Admin access required.", "error")
        return redirect(url_for("pulse.index"))

    with get_conn() as conn:
        cur = conn.cursor()
        poll = _fetch_poll(cur, poll_id)
        if not poll:
            flash("Poll not found.", "error")
            return redirect(url_for("pulse.polls"))

        if request.method == "POST":
            title, question_count, questions = _poll_payload_from_form()
            errors = _validate_poll_payload(title, questions)
            if errors:
                for error in errors[:5]:
                    flash(error, "error")
                return render_template(
                    "pulse/edit_poll.html",
                    poll=poll,
                    title=title,
                    question_count=question_count,
                    questions=questions,
                )
            _save_poll(cur, title, questions, poll_id=poll_id)
            flash("Poll updated.", "success")
            return redirect(url_for("pulse.polls"))

        questions = []
        for question in _fetch_questions(cur, poll_id):
            options = _fetch_options(cur, question[0])
            questions.append({
                "id": question[0],
                "text": question[1],
                "options": [{"id": opt[0], "label": opt[1]} for opt in options],
            })

    return render_template(
        "pulse/edit_poll.html",
        poll=poll,
        title=poll[1],
        question_count=len(questions),
        questions=questions,
    )


@pulse_bp.route("/close/<int:poll_id>", methods=["POST"])
def close(poll_id):
    if not _is_admin():
        flash("Admin access required.", "error")
        return redirect(url_for("pulse.index"))
    with get_conn() as conn:
        conn.cursor().execute(f"UPDATE polls SET is_active = {ph()} WHERE id = {ph()}", (False, poll_id))
    flash("Poll closed.", "success")
    return redirect(url_for("pulse.polls"))


@pulse_bp.route("/reopen/<int:poll_id>", methods=["POST"])
def reopen(poll_id):
    if not _is_admin():
        flash("Admin access required.", "error")
        return redirect(url_for("pulse.index"))
    with get_conn() as conn:
        conn.cursor().execute(f"UPDATE polls SET is_active = {ph()} WHERE id = {ph()}", (True, poll_id))
    flash("Poll reopened.", "success")
    return redirect(url_for("pulse.polls"))


@pulse_bp.route("/delete/<int:poll_id>", methods=["POST"])
def delete(poll_id):
    if not _is_admin():
        flash("Admin access required.", "error")
        return redirect(url_for("pulse.index"))
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"DELETE FROM poll_submissions WHERE poll_id = {ph()}", (poll_id,))
        cur.execute(f"DELETE FROM poll_votes WHERE poll_id = {ph()}", (poll_id,))
        cur.execute(f"DELETE FROM poll_options WHERE poll_id = {ph()}", (poll_id,))
        cur.execute(f"DELETE FROM poll_questions WHERE poll_id = {ph()}", (poll_id,))
        cur.execute(f"DELETE FROM polls WHERE id = {ph()}", (poll_id,))
    flash("Poll deleted.", "success")
    return redirect(url_for("pulse.polls"))


@pulse_bp.route("/polls/<int:poll_id>/results")
def poll_results(poll_id):
    if not _is_admin():
        flash("Admin access required.", "error")
        return redirect(url_for("pulse.index"))

    with get_conn() as conn:
        cur = conn.cursor()
        poll = _fetch_poll(cur, poll_id)
        if not poll:
            flash("Poll not found.", "error")
            return redirect(url_for("pulse.polls"))

        results = []
        questions = _fetch_questions(cur, poll_id)
        for question in questions:
            options_data = []
            total = 0
            for opt in _fetch_options(cur, question[0]):
                cur.execute(
                    f"SELECT COUNT(*) FROM poll_votes v "
                    f"JOIN poll_submissions s ON s.poll_id = v.poll_id AND s.user_id = v.user_id "
                    f"WHERE v.question_id = {ph()} AND v.option_id = {ph()}",
                    (question[0], opt[0]),
                )
                votes = cur.fetchone()[0]
                total += votes
                options_data.append({"id": opt[0], "label": opt[1], "votes": votes})
            for opt in options_data:
                opt["pct"] = round((opt["votes"] / total * 100), 1) if total else 0
            results.append({"question": question[1], "options": options_data, "total": total})

    return render_template("pulse/results.html", poll=poll, results=results)


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
    if len(title) > _MAX_VIDEO_TITLE_LENGTH:
        flash("Title is too long.", "error")
        return redirect(url_for("pulse.index"))

    with get_conn() as conn:
        conn.cursor().execute(
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
        conn.cursor().execute(f"DELETE FROM pulse_videos WHERE id = {ph()}", (video_id,))
    flash("Video removed.", "success")
    return redirect(url_for("pulse.index"))


@pulse_bp.route("/live-settings", methods=["POST"])
def live_settings():
    if not _is_admin():
        flash("Admin access required.", "error")
        return redirect(url_for("pulse.index"))

    live_active = "1" if request.form.get("live_active") else "0"
    youtube_id_raw = request.form.get("live_youtube_id", "").strip()
    twitch_channel = request.form.get("live_twitch_channel", "").strip()
    yt_id = ""
    if youtube_id_raw:
        extracted = _extract_youtube_id(youtube_id_raw)
        if not extracted:
            flash("Invalid YouTube stream URL or video ID.", "error")
            return redirect(url_for("pulse.index"))
        yt_id = extracted
    if twitch_channel.startswith("@"):
        twitch_channel = twitch_channel[1:]
    if twitch_channel and not _TWITCH_CHANNEL_RE.fullmatch(twitch_channel):
        flash("Invalid Twitch channel name.", "error")
        return redirect(url_for("pulse.index"))

    with get_conn() as conn:
        cur = conn.cursor()
        _set_setting(cur, "live_active", live_active)
        _set_setting(cur, "live_youtube_id", yt_id)
        _set_setting(cur, "live_twitch_channel", twitch_channel)

    flash("Live settings updated!", "success")
    return redirect(url_for("pulse.index"))
