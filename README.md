# Class Pulse (Flask prototype)

A lightweight **course-based classroom interaction** prototype:
- Students join a course and post **comments/questions** (optionally anonymous)
- Lecturers **view** comments and **resolve** them with an optional note
- Student feed **auto-refreshes** (polling every 3 seconds)

## 1) Run (Windows / macOS / Linux)

> Uses only: `Flask==2.3.3` + built-in `sqlite3` (no extra DB setup).

### Option A: Run directly (recommended)
```bash
python app.py
```

Then open:
- http://127.0.0.1:5000/

### Option B: (If you need to install deps)
```bash
pip install -r requirements.txt
python app.py
```

## 2) Lecturer password
Default lecturer password is `admin`.

You can change it by setting an environment variable:
- Windows (PowerShell):
```powershell
$env:CLASS_PULSE_ADMIN_PASSWORD (legacy CAMPUS_PULSE_ADMIN_PASSWORD also works)="yourPassword"
python app.py
```
- macOS/Linux:
```bash
CLASS_PULSE_ADMIN_PASSWORD (legacy CAMPUS_PULSE_ADMIN_PASSWORD also works)="yourPassword" python app.py
```

## 3) Demo flow
1. Student joins **CS101** (pre-created demo course) → submits a comment
2. Lecturer logs in → opens **CS101** → resolves the comment with a note
3. Student sees status update in the live feed

## 4) Where data is stored
SQLite DB file is created automatically at:
- `instance/class_pulse.db`

## 5) Manual test checklist (for your coursework evidence)
- **US1 Submit comment**: after submit, the comment appears in the live feed
- **US2 View confirmation**: a success message is shown after submission
- **US3 View comments**: lecturer can open a course and view all comments
- **US4 Resolve comment**: lecturer marks a comment as resolved; student sees status

---
Built for coursework prototyping, not production security.


## 6) Danmaku (bullet screen)
- Open questions float across both Student and Lecturer screens.
- Students can click a danmaku to **like** it.
- More likes => different color (heat levels).


## FAQ: Why can't I see danmaku / why are likes not changing?
1) **The lecturer must open a specific course page** (click `Open` in the Lecturer Dashboard). Danmaku is shown on the course page.
2) Danmaku only shows questions with **status=open**. If the lecturer clicks `Resolve`, that item disappears from danmaku.
3) Likes are deduplicated within the same browser session, so the same window/session can only like the same item once.
   To simulate likes from other students, use **a different browser / incognito window / different device**.
