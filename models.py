"""
models.py - SQLAlchemy ORM Models
AI Based Adaptive Learning and Forgetting Prediction System
Defines all database tables and relationships
"""
from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from sqlalchemy import Index, func
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    """User table: students and faculty"""
    __tablename__ = "users"
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120))
    role = db.Column(db.String(20), default="student")  # "student" or "faculty"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    documents = db.relationship("Document", back_populates="uploader", foreign_keys="Document.uploader_id")
    attempts = db.relationship("Attempt", back_populates="user")
    concept_mastery = db.relationship("ConceptMastery", back_populates="user", cascade="all, delete-orphan")
    revision_schedules = db.relationship("RevisionSchedule", back_populates="user", cascade="all, delete-orphan")
    
    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Verify password against hash"""
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f"<User {self.username}>"


class Document(db.Model):
    """Document table: uploaded PDFs"""
    __tablename__ = "documents"
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    uploader_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    extracted_text = db.Column(db.Text, nullable=True)  # Full text from PDF
    summary = db.Column(db.Text, nullable=True)  # Summarized text
    file_size = db.Column(db.Integer)  # Size in bytes
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    uploader = db.relationship("User", back_populates="documents", foreign_keys=[uploader_id])
    concepts = db.relationship("Concept", back_populates="document", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Document {self.title}>"


class Concept(db.Model):
    """Concept table: chunks/topics extracted from documents"""
    __tablename__ = "concepts"
    
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)  # Extracted chunk of text
    chunk_index = db.Column(db.Integer)  # Order within document
    difficulty_level = db.Column(db.Float, default=0.5)  # Estimated difficulty (0-1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    document = db.relationship("Document", back_populates="concepts")
    questions = db.relationship("Question", back_populates="concept", cascade="all, delete-orphan")
    concept_mastery = db.relationship("ConceptMastery", back_populates="concept", cascade="all, delete-orphan")
    revision_schedules = db.relationship("RevisionSchedule", back_populates="concept", cascade="all, delete-orphan")
    
    __table_args__ = (Index("idx_document_id", "document_id"),)
    
    def __repr__(self):
        return f"<Concept {self.title}>"


class Question(db.Model):
    """Question table: auto-generated quiz questions"""
    __tablename__ = "questions"
    
    id = db.Column(db.Integer, primary_key=True)
    concept_id = db.Column(db.Integer, db.ForeignKey("concepts.id"), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    question_type = db.Column(db.String(50))  # "mcq" or "short_answer"
    options = db.Column(db.JSON, nullable=True)  # List of options for MCQ
    correct_answer = db.Column(db.Text, nullable=False)
    difficulty_score = db.Column(db.Float, default=0.5)  # 0-1, updated based on student performance
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    concept = db.relationship("Concept", back_populates="questions")
    attempts = db.relationship("Attempt", back_populates="question")
    
    __table_args__ = (Index("idx_concept_id", "concept_id"),)
    
    def __repr__(self):
        return f"<Question {self.id}>"


class Attempt(db.Model):
    """Attempt table: quiz attempt history with scores"""
    __tablename__ = "attempts"
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id"), nullable=False)
    user_answer = db.Column(db.Text, nullable=False)
    is_correct = db.Column(db.Boolean, default=False)
    response_time_seconds = db.Column(db.Integer, nullable=True)  # Time spent on this question
    attempt_number = db.Column(db.Integer, default=1)  # 1st, 2nd, 3rd attempt on same question
    days_since_last_attempt = db.Column(db.Float, nullable=True)  # Days gap from previous attempt on this question
    attempted_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    user = db.relationship("User", back_populates="attempts")
    question = db.relationship("Question", back_populates="attempts")
    
    __table_args__ = (
        Index("idx_user_id", "user_id"),
        Index("idx_question_id", "question_id"),
        Index("idx_attempted_at", "attempted_at"),
        Index("idx_user_question", "user_id", "question_id"),
    )
    
    def __repr__(self):
        return f"<Attempt {self.id}>"


class ConceptMastery(db.Model):
    """ConceptMastery table: per-student mastery score per concept"""
    __tablename__ = "concept_mastery"
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    concept_id = db.Column(db.Integer, db.ForeignKey("concepts.id"), nullable=False)
    mastery_score = db.Column(db.Float, default=0.0)  # 0-1, based on correct attempts
    total_attempts = db.Column(db.Integer, default=0)
    correct_attempts = db.Column(db.Integer, default=0)
    last_attempted_at = db.Column(db.DateTime, nullable=True)
    last_correct_at = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship("User", back_populates="concept_mastery")
    concept = db.relationship("Concept", back_populates="concept_mastery")
    
    __table_args__ = (
        Index("idx_user_concept", "user_id", "concept_id"),
        db.UniqueConstraint("user_id", "concept_id", name="uq_user_concept"),
    )
    
    def update_mastery(self):
        """Recalculate mastery score based on correct_attempts / total_attempts"""
        if self.total_attempts > 0:
            self.mastery_score = self.correct_attempts / self.total_attempts
        self.updated_at = datetime.utcnow()
    
    def __repr__(self):
        return f"<ConceptMastery user={self.user_id} concept={self.concept_id}>"


class RevisionSchedule(db.Model):
    """RevisionSchedule table: predicted next revision dates per student-concept"""
    __tablename__ = "revision_schedules"
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    concept_id = db.Column(db.Integer, db.ForeignKey("concepts.id"), nullable=False)
    next_revision_date = db.Column(db.DateTime, nullable=False, index=True)  # When to revise
    forgetting_probability = db.Column(db.Float, default=0.5)  # 0-1, prob of forgetting by next_revision_date
    interval_days = db.Column(db.Integer)  # Gap from last attempt to next revision
    schedule_reason = db.Column(db.String(255))  # Why this interval was chosen
    was_revised = db.Column(db.Boolean, default=False)  # Did student revise by that date?
    revised_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship("User", back_populates="revision_schedules")
    concept = db.relationship("Concept", back_populates="revision_schedules")
    
    __table_args__ = (
        Index("idx_user_next_revision", "user_id", "next_revision_date"),
        Index("idx_concept_next_revision", "concept_id", "next_revision_date"),
    )
    
    def __repr__(self):
        return f"<RevisionSchedule user={self.user_id} concept={self.concept_id} date={self.next_revision_date}>"


# ===================================================================
# Helper functions to update summarized data
# ===================================================================

def update_concept_mastery(user_id, concept_id, is_correct):
    """
    Update ConceptMastery record after an attempt.
    Called immediately after an attempt is recorded.
    """
    mastery = ConceptMastery.query.filter_by(user_id=user_id, concept_id=concept_id).first()
    
    if not mastery:
        mastery = ConceptMastery(user_id=user_id, concept_id=concept_id, total_attempts=0, correct_attempts=0, mastery_score=0.0)
        db.session.add(mastery)
    
    # Initialize to 0 if None
    if mastery.total_attempts is None:
        mastery.total_attempts = 0
    if mastery.correct_attempts is None:
        mastery.correct_attempts = 0
    
    mastery.total_attempts += 1
    if is_correct:
        mastery.correct_attempts += 1
        mastery.last_correct_at = datetime.utcnow()
    
    mastery.last_attempted_at = datetime.utcnow()
    mastery.update_mastery()
    
    db.session.commit()
    return mastery


def schedule_next_revision(user_id, concept_id, interval_days, forgetting_prob, reason="auto"):
    """
    Create or update a RevisionSchedule record.
    Called by the forgetting prediction model to schedule next revision.
    """
    schedule = RevisionSchedule.query.filter_by(user_id=user_id, concept_id=concept_id).first()
    
    next_date = datetime.utcnow() + timedelta(days=interval_days)
    
    if not schedule:
        schedule = RevisionSchedule(
            user_id=user_id,
            concept_id=concept_id,
            next_revision_date=next_date,
            forgetting_probability=forgetting_prob,
            interval_days=interval_days,
            schedule_reason=reason
        )
        db.session.add(schedule)
    else:
        schedule.next_revision_date = next_date
        schedule.forgetting_probability = forgetting_prob
        schedule.interval_days = interval_days
        schedule.schedule_reason = reason
        schedule.updated_at = datetime.utcnow()
    
    db.session.commit()
    return schedule
class StudentFeature(db.Model):
    """ML Training Feature Table"""
    __tablename__ = "student_features"

    id = db.Column(db.Integer, primary_key=True)

    # Student Info
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    student_category = db.Column(db.String(20))  # Weak / Average / Topper
    student_historical_avg = db.Column(db.Float)

    # Concept Info
    concept_id = db.Column(db.Integer, db.ForeignKey("concepts.id"), nullable=False)
    concept_name = db.Column(db.String(255))
    subject = db.Column(db.String(100))
    concept_difficulty = db.Column(db.String(20))  # Easy / Medium / Hard
    diff_numeric = db.Column(db.Integer)

    # Performance
    num_attempts = db.Column(db.Integer)
    latest_quiz_score = db.Column(db.Float)
    avg_quiz_score = db.Column(db.Float)
    score_trend = db.Column(db.Float)

    # Time + Memory
    days_since_last_attempt = db.Column(db.Float)
    retention_score = db.Column(db.Float)
    days_until_revision = db.Column(db.Float)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
