import os
import sqlite3
import uuid
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for, flash,
    session, jsonify, g, abort
)

APP_NAME = "Class Pulse"
DB_FILENAME = "class_pulse.db"

def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config["SECRET_KEY"] = os.environ.get("CLASS_PULSE_SECRET") or os.environ.get("CAMPUS_PULSE_SECRET", "dev-secret-change-me")
    app.config["ADMIN_PASSWORD"] = os.environ.get("CLASS_PULSE_ADMIN_PASSWORD") or os.environ.get("CAMPUS_PULSE_ADMIN_PASSWORD", "admin")
    app.config["DATABASE"] = os.path.join(app.instance_path, DB_FILENAME)

    # Ensure instance folder exists
    os.makedirs(app.instance_path, exist_ok=True)

    @app.before_request
    def _ensure_db():
        init_db()
        # A stable anonymous token per browser session to prevent repeated likes
        if "liker_token" not in session:
            session["liker_token"] = str(uuid.uuid4())
        # A stable student token used to determine comment ownership
        if "student_token" not in session:
            session["student_token"] = str(uuid.uuid4())

    def get_db():
        if "db" not in g:
            conn = sqlite3.connect(app.config["DATABASE"])
            conn.row_factory = sqlite3.Row
            g.db = conn
        return g.db

    @app.teardown_appcontext
    def close_db(exc):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    
    def init_db():
        db_path = app.config["DATABASE"]
        first_time = not os.path.exists(db_path)

        db = sqlite3.connect(db_path)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON;")

        # Core schema (idempotent)
        db.executescript(
            '''
            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                display_name TEXT,
                anonymous INTEGER NOT NULL DEFAULT 1,
                author_token TEXT,
                status TEXT NOT NULL DEFAULT 'open',
                previous_status TEXT,
                lecturer_note TEXT,
                praised INTEGER NOT NULL DEFAULT 0,
                likes INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                resolved_at TEXT,
                deleted_at TEXT,
                FOREIGN KEY (course_id) REFERENCES courses (id) ON DELETE CASCADE
            );

            -- Track likes to prevent duplicate likes per session token
            CREATE TABLE IF NOT EXISTS comment_likes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                comment_id INTEGER NOT NULL,
                liker_token TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(comment_id, liker_token),
                FOREIGN KEY (comment_id) REFERENCES comments (id) ON DELETE CASCADE
            );
            '''
        )

        # Lightweight migration for older DBs: add likes column if missing
        cols = [r["name"] for r in db.execute("PRAGMA table_info(comments)").fetchall()]
        if "likes" not in cols:
            db.execute("ALTER TABLE comments ADD COLUMN likes INTEGER NOT NULL DEFAULT 0;")
        if "author_token" not in cols:
            db.execute("ALTER TABLE comments ADD COLUMN author_token TEXT;")
        if "previous_status" not in cols:
            db.execute("ALTER TABLE comments ADD COLUMN previous_status TEXT;")
        if "deleted_at" not in cols:
            db.execute("ALTER TABLE comments ADD COLUMN deleted_at TEXT;")
        if "praised" not in cols:
            db.execute("ALTER TABLE comments ADD COLUMN praised INTEGER NOT NULL DEFAULT 0;")

        # 修正历史数据：有填写姓名的评论应为非匿名
        db.execute(
            """
            UPDATE comments
            SET anonymous = 0
            WHERE display_name IS NOT NULL AND TRIM(display_name) <> ''
            """
        )

        # Seed demo course on first init
        if first_time:
            db.execute(
                "INSERT OR IGNORE INTO courses (code, name, created_at) VALUES (?, ?, datetime('now'))",
                ("CS101", "Demo Course: CS101",)
            )

        db.commit()
        db.close()


    def require_lecturer(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("is_lecturer"):
                return redirect(url_for("lecturer_login", next=request.path))
            return view(*args, **kwargs)
        return wrapped

    def require_course(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("course_id"):
                flash("Please join a course first.", "warning")
                return redirect(url_for("index"))
            return view(*args, **kwargs)
        return wrapped

    def now_iso():
        return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    @app.route("/", methods=["GET"])
    def index():
        db = get_db()
        courses = db.execute("SELECT id, code, name FROM courses ORDER BY created_at DESC").fetchall()
        return render_template("index.html", app_name=APP_NAME, courses=courses)

    @app.route("/about", methods=["GET"])
    def about():
        return render_template("about.html", app_name=APP_NAME)

    @app.route("/student/join", methods=["POST"])
    def student_join():
        course_code = (request.form.get("course_code") or "").strip().upper()
        display_name = (request.form.get("display_name") or "").strip()
        anonymous = 0 if display_name else 1

        if not course_code:
            flash("Course code is required.", "danger")
            return redirect(url_for("index"))

        db = get_db()
        course = db.execute("SELECT id, code, name FROM courses WHERE code = ?", (course_code,)).fetchone()
        if course is None:
            flash(f"Course '{course_code}' not found. Ask your lecturer to create it.", "warning")
            return redirect(url_for("index"))

        session["course_id"] = int(course["id"])
        session["course_code"] = course["code"]
        session["course_name"] = course["name"]
        session["student_display_name"] = display_name
        session["student_anonymous"] = anonymous
        # Refresh identities when a student joins/re-joins.
        session["liker_token"] = str(uuid.uuid4())
        session["student_token"] = str(uuid.uuid4())

        flash(f"Joined {course['code']} — {course['name']}.", "success")
        return redirect(url_for("student_room"))

    @app.route("/student", methods=["GET"])
    @require_course
    def student_room():
        course_id = int(session["course_id"])
        course_code = session.get("course_code", "")
        course_name = session.get("course_name", "")
        display_name = session.get("student_display_name", "")
        anonymous = int(session.get("student_anonymous", 1))

        return render_template(
            "student.html",
            app_name=APP_NAME,
            course_id=course_id,
            course_code=course_code,
            course_name=course_name,
            display_name=display_name,
            anonymous=anonymous
        )

    @app.route("/student/comment", methods=["POST"])
    @require_course
    def student_comment():
        content = (request.form.get("content") or "").strip()
        if not content:
            flash("Comment cannot be empty.", "danger")
            return redirect(url_for("student_room"))

        course_id = int(session["course_id"])
        display_name = (session.get("student_display_name") or "").strip()
        anonymous = 0 if display_name else 1

        db = get_db()
        db.execute(
            """
            INSERT INTO comments (course_id, content, display_name, anonymous, author_token, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'open', ?)
            """,
            (course_id, content, display_name if display_name else None, anonymous, session.get("student_token"), now_iso())
        )
        db.commit()

        flash("Submitted! Your comment is now visible to the lecturer.", "success")
        return redirect(url_for("student_room"))

    @app.route("/student/leave", methods=["POST"])
    def student_leave():
        for k in ["course_id", "course_code", "course_name", "student_display_name", "student_anonymous", "student_token"]:
            session.pop(k, None)
        flash("You left the course.", "info")
        return redirect(url_for("index"))

    # --- Lecturer ---
    @app.route("/lecturer/login", methods=["GET", "POST"])
    def lecturer_login():
        if request.method == "POST":
            password = request.form.get("password") or ""
            if password == app.config["ADMIN_PASSWORD"]:
                session["is_lecturer"] = True
                flash("Logged in as lecturer.", "success")
                nxt = request.args.get("next") or url_for("lecturer_dashboard")
                return redirect(nxt)
            flash("Wrong password.", "danger")

        return render_template("lecturer_login.html", app_name=APP_NAME)

    @app.route("/lecturer/logout", methods=["POST"])
    def lecturer_logout():
        session.pop("is_lecturer", None)
        flash("Logged out.", "info")
        return redirect(url_for("index"))

    @app.route("/lecturer", methods=["GET"])
    @require_lecturer
    def lecturer_dashboard():
        db = get_db()
        courses = db.execute("SELECT id, code, name, created_at FROM courses ORDER BY created_at DESC").fetchall()
        return render_template("lecturer_dashboard.html", app_name=APP_NAME, courses=courses)

    @app.route("/lecturer/course/create", methods=["POST"])
    @require_lecturer
    def lecturer_create_course():
        code = (request.form.get("code") or "").strip().upper()
        name = (request.form.get("name") or "").strip()

        if not code or not name:
            flash("Both course code and course name are required.", "danger")
            return redirect(url_for("lecturer_dashboard"))

        db = get_db()
        try:
            db.execute(
                "INSERT INTO courses (code, name, created_at) VALUES (?, ?, ?)",
                (code, name, now_iso())
            )
            db.commit()
            flash(f"Course {code} created.", "success")
        except sqlite3.IntegrityError:
            flash(f"Course code '{code}' already exists.", "warning")

        return redirect(url_for("lecturer_dashboard"))

    @app.route("/lecturer/course/<int:course_id>", methods=["GET"])
    @require_lecturer
    def lecturer_course(course_id: int):
        db = get_db()
        course = db.execute("SELECT id, code, name FROM courses WHERE id = ?", (course_id,)).fetchone()
        if course is None:
            abort(404)

        status = request.args.get("status", "open").strip().lower()
        if status not in ("open", "resolved", "deleted", "all"):
            status = "open"

        if status == "all":
            comments = db.execute(
                """
                SELECT * FROM comments
                WHERE course_id = ?
                ORDER BY created_at DESC
                """,
                (course_id,)
            ).fetchall()
        else:
            comments = db.execute(
                """
                SELECT * FROM comments
                WHERE course_id = ? AND status = ?
                ORDER BY created_at DESC
                """,
                (course_id, status)
            ).fetchall()

        return render_template(
            "lecturer_course.html",
            app_name=APP_NAME,
            course=course,
            comments=comments,
            status=status
        )

    @app.route("/lecturer/comment/<int:comment_id>/resolve", methods=["POST"])
    @require_lecturer
    def lecturer_resolve_comment(comment_id: int):
        note = (request.form.get("lecturer_note") or "").strip()
        db = get_db()
        db.execute(
            """
            UPDATE comments
            SET status = 'resolved',
                lecturer_note = ?,
                resolved_at = ?
            WHERE id = ?
            """,
            (note if note else None, now_iso(), comment_id)
        )
        db.commit()
        flash("Marked as resolved.", "success")

        course_id = request.form.get("course_id")
        if course_id:
            return redirect(url_for("lecturer_course", course_id=int(course_id), status=request.args.get("status", "open")))
        return redirect(url_for("lecturer_dashboard"))

    @app.route("/lecturer/comment/<int:comment_id>/reopen", methods=["POST"])
    @require_lecturer
    def lecturer_reopen_comment(comment_id: int):
        db = get_db()
        db.execute(
            """
            UPDATE comments
            SET status = 'open',
                resolved_at = NULL
            WHERE id = ?
            """,
            (comment_id,)
        )
        db.commit()
        flash("Re-opened.", "info")
        course_id = request.form.get("course_id")
        if course_id:
            return redirect(url_for("lecturer_course", course_id=int(course_id), status=request.args.get("status", "open")))
        return redirect(url_for("lecturer_dashboard"))

    # --- API (polling for "real-time") ---
    @app.route("/api/comments/<int:course_id>", methods=["GET"])
    def api_comments(course_id: int):
        db = get_db()
        rows = db.execute(
            """
            SELECT c.id, c.content, c.display_name, c.anonymous, c.author_token, c.status,
                   c.previous_status, c.lecturer_note, c.praised, c.created_at, c.resolved_at, c.deleted_at, c.likes
            FROM comments c
            WHERE c.course_id = ?
            ORDER BY c.created_at DESC
            LIMIT 100
            """,
            (course_id,)
        ).fetchall()

        def format_name(r):
            if r["display_name"] and str(r["display_name"]).strip():
                return r["display_name"]
            return "Anonymous"

        data = []
        student_token = session.get("student_token")
        is_lecturer = bool(session.get("is_lecturer"))
        for r in rows:
            is_owner = bool(student_token and r["author_token"] and student_token == r["author_token"])
            can_delete = is_lecturer or is_owner
            can_undo = is_lecturer or is_owner
            data.append({
                "id": int(r["id"]),
                "content": r["content"],
                "name": format_name(r),
                "status": r["status"],
                "previous_status": r["previous_status"],
                "lecturer_note": r["lecturer_note"],
                "praised": int(r["praised"] or 0),
                "created_at": r["created_at"],
                "resolved_at": r["resolved_at"],
                "deleted_at": r["deleted_at"],
                "likes": int(r["likes"]),
                "is_owner": is_owner,
                "can_delete": can_delete,
                "can_undo": can_undo,
            })
        return jsonify({"course_id": course_id, "comments": data})

    
    @app.route("/api/like/<int:comment_id>", methods=["POST"])
    def api_like(comment_id: int):
        """
        Like a comment (danmaku). Uses session["liker_token"] to prevent repeat likes.
        """
        db = get_db()
        token = session.get("liker_token")
        if not token:
            token = str(uuid.uuid4())
            session["liker_token"] = token

        row = db.execute("SELECT id, likes FROM comments WHERE id = ?", (comment_id,)).fetchone()
        if row is None:
            return jsonify({"ok": False, "reason": "not_found"}), 404

        try:
            db.execute(
                "INSERT INTO comment_likes (comment_id, liker_token, created_at) VALUES (?, ?, ?)",
                (comment_id, token, now_iso())
            )
            db.execute("UPDATE comments SET likes = likes + 1 WHERE id = ?", (comment_id,))
            db.commit()
        except sqlite3.IntegrityError:
            current = db.execute("SELECT likes FROM comments WHERE id = ?", (comment_id,)).fetchone()
            return jsonify({"ok": False, "reason": "already_liked", "likes": int(current["likes"])}), 200

        current = db.execute("SELECT likes FROM comments WHERE id = ?", (comment_id,)).fetchone()
        return jsonify({"ok": True, "likes": int(current["likes"])}), 200


    @app.route("/api/honors/<int:course_id>", methods=["GET"])
    def api_honors(course_id: int):
        db = get_db()
        rows = db.execute(
            """
            SELECT
                COALESCE(NULLIF(display_name, ''), CASE WHEN anonymous = 1 THEN 'Anonymous' ELSE 'Student' END) AS student_name,
                COUNT(*) AS praise_count,
                MAX(created_at) AS latest_time
            FROM comments
            WHERE course_id = ? AND praised = 1 AND status != 'deleted'
            GROUP BY author_token, student_name
            ORDER BY praise_count DESC, latest_time DESC
            LIMIT 5
            """,
            (course_id,)
        ).fetchall()
        data = [
            {"name": r["student_name"], "praise_count": int(r["praise_count"])}
            for r in rows
        ]
        return jsonify({"course_id": course_id, "honors": data})

    @app.route("/lecturer/comment/<int:comment_id>/praise", methods=["POST"])
    @require_lecturer
    def lecturer_praise_comment(comment_id: int):
        db = get_db()
        db.execute(
            "UPDATE comments SET praised = 1 WHERE id = ? AND status != 'deleted'",
            (comment_id,)
        )
        db.commit()
        flash("Comment praised.", "success")
        course_id = request.form.get("course_id")
        if course_id:
            return redirect(url_for("lecturer_course", course_id=int(course_id), status=request.args.get("status", "open")))
        return redirect(url_for("lecturer_dashboard"))

    @app.route("/lecturer/comment/<int:comment_id>/unpraise", methods=["POST"])
    @require_lecturer
    def lecturer_unpraise_comment(comment_id: int):
        db = get_db()
        db.execute("UPDATE comments SET praised = 0 WHERE id = ?", (comment_id,))
        db.commit()
        flash("Praise removed.", "info")
        course_id = request.form.get("course_id")
        if course_id:
            return redirect(url_for("lecturer_course", course_id=int(course_id), status=request.args.get("status", "open")))
        return redirect(url_for("lecturer_dashboard"))

    @app.route("/comment/<int:comment_id>/delete", methods=["POST"])
    def delete_comment(comment_id: int):
        db = get_db()
        row = db.execute(
            "SELECT id, author_token, status, course_id FROM comments WHERE id = ?",
            (comment_id,)
        ).fetchone()
        if row is None:
            flash("Comment not found.", "danger")
            return redirect(request.referrer or url_for("index"))

        is_lecturer = bool(session.get("is_lecturer"))
        is_owner = bool(session.get("student_token") and row["author_token"] and session.get("student_token") == row["author_token"])
        if not (is_lecturer or is_owner):
            flash("You do not have permission to delete this comment.", "danger")
            return redirect(request.referrer or url_for("index"))

        if row["status"] != "deleted":
            db.execute(
                """
                UPDATE comments
                SET previous_status = status,
                    status = 'deleted',
                    deleted_at = ?,
                    resolved_at = CASE WHEN status = 'resolved' THEN resolved_at ELSE resolved_at END
                WHERE id = ?
                """,
                (now_iso(), comment_id)
            )
            db.commit()
            flash("Comment deleted.", "info")
        else:
            flash("Comment is already deleted.", "warning")
        return redirect(request.referrer or url_for("index"))

    @app.route("/comment/<int:comment_id>/undo", methods=["POST"])
    def undo_delete_comment(comment_id: int):
        db = get_db()
        row = db.execute(
            "SELECT id, author_token, status, previous_status FROM comments WHERE id = ?",
            (comment_id,)
        ).fetchone()
        if row is None:
            flash("Comment not found.", "danger")
            return redirect(request.referrer or url_for("index"))

        is_lecturer = bool(session.get("is_lecturer"))
        is_owner = bool(session.get("student_token") and row["author_token"] and session.get("student_token") == row["author_token"])
        if not (is_lecturer or is_owner):
            flash("You do not have permission to undo this action.", "danger")
            return redirect(request.referrer or url_for("index"))

        if row["status"] == "deleted":
            restore_status = row["previous_status"] or "open"
            db.execute(
                """
                UPDATE comments
                SET status = ?,
                    previous_status = NULL,
                    deleted_at = NULL
                WHERE id = ?
                """,
                (restore_status, comment_id)
            )
            db.commit()
            flash("Delete action undone.", "success")
        else:
            flash("This comment is not deleted.", "warning")
        return redirect(request.referrer or url_for("index"))

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok", "app": APP_NAME})
    return app


app = create_app()

if __name__ == "__main__":
    # For local development only
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host=host, port=port, debug=debug)
