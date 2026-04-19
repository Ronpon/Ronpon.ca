"""Auth routes — register, login, logout, profile."""
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_user, logout_user, login_required, current_user
from flask_bcrypt import generate_password_hash

from models.user import User
from models.db import get_conn, ph

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    # Registration is only available when no users exist (first-run admin setup)
    if User.count() > 0:
        abort(404)

    if current_user.is_authenticated:
        return redirect(url_for("main.home"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        # --- validation ---
        errors = []
        if not username or len(username) < 3:
            errors.append("Username must be at least 3 characters.")
        if not email or "@" not in email:
            errors.append("Enter a valid email.")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        if password != confirm:
            errors.append("Passwords do not match.")
        if User.get_by_username(username):
            errors.append("Username already taken.")
        if User.get_by_email(email):
            errors.append("Email already registered.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("auth/register.html",
                                   username=username, email=email)

        user = User.create(username, email, password)
        login_user(user)
        flash("Account created!", "success")
        return redirect(url_for("main.home"))

    return render_template("auth/register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.get_by_username(username)
        if user and user.check_password(password):
            login_user(user, remember=True)
            next_page = request.args.get("next")
            flash("Logged in.", "success")
            return redirect(next_page or url_for("main.home"))

        flash("Invalid username or password.", "error")
        return render_template("auth/login.html", username=username)

    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out.", "success")
    return redirect(url_for("main.home"))


@auth_bp.route("/social/<provider>")
def social_login(provider):
    flash(f"{provider.title()} login coming soon!", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/profile")
@login_required
def profile():
    return render_template("auth/profile.html")


@auth_bp.route("/change-password", methods=["POST"])
@login_required
def change_password():
    current_pw = request.form.get("current_password", "")
    new_pw = request.form.get("new_password", "")
    confirm_pw = request.form.get("confirm_password", "")

    if not current_user.check_password(current_pw):
        flash("Current password is incorrect.", "error")
        return redirect(url_for("auth.profile"))

    if len(new_pw) < 6:
        flash("New password must be at least 6 characters.", "error")
        return redirect(url_for("auth.profile"))

    if new_pw != confirm_pw:
        flash("New passwords do not match.", "error")
        return redirect(url_for("auth.profile"))

    pw_hash = generate_password_hash(new_pw).decode("utf-8")
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE users SET pw_hash = {ph()} WHERE id = {ph()}",
            (pw_hash, current_user.id),
        )

    flash("Password updated successfully.", "success")
    return redirect(url_for("auth.profile"))


@auth_bp.route("/delete-account", methods=["POST"])
@login_required
def delete_account():
    password = request.form.get("password", "")

    if not current_user.check_password(password):
        flash("Incorrect password.", "error")
        return redirect(url_for("auth.profile"))

    user_id = current_user.id
    logout_user()

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"DELETE FROM poll_votes WHERE user_id = {ph()}", (user_id,))
        cur.execute(f"DELETE FROM users WHERE id = {ph()}", (user_id,))

    flash("Your account has been deleted.", "success")
    return redirect(url_for("main.home"))
