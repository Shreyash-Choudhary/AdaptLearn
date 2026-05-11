"""
app.py — ENHANCED VERSION
Original features + new additions:
  1. Flashcard study mode before every quiz (/flashcards/<doc_id>)
  2. Standalone flashcard practice page from My Documents
  3. Full personalized performance dashboard (/dashboard)
     - KPI overview, score trend, forgetting pattern graph
     - Concept mastery table, weak topics, activity heatmap
     - Retention risk chart, upcoming revision schedule
  4. Flashcard generation via Groq API (flashcard_generator.py)
  5. All original features preserved
"""

from dotenv import load_dotenv
load_dotenv()

import os
import traceback
from datetime import datetime

from flask import Flask, request, render_template, redirect, url_for, session, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy.exc import IntegrityError

from config import CONFIG
from models import (
    db, User, Document, Concept, Question, Attempt,
    ConceptMastery, StudentFeature,
    update_concept_mastery, schedule_next_revision, RevisionSchedule
)
from pdf_utils import extract_text_from_pdf
from summarizer import summarize_text
from quiz_generator import generate_quiz
from predictor import predict_revision
from flashcard_generator import generate_flashcards

# ─────────────────────────────────────────────
# APP SETUP
# ─────────────────────────────────────────────
app = Flask(__name__)
app.config.from_object(CONFIG)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret")

db.init_app(app)

# ─────────────────────────────────────────────
# LOGIN MANAGER
# ─────────────────────────────────────────────
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ─────────────────────────────────────────────
# FILE UPLOAD CONFIG
# ─────────────────────────────────────────────
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# ─────────────────────────────────────────────
# DB INIT
# ─────────────────────────────────────────────
with app.app_context():
    db.create_all()


# ═══════════════════════════════════════════════════════════
# HELPER — get pending revision notifications for current user
# ═══════════════════════════════════════════════════════════
def get_notifications(user_id):
    """
    Returns list of dicts for revisions that are due today or overdue.
    Each dict has: concept_name, document_title, doc_id, days_overdue
    """
    now = datetime.utcnow()
    due_schedules = RevisionSchedule.query.filter(
        RevisionSchedule.user_id == user_id,
        RevisionSchedule.was_revised == False,
        RevisionSchedule.next_revision_date <= now
    ).all()

    notifications = []
    for s in due_schedules:
        concept = Concept.query.get(s.concept_id)
        doc = Document.query.get(concept.document_id) if concept else None
        if doc:
            days_overdue = (now - s.next_revision_date).days
            notifications.append({
                "schedule_id": s.id,
                "concept_name": concept.title,
                "document_title": doc.title,
                "doc_id": doc.id,
                "days_overdue": days_overdue
            })
    return notifications


# ═══════════════════════════════════════════════════════════
# ROUTES — AUTH
# ═══════════════════════════════════════════════════════════

@app.route("/")
def index():
    if not current_user.is_authenticated:
        return redirect(url_for("login"))
    notifications = get_notifications(current_user.id)
    return render_template("upload.html", user=current_user, notifications=notifications)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        user = User.query.filter_by(username=username).first()
        if not user or not user.check_password(password):
            flash("Invalid credentials", "error")
            return render_template("login.html")
        login_user(user)
        return redirect(url_for("index"))
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email    = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        if User.query.filter_by(username=username).first():
            flash("Username already exists", "error")
            return render_template("register.html")

        if User.query.filter_by(email=email).first():
            flash("Email already registered. Please login.", "error")
            return render_template("register.html")

        user = User(username=username, email=email)
        user.set_password(password)
        try:
            db.session.add(user)
            db.session.commit()
            flash("Registration successful! Please login.", "success")
            return redirect(url_for("login"))
        except IntegrityError:
            db.session.rollback()
            flash("Something went wrong. Try again.", "error")

    return render_template("register.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# ═══════════════════════════════════════════════════════════
# ROUTES — UPLOAD (first time PDF upload)
# ═══════════════════════════════════════════════════════════

@app.route("/upload", methods=["POST"])
@login_required
def upload():
    try:
        file = request.files.get("pdf_file")
        if not file or file.filename == "":
            flash("No file selected", "error")
            return redirect(url_for("index"))

        filename = secure_filename(file.filename)
        path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(path)

        text    = extract_text_from_pdf(path)
        summary = summarize_text(text)
        quiz    = generate_quiz(summary)

        # Save document to DB
        doc = Document(
            title=filename,
            filename=filename,
            uploader_id=current_user.id,
            extracted_text=text,
            summary=summary,
            file_size=os.path.getsize(path)
        )
        db.session.add(doc)
        db.session.flush()  # get doc.id before concept creation

        # Create one concept per document (the summary chunk)
        concept = Concept(
            document_id=doc.id,
            title=filename,
            content=summary,
            chunk_index=0,
            difficulty_level=0.5
        )
        db.session.add(concept)
        db.session.flush()

        # Save quiz questions to DB linked to this concept
        for q in quiz:
            question_obj = Question(
                concept_id=concept.id,
                question_text=q["question"],
                question_type="mcq",
                options=q["options"],
                correct_answer=q["correct_answer"],
                difficulty_score=0.5
            )
            db.session.add(question_obj)

        db.session.commit()

        # Store in session for submit handler
        session["quiz"]              = quiz
        session["document_id"]       = doc.id
        session["student_user_id"]   = current_user.id

        # ── NEW: show flashcards FIRST, then quiz ──────────────────
        # Generate flashcards and cache them
        try:
            fc = generate_flashcards(summary)
            session["flashcards"]       = fc
            session["flashcard_doc_id"] = doc.id
        except Exception:
            session["flashcards"] = []

        return redirect(url_for("flashcards", doc_id=doc.id))

    except Exception:
        print(traceback.format_exc())
        flash("Upload failed. Please try again.", "error")
        return redirect(url_for("index"))


# ═══════════════════════════════════════════════════════════
# ROUTES — QUIZ FROM EXISTING DOCUMENT (no re-upload needed)
# This is what the notification "Start Test" button calls.
# ═══════════════════════════════════════════════════════════

@app.route("/quiz-from-document/<int:doc_id>")
@login_required
def quiz_from_document(doc_id):
    """
    Generate a fresh quiz from an already-uploaded document.
    The PDF is NOT re-uploaded — we use the stored summary.
    After submission the loop continues: score saved → new revision scheduled.
    """
    doc = Document.query.filter_by(id=doc_id, uploader_id=current_user.id).first()
    if not doc:
        flash("Document not found.", "error")
        return redirect(url_for("my_documents"))

    try:
        # Mark this revision as "started" (was_revised = True) so it clears from notifications
        concept = Concept.query.filter_by(document_id=doc.id).first()
        if concept:
            schedule = RevisionSchedule.query.filter_by(
                user_id=current_user.id,
                concept_id=concept.id,
                was_revised=False
            ).first()
            if schedule:
                schedule.was_revised = True
                schedule.revised_at  = datetime.utcnow()
                db.session.commit()

        # Generate new quiz questions from the stored summary
        quiz = generate_quiz(doc.summary)

        # Save new questions to DB (fresh batch for this attempt)
        if concept:
            for q in quiz:
                question_obj = Question(
                    concept_id=concept.id,
                    question_text=q["question"],
                    question_type="mcq",
                    options=q["options"],
                    correct_answer=q["correct_answer"],
                    difficulty_score=0.5
                )
                db.session.add(question_obj)
            db.session.commit()

        # Store in session
        session["quiz"]            = quiz
        session["document_id"]     = doc.id
        session["student_user_id"] = current_user.id

        return render_template(
            "quiz.html",
            questions=quiz,
            summary=doc.summary,
            document_title=doc.title
        )

    except Exception:
        print(traceback.format_exc())
        flash("Could not generate quiz. Please try again.", "error")
        return redirect(url_for("my_documents"))


# ═══════════════════════════════════════════════════════════
# ROUTES — SUBMIT QUIZ
# Saves every attempt to the DB, then redirects to difficulty
# ═══════════════════════════════════════════════════════════

@app.route("/submit", methods=["POST"])
@login_required
def submit():
    quiz_questions   = session.get("quiz", [])
    student_user_id  = session.get("student_user_id")
    document_id      = session.get("document_id")

    if not quiz_questions or not student_user_id:
        flash("Session expired. Please start again.", "error")
        return redirect(url_for("index"))

    total   = len(quiz_questions)
    correct = 0
    results = []

    # Load questions from DB for this document so we can save attempts
    doc = Document.query.get(document_id) if document_id else None
    questions_from_db = []
    if doc:
        concept_ids = [c.id for c in doc.concepts]
        if concept_ids:
            questions_from_db = (
                Question.query
                .filter(Question.concept_id.in_(concept_ids))
                .order_by(Question.id.desc())           # latest batch first
                .limit(len(quiz_questions))
                .all()[::-1]                            # restore original order
            )

    # ── Grade answers + save attempts ──────────────────────────────
    for i, question in enumerate(quiz_questions):
        user_answer    = request.form.get(f"answer_{i}", "").strip()
        correct_answer = question.get("correct_answer", "").strip()
        is_correct     = user_answer.upper() == correct_answer.upper()
        if is_correct:
            correct += 1

        # Save attempt to DB
        question_obj = questions_from_db[i] if i < len(questions_from_db) else None
        if question_obj:
            # Calculate days since last attempt on this specific question
            last_attempt = (
                Attempt.query
                .filter_by(user_id=student_user_id, question_id=question_obj.id)
                .order_by(Attempt.attempted_at.desc())
                .first()
            )
            days_since_last = None
            if last_attempt:
                diff = datetime.utcnow() - last_attempt.attempted_at
                days_since_last = round(diff.total_seconds() / 86400, 4)

            attempt_number = (
                Attempt.query
                .filter_by(user_id=student_user_id, question_id=question_obj.id)
                .count()
            ) + 1

            attempt = Attempt(
                user_id=student_user_id,
                question_id=question_obj.id,
                user_answer=user_answer if user_answer else "skipped",
                is_correct=is_correct,
                response_time_seconds=0,
                attempt_number=attempt_number,
                days_since_last_attempt=days_since_last
            )
            db.session.add(attempt)

            # Update concept mastery
            if question_obj.concept_id:
                update_concept_mastery(student_user_id, question_obj.concept_id, is_correct)

        results.append({
            "question":       question["question"],
            "options":        question["options"],
            "correct_answer": correct_answer,
            "user_answer":    user_answer,
            "is_correct":     is_correct
        })

    db.session.commit()

    score_percent = round((correct / total) * 100, 2) if total > 0 else 0
    print(f"[INFO] Quiz submitted: {correct}/{total} = {score_percent}%  (user={student_user_id})")

    # Save to session for predict step
    session["total"]         = total
    session["correct"]       = correct
    session["results"]       = results
    session["score_percent"] = score_percent

    return render_template("select_difficulty.html")


# ═══════════════════════════════════════════════════════════
# ROUTES — PREDICT (after difficulty dropdown)
# Runs ML model, saves StudentFeature + RevisionSchedule
# ═══════════════════════════════════════════════════════════

@app.route("/predict", methods=["POST"])
@login_required
def predict():
    student_user_id = current_user.id
    difficulty      = request.form.get("difficulty", "medium")
    diff_map        = {"easy": 1, "medium": 2, "hard": 3}
    diff_numeric    = diff_map.get(difficulty.lower(), 2)

    score_percent = session.get("score_percent", 0)
    document_id   = session.get("document_id")

    all_attempts = Attempt.query.filter_by(user_id=student_user_id).all()
    if all_attempts:
        avg = round(sum(100 if a.is_correct else 0 for a in all_attempts) / len(all_attempts), 2)
    else:
        avg = score_percent

    category = "Topper" if avg >= 75 else "Average" if avg >= 50 else "Weak"

    # ── ML Prediction ──────────────────────────────────────────────
    revision_info = None
    try:
        revision_info = predict_revision(
            student_historical_avg=avg,
            diff_numeric=diff_numeric,
            all_scores_this_concept=[score_percent],
            days_since_last_attempt=0
        )
        print(f"[PREDICT] revision_info={revision_info}")
    except Exception:
        print("[PREDICT] ML error:")
        print(traceback.format_exc())
        revision_info = {"revise_in_days": 7, "revision_date": "", "urgency": "moderate"}

    # ── Save StudentFeature + RevisionSchedule for each concept ────
    doc = Document.query.get(document_id) if document_id else None
    if doc and doc.concepts:
        for concept in doc.concepts:
            # StudentFeature row
            feature = StudentFeature(
                user_id=student_user_id,
                concept_id=concept.id,
                student_category=category,
                student_historical_avg=avg,
                concept_name=concept.title,
                concept_difficulty=difficulty,
                diff_numeric=diff_numeric,
                latest_quiz_score=score_percent,
                avg_quiz_score=score_percent,
                num_attempts=len(all_attempts),
                days_since_last_attempt=0,
                retention_score=100 - score_percent,
                days_until_revision=revision_info["revise_in_days"]
            )
            db.session.add(feature)

            # RevisionSchedule row
            schedule_next_revision(
                user_id=student_user_id,
                concept_id=concept.id,
                interval_days=int(revision_info["revise_in_days"]),
                forgetting_prob=round(1 - (score_percent / 100), 2),
                reason=revision_info["urgency"]
            )
        db.session.commit()
        print(f"[PREDICT] Saved features + schedule for {len(doc.concepts)} concept(s)")

    session["document_id"] = document_id  # keep for result page

    return render_template(
        "result.html",
        total=session.get("total", 0),
        correct=session.get("correct", 0),
        results=session.get("results", []),
        score_percent=score_percent,
        revision_info=revision_info,
        document_id=document_id
    )


# ═══════════════════════════════════════════════════════════
# ROUTES — MY DOCUMENTS
# ═══════════════════════════════════════════════════════════

@app.route("/my-documents")
@login_required
def my_documents():
    documents = (
        Document.query
        .filter_by(uploader_id=current_user.id)
        .order_by(Document.created_at.desc())
        .all()
    )

    document_stats = []
    for doc in documents:
        concepts  = Concept.query.filter_by(document_id=doc.id).count()
        questions = (
            Question.query.join(Concept)
            .filter(Concept.document_id == doc.id)
            .count()
        )
        attempts = (
            Attempt.query.join(Question).join(Concept)
            .filter(Concept.document_id == doc.id, Attempt.user_id == current_user.id)
            .count()
        )
        document_stats.append({
            "doc":       doc,
            "concepts":  concepts,
            "questions": questions,
            "attempts":  attempts
        })

    notifications = get_notifications(current_user.id)
    return render_template(
        "my_documents.html",
        document_stats=document_stats,
        notifications=notifications
    )


# ═══════════════════════════════════════════════════════════
# ROUTES — MY REVISIONS
# ═══════════════════════════════════════════════════════════

@app.route("/my-revisions")
@login_required
def my_revisions():
    schedules = (
        RevisionSchedule.query
        .filter_by(user_id=current_user.id, was_revised=False)
        .order_by(RevisionSchedule.next_revision_date.asc())
        .all()
    )

    revision_list = []
    for s in schedules:
        concept = Concept.query.get(s.concept_id)
        doc     = Document.query.get(concept.document_id) if concept else None
        days_left = (s.next_revision_date - datetime.utcnow()).days
        revision_list.append({
            "schedule_id":    s.id,
            "concept_name":   concept.title if concept else "Unknown",
            "document_title": doc.title if doc else "Unknown",
            "doc_id":         doc.id if doc else None,
            "revision_date":  s.next_revision_date.strftime("%b %d, %Y"),
            "days_left":      max(0, days_left),
            "urgency":        s.schedule_reason,
            "forgetting_prob": round(s.forgetting_probability * 100, 2),
            "is_due":         days_left <= 0
        })

    notifications = get_notifications(current_user.id)
    return render_template(
        "my_revisions.html",
        revision_list=revision_list,
        notifications=notifications
    )


# ═══════════════════════════════════════════════════════════
# API — notifications count (for live badge updates)
# ═══════════════════════════════════════════════════════════

@app.route("/api/notifications")
@login_required
def api_notifications():
    """Returns JSON with pending notification count — used by JS polling."""
    notifs = get_notifications(current_user.id)
    return jsonify({"count": len(notifs), "notifications": notifs})


# ═══════════════════════════════════════════════════════════
# NEW: FLASHCARDS — study mode before quiz (from upload flow)
# ═══════════════════════════════════════════════════════════

@app.route("/flashcards/<int:doc_id>")
@login_required
def flashcards(doc_id):
    """
    Show flashcard study session for a document BEFORE the quiz.
    Generates 10 flashcards from the document summary via Groq.
    """
    doc = Document.query.filter_by(id=doc_id, uploader_id=current_user.id).first()
    if not doc:
        flash("Document not found.", "error")
        return redirect(url_for("my_documents"))

    try:
        # Check if flashcards are cached in session (same doc, same session)
        cached_doc_id = session.get("flashcard_doc_id")
        cached_cards  = session.get("flashcards")
        if cached_doc_id == doc_id and cached_cards:
            flashcard_list = cached_cards
        else:
            flashcard_list = generate_flashcards(doc.summary)
            session["flashcards"]       = flashcard_list
            session["flashcard_doc_id"] = doc_id

        return render_template(
            "flashcards.html",
            flashcards=flashcard_list,
            document_title=doc.title,
            doc_id=doc_id
        )
    except Exception:
        print(traceback.format_exc())
        flash("Could not generate flashcards. Proceeding to quiz.", "error")
        return redirect(url_for("quiz_from_document", doc_id=doc_id))


# ═══════════════════════════════════════════════════════════
# NEW: FLASHCARDS — after upload (redirect here first)
# Intercept the upload flow to show flashcards before quiz
# ═══════════════════════════════════════════════════════════

@app.route("/flashcards-from-upload")
@login_required
def flashcards_from_upload():
    """
    After upload, redirect here to study flashcards.
    Session must have document_id set from the upload step.
    """
    doc_id = session.get("document_id")
    if not doc_id:
        flash("No document in session. Please upload again.", "error")
        return redirect(url_for("index"))
    return redirect(url_for("flashcards", doc_id=doc_id))


# ═══════════════════════════════════════════════════════════
# NEW: PERSONALIZED DASHBOARD
# Full performance analytics dashboard for the student
# ═══════════════════════════════════════════════════════════

@app.route("/dashboard")
@login_required
def dashboard():
    """
    Personalized performance dashboard with:
    - KPI tiles (avg score, total attempts, docs, pending revisions)
    - Score trend over time
    - Forgetting pattern visualization
    - Concept mastery table
    - Weak topic list (mastery < 50%)
    - Upcoming revision schedule
    - Per-document activity bar chart
    - Retention risk chart
    - Activity heatmap (last 30 days)
    """
    import json
    from collections import defaultdict

    uid = current_user.id

    # ── All attempts for this user ──────────────────────────────
    all_attempts = (
        Attempt.query
        .filter_by(user_id=uid)
        .order_by(Attempt.attempted_at.asc())
        .all()
    )
    total_attempts  = len(all_attempts)
    total_correct   = sum(1 for a in all_attempts if a.is_correct)
    total_incorrect = total_attempts - total_correct
    overall_avg     = round((total_correct / total_attempts) * 100, 1) if total_attempts > 0 else 0

    # ── Student level ────────────────────────────────────────────
    if overall_avg >= 75:
        student_level = "Topper"
    elif overall_avg >= 50:
        student_level = "Average"
    else:
        student_level = "Weak"

    # ── Score trend (group by quiz session = document) ───────────
    # Each RevisionSchedule creation marks a quiz session; use StudentFeature for trend
    features = (
        StudentFeature.query
        .filter_by(user_id=uid)
        .order_by(StudentFeature.created_at.asc())
        .all()
    )
    score_trend = [round(f.latest_quiz_score, 1) for f in features] if features else []
    if not score_trend:
        # Fall back to per-question attempt grouping (group by date)
        by_day = defaultdict(list)
        for a in all_attempts:
            day = a.attempted_at.strftime("%Y-%m-%d")
            by_day[day].append(1 if a.is_correct else 0)
        score_trend = [round(sum(v)/len(v)*100, 1) for v in by_day.values()]

    # ── Concept mastery data ─────────────────────────────────────
    mastery_records = ConceptMastery.query.filter_by(user_id=uid).all()
    mastery_data = []
    weak_topics  = []
    for m in mastery_records:
        concept = Concept.query.get(m.concept_id)
        doc     = Document.query.get(concept.document_id) if concept else None
        pct     = round(m.mastery_score * 100, 1)
        item    = {
            "concept_name":  concept.title if concept else "Unknown",
            "doc_title":     doc.title if doc else "Unknown",
            "mastery_pct":   pct,
            "total_attempts": m.total_attempts,
            "correct":        m.correct_attempts,
        }
        mastery_data.append(item)
        if pct < 50:
            weak_topics.append({
                "name": concept.title if concept else "Unknown",
                "doc":  doc.title if doc else "Unknown",
                "pct":  pct,
            })

    mastery_data.sort(key=lambda x: x["mastery_pct"])
    weak_topics.sort(key=lambda x: x["pct"])

    # ── Document activity (attempts per document) ─────────────────
    documents = Document.query.filter_by(uploader_id=uid).all()
    total_documents = len(documents)
    doc_activity = []
    for doc in documents:
        concept_ids = [c.id for c in doc.concepts]
        if not concept_ids:
            continue
        n = (
            Attempt.query
            .join(Question)
            .filter(Question.concept_id.in_(concept_ids), Attempt.user_id == uid)
            .count()
        )
        doc_activity.append({"label": doc.title[:25], "value": n})
    doc_activity.sort(key=lambda x: x["value"], reverse=True)

    # ── Activity heatmap (last 30 days) ───────────────────────────
    date_counts = defaultdict(int)
    for a in all_attempts:
        d = a.attempted_at.strftime("%Y-%m-%d")
        date_counts[d] += 1
    activity_dates = list(date_counts.items())

    # ── Upcoming revisions ────────────────────────────────────────
    from datetime import timedelta
    pending_schedules = (
        RevisionSchedule.query
        .filter_by(user_id=uid, was_revised=False)
        .order_by(RevisionSchedule.next_revision_date.asc())
        .limit(8)
        .all()
    )
    pending_revisions = len(pending_schedules)
    upcoming_revisions = []
    for s in pending_schedules:
        concept = Concept.query.get(s.concept_id)
        doc     = Document.query.get(concept.document_id) if concept else None
        days_left = max(0, (s.next_revision_date - datetime.utcnow()).days)
        upcoming_revisions.append({
            "concept":   concept.title if concept else "Unknown",
            "doc":       doc.title if doc else "Unknown",
            "date":      s.next_revision_date.strftime("%b %d"),
            "days_left": days_left,
        })

    # ── Retention risk per concept ────────────────────────────────
    retention_data = []
    for m in mastery_records[:6]:
        concept = Concept.query.get(m.concept_id)
        risk    = round((1 - m.mastery_score) * 100, 0)
        retention_data.append({
            "label": concept.title[:20] if concept else "Unknown",
            "risk":  risk,
        })
    retention_data.sort(key=lambda x: x["risk"], reverse=True)

    return render_template(
        "dashboard.html",
        student_name      = current_user.username,
        student_level     = student_level,
        overall_avg       = overall_avg,
        total_attempts    = total_attempts,
        total_documents   = total_documents,
        pending_revisions = pending_revisions,
        mastery_data      = mastery_data,
        weak_topics       = weak_topics[:6],
        upcoming_revisions= upcoming_revisions,
        total_correct     = total_correct,
        total_incorrect   = total_incorrect,
        # JSON for charts
        score_trend_json    = json.dumps(score_trend),
        mastery_json        = json.dumps(mastery_data),
        doc_activity_json   = json.dumps(doc_activity),
        activity_dates_json = json.dumps(activity_dates),
        retention_json      = json.dumps(retention_data),
    )


# ═══════════════════════════════════════════════════════════
# NEW: API — get flashcards for a document (AJAX endpoint)
# ═══════════════════════════════════════════════════════════

@app.route("/api/flashcards/<int:doc_id>")
@login_required
def api_flashcards(doc_id):
    """Returns JSON list of flashcards for given document."""
    doc = Document.query.filter_by(id=doc_id, uploader_id=current_user.id).first()
    if not doc:
        return jsonify({"error": "Document not found"}), 404
    try:
        cards = generate_flashcards(doc.summary)
        return jsonify({"flashcards": cards, "count": len(cards)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ═══════════════════════════════════════════════════════════
# RUN
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    app.run(debug=True)