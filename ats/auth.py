"""
Simple 2-user auth system. Passwords stored as env vars (hashed).
To generate a new password hash: python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('yourpassword'))"
"""

import os
from functools import wraps
from flask import session, redirect, url_for, request
from werkzeug.security import check_password_hash, generate_password_hash

# Users loaded from env vars — set these on Render
USERS = {
    os.getenv("ADMIN_USERNAME", "connor"): {
        "password_hash": os.getenv("ADMIN_PASSWORD_HASH", generate_password_hash(os.getenv("ADMIN_PASSWORD", "changeme123"))),
        "display_name": os.getenv("ADMIN_DISPLAY_NAME", "Connor"),
        "role": "admin",
        "avatar": os.getenv("ADMIN_AVATAR", "C"),
    },
    os.getenv("USER2_USERNAME", "user2"): {
        "password_hash": os.getenv("USER2_PASSWORD_HASH", generate_password_hash(os.getenv("USER2_PASSWORD", "changeme456"))),
        "display_name": os.getenv("USER2_DISPLAY_NAME", "Partner"),
        "role": "editor",
        "avatar": os.getenv("USER2_AVATAR", "P"),
    }
}


def verify_login(username: str, password: str) -> dict | None:
    user = USERS.get(username.lower().strip())
    if user and check_password_hash(user["password_hash"], password):
        return {"username": username, **user}
    return None


def login_user(username: str, display_name: str, role: str, avatar: str):
    session.permanent = True
    session["user"] = {"username": username, "display_name": display_name,
                       "role": role, "avatar": avatar}


def logout_user():
    session.pop("user", None)


def current_user() -> dict | None:
    return session.get("user")


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user():
            return redirect(f"/ats/login?next={request.path}")
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = current_user()
        if not user:
            return redirect(f"/ats/login?next={request.path}")
        if user.get("role") != "admin":
            return redirect("/ats/")
        return f(*args, **kwargs)
    return decorated
