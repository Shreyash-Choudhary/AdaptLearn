# Database Setup Guide

## Overview
This document explains how to set up and use the database for the AI Adaptive Learning System.

---

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Database Connection

You have two options:

#### Option A: PostgreSQL (Recommended for Production)
```bash
# Install PostgreSQL: https://www.postgresql.org/download/
# Create a database:
psql -U postgres
CREATE DATABASE adaptive_learning;
\q
```

Then update `.env`:
```
DATABASE_URL=postgresql://postgres:your_password@localhost:5432/adaptive_learning
```

#### Option B: SQLite (Quick Development)
Edit `.env`:
```
DATABASE_URL=sqlite:///adaptive_learning.db
```

### 3. Initialize Database
```bash
python db_init.py
```

This creates all tables:
- `users` - Student and faculty accounts
- `documents` - Uploaded PDFs
- `concepts` - Text chunks from PDFs
- `questions` - Generated quiz questions
- `attempts` - Quiz submission history
- `concept_mastery` - Per-student mastery tracking
- `revision_schedules` - Predicted revision dates

### 4. Run the App
```bash
python app.py
```

Visit `http://localhost:5000`

---

## Database Schema Overview

### Users Table
```
id (PK) | username | email | password_hash | full_name | role | created_at
```
- `role`: "student" or "faculty"

### Documents Table
```
id (PK) | title | filename | uploader_id (FK) | extracted_text | summary | file_size | created_at
```

### Concepts Table
```
id (PK) | document_id (FK) | title | content | chunk_index | difficulty_level | created_at
```
- Concepts are text chunks from a PDF
- One document can have many concepts

### Questions Table
```
id (PK) | concept_id (FK) | question_text | question_type | options (JSON) | correct_answer | difficulty_score | created_at
```
- `question_type`: "mcq" or "short_answer"
- `options`: JSON array like ["option A", "option B", "option C", "option D"]

### Attempts Table
```
id (PK) | user_id (FK) | question_id (FK) | user_answer | is_correct | response_time_seconds | attempt_number | attempted_at
```
- **Most important for ML**: Stores every quiz submission
- Links student → question → concept → document

### ConceptMastery Table
```
id (PK) | user_id (FK) | concept_id (FK) | mastery_score | total_attempts | correct_attempts | last_attempted_at | last_correct_at
```
- Summarizes student's understanding of each concept
- Example: "student 5 got concept 12 correct 7/10 times = 0.7 mastery"

### RevisionSchedule Table
```
id (PK) | user_id (FK) | concept_id (FK) | next_revision_date | forgetting_probability | interval_days | schedule_reason | was_revised | revised_at
```
- **For spaced repetition**: Stores predicted next revision date
- Will be populated by the forgetting prediction model

---

## How Data Flows Through the System

### When a PDF is Uploaded:
1. User uploads PDF via `/upload`
2. System extracts text → saves to `Document.extracted_text`
3. Text is summarized → saved to `Document.summary`
4. Quiz questions are generated → saved to `Question` table
5. Concepts (text chunks) are created → saved to `Concept` table
6. Questions are linked to concepts

Example:
```
Document {id: 1, title: "Math101.pdf"}
├── Concept {id: 1, title: "Algebra", chunk_index: 0}
│   ├── Question {id: 1, text: "2+2=?"}
│   ├── Question {id: 2, text: "3x+5=8, solve for x"}
├── Concept {id: 2, title: "Geometry", chunk_index: 1}
│   ├── Question {id: 3, text: "Area of circle?"}
```

### When a Student Takes a Quiz:
1. Student answers questions via `/submit`
2. System creates `Attempt` record for each answer
3. System updates `ConceptMastery` scores
4. System calculates next revision interval (placeholder for now)
5. Future: System predicts next revision date in `RevisionSchedule`

Example:
```
Student 5 attempts Document 1:
├── Question 1: CORRECT ✓   → Attempt {user_id: 5, q_id: 1, is_correct: true}
├── Question 2: WRONG ✗     → Attempt {user_id: 5, q_id: 2, is_correct: false}
└── Question 3: CORRECT ✓   → Attempt {user_id: 5, q_id: 3, is_correct: true}

ConceptMastery updated:
├── Concept 1: 1/2 = 0.5 mastery (1 correct out of 2 attempts)
└── Concept 2: 1/1 = 1.0 mastery (1 correct out of 1 attempt)
```

---

## Useful Database Queries

### View All Attempts for a Student
```python
from models import User, Attempt
user = User.query.filter_by(username="student1").first()
attempts = Attempt.query.filter_by(user_id=user.id).all()
for attempt in attempts:
    print(f"Q{attempt.question_id}: {attempt.is_correct}")
```

### Get Student Mastery Across All Concepts
```python
from models import ConceptMastery
mastery = ConceptMastery.query.filter_by(user_id=5).all()
for m in mastery:
    print(f"Concept {m.concept_id}: {m.mastery_score:.2%}")
```

### Check Pending Revisions
```python
from models import RevisionSchedule
from datetime import datetime
pending = RevisionSchedule.query.filter(
    RevisionSchedule.next_revision_date <= datetime.utcnow(),
    RevisionSchedule.was_revised == False
).all()
```

### Export Data for Training ML Model
```python
import pandas as pd
from models import Attempt, ConceptMastery

# Get all attempts as CSV
attempts = Attempt.query.all()
df = pd.DataFrame([
    {
        'user_id': a.user_id,
        'question_id': a.question_id,
        'is_correct': a.is_correct,
        'response_time_seconds': a.response_time_seconds,
        'attempted_at': a.attempted_at
    }
    for a in attempts
])
df.to_csv('training_data.csv', index=False)
```

---

## Next Steps

### Phase 2: Add Authentication
- User login/signup system
- Replace "default_student" with actual users
- Faculty dashboard access control

### Phase 3: Build Forgetting Prediction Model
- Collect 2-4 weeks of student data
- Train XGBoost model on `Attempt` + `ConceptMastery` data
- Populate `RevisionSchedule` table with predictions
- Build reminder notifications

### Phase 4: Adaptive Revision
- Auto-generate micro-quizzes for due concepts
- Send reminders via email/in-app
- Track revision compliance

### Phase 5: Analytics Dashboards
- Student: mastery heatmap, revision calendar, performance trends
- Faculty: class-wide retention, concept difficulty analysis, struggling students

---

## Troubleshooting

### "database doesn't exist" error
```bash
# Create the database first:
createdb adaptive_learning
python db_init.py
```

### "connection refused" error
Make sure PostgreSQL is running:
```bash
# On Windows:
net start postgresql-x64-15

# On Mac:
brew services start postgresql

# On Linux:
sudo systemctl start postgresql
```

### "table already exists" error
Drop all tables and reinitialize:
```bash
python db_init.py drop
python db_init.py
```

### Want to see SQL queries being executed?
In `config.py`, set `SQLALCHEMY_ECHO = True`

---

## Files Created/Modified

- ✅ `models.py` - Database models (tables)
- ✅ `config.py` - Database configuration
- ✅ `db_init.py` - Database initialization script
- ✅ `.env.example` - Environment variable template
- ✅ `app.py` - Updated to save data to database
- ✅ `requirements.txt` - Added Flask-SQLAlchemy, psycopg2

All database operations are integrated. Your app now **persists all data**.

