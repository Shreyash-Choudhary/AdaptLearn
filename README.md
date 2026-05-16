<div align="center">

# ⚡ AdaptLearn

### AI-Powered Adaptive Learning & Forgetting Prediction System


## 📖 About The Project

AdaptLearn is a full-stack web application that solves one of the biggest problems in education — **students forget what they study**.

Based on the **Ebbinghaus Forgetting Curve** (R = e^(-t/S)), the human brain forgets 50–80% of newly learned information within just a few days without revision. AdaptLearn fights this by:

1. **Automatically generating quiz questions** from any PDF you upload — no manual work needed
2. **Tracking your performance** across every attempt to build your mastery score
3. **Predicting exactly when you will forget** a topic using a trained XGBoost machine learning model
4. **Scheduling personalized revision reminders** before knowledge decay sets in

> Built by students, for students — especially for those preparing for high-stakes exams like JEE, NEET, GATE, and university semester exams.

---

## ✨ Features

### 🤖 AI-Powered Quiz Generation
- Upload any text-based PDF (lecture notes, textbook chapters, question papers)
- AI reads and summarizes the content automatically
- Generates **10 high-quality MCQs** with 4 options each in under 30 seconds
- Choose difficulty level: Easy / Medium / Hard

### 📊 Smart Dashboards
- **Performance Dashboard** — score trend graph + forgetting pattern overlay vs Ebbinghaus curve
- **Concept Mastery Tracker** — per-topic mastery %, progress bar, Weak / Average / Strong labels
- **Detailed Analytics** — accuracy breakdown, retention risk chart, 30-day study heatmap
- **Revision Schedule** — AI-predicted next revision dates with countdown timers

### 🧠 Forgetting Prediction Engine
- XGBoost regression model (R² = **0.936**, MAE = **4.3 days**)
- 8-feature behavioral input: scores, trends, days elapsed, difficulty, retention score
- Urgency labels: **Critical** (≤3 days) / **Soon** (4–7 days) / **Moderate** (8–30 days) / **Good** (>30 days)

### 🔐 Secure Multi-Role Authentication
- Student and Faculty roles with separate access levels
- bcrypt password hashing via Werkzeug
- Flask-Login session management
- All data isolated per user — complete privacy

### 📚 Additional Tools
- **Flashcard Generator** — AI-generated term & definition pairs per document
- **AI Summary** — 150–250 word summary of any uploaded PDF
- **My Documents** — unlimited quiz regeneration from the same PDF (prevents answer memorization)

---

## 🔄 How It Works

```
Student uploads PDF
        ↓
pdfplumber extracts text from all pages
        ↓
Groq LLaMA 3.3 70B summarizes content (150–250 words)
        ↓
LLaMA generates 10 MCQs → 5-stage JSON validation pipeline
        ↓
Student takes quiz → answers saved to PostgreSQL
        ↓
Mastery score updated (correct / total attempts)
        ↓
XGBoost predicts next revision date using 8 behavioral features
        ↓
Urgency label assigned → Revision Schedule updated
        ↓
Student sees dashboard with full learning analytics
```

### The 5-Stage JSON Parsing Pipeline
Raw LLM output is cleaned through these steps to ensure valid quiz data every time:

1. Strip markdown code fences (` ```json ` etc.)
2. Extract substring between first `[` and last `]`
3. Normalize escape sequences
4. Attempt `json.loads()` with 2 recovery fallbacks
5. Validate: exactly 4 options (A/B/C/D) + valid `correct_answer`

✅ Achieves **8–10 valid questions** per document reliably across all subject areas.

---

## 🛠 Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Backend** | Python 3.11 + Flask 3.0 | HTTP routing, Jinja2 templates, REST API |
| **Database** | PostgreSQL 15 + SQLAlchemy ORM | Data persistence, relational schema |
| **Authentication** | Flask-Login + Werkzeug | Session management, bcrypt hashing |
| **PDF Extraction** | pdfplumber | Page-by-page text extraction |
| **AI / LLM** | Groq API — LLaMA 3.3 70B | Summarization and MCQ generation |
| **ML Model** | XGBoost + scikit-learn | Forgetting interval regression |
| **Frontend** | HTML5 + CSS3 + JavaScript | UI, SVG animations, drag-and-drop |
| **Configuration** | python-dotenv | API keys and environment variables |

---

## 🗄 Database Schema

```
users               → id, username, email, password_hash, role
documents           → id, uploader_id, filename, text, summary, created_at
concepts            → id, document_id, content, difficulty
questions           → id, concept_id, question, options (JSON), correct_answer
attempts            → id, user_id, question_id, is_correct, attempted_at, days_since_last
concept_mastery     → user_id, concept_id, mastery_score, total_attempts, correct_attempts
revision_schedules  → user_id, concept_id, next_revision_date, interval_days, urgency
```

---

## 🤖 ML Model

### XGBoost Forgetting Prediction

The core of AdaptLearn is an **XGBoost regression model** that predicts `days_until_revision` — the number of days before a student's retention drops below 80%.

### Input Features (8 total)

| Feature | Description |
|---|---|
| `student_historical_avg` | Mean quiz score across all topics |
| `diff_numeric` | Concept difficulty (1=Easy, 2=Medium, 3=Hard) |
| `num_attempts` | Total attempts on this concept |
| `latest_quiz_score` | Most recent quiz score (0–100) |
| `avg_quiz_score` | Rolling average score on this concept |
| `score_trend` | Slope of linear regression over sequential scores |
| `days_since_last_attempt` | Days elapsed since last quiz |
| `retention_score` | Ebbinghaus estimate: exp(–d / max(s/10, 0.1)) × 100 |

### Model Comparison (Test Set)

| Model | R² | MAE (days) | RMSE (days) |
|---|---|---|---|
| Linear Regression | 0.695 | 14.2 | 17.8 |
| Ridge Regression | 0.695 | 14.1 | 17.8 |
| Decision Tree | 0.868 | 7.9 | 11.6 |
| Random Forest | 0.909 | 5.8 | 9.7 |
| **XGBoost ✅ Selected** | **0.936** | **4.3** | **8.1** |
| KNN | 0.888 | 6.2 | 10.7 |
| SVR | 0.906 | 5.9 | 9.8 |

### Final XGBoost Configuration

```python
XGBRegressor(
    n_estimators=300,
    learning_rate=0.05,
    max_depth=4,
    min_child_weight=10,
    subsample=0.8
)
```

### Urgency Threshold System

| Predicted Days | Label | Action |
|---|---|---|
| ≤ 3 days | 🔴 Critical | Revise immediately |
| 4 – 7 days | 🟠 Soon | Revise this week |
| 8 – 30 days | 🟡 Moderate | Plan a revision |
| > 30 days | 🟢 Good | No rush |

---

## 📁 Project Structure

```
adaptlearn/
│
├── app.py                  # Main Flask app — all routes
├── models.py               # SQLAlchemy ORM models (7 tables)
├── pdf_utils.py            # pdfplumber PDF text extraction
├── summarizer.py           # Groq API summarization
├── quiz_generator.py       # LLM quiz generation + 5-stage JSON parser
├── predictor.py            # XGBoost inference — predict_revision()
├── config.py               # Dev / Prod / Test configuration
├── db_init.py              # Database initialization script
│
├── best_model.pkl          # Trained XGBoost model bundle
│                           # (contains: model + StandardScaler + feature_cols)
│
├── static/
│   ├── style.css           # All styles
│   └── script.js           # Quiz logic, drag-and-drop, SVG animations
│
├── templates/
│   ├── index.html          # PDF upload page
│   ├── quiz.html           # Quiz interface
│   ├── result.html         # Score + SVG ring result
│   ├── my_documents.html   # Document library
│   ├── dashboard.html      # Performance dashboard
│   ├── mastery.html        # Concept mastery tracker
│   ├── analytics.html      # Detailed analytics
│   ├── revisions.html      # Revision schedule
│   ├── login.html          # Login page
│   └── register.html       # Registration page
│
├── uploads/                # Uploaded PDF files (gitignored)
├── requirements.txt        # Python dependencies
└── .env                    # Environment variables (gitignored)
```

---

## ⚙️ Installation

### Prerequisites
- Python 3.11+
- PostgreSQL 15+
- Groq API key — [Get it free at console.groq.com](https://console.groq.com)

### Step 1 — Clone the Repository
```bash
git clone https://github.com/yourusername/adaptlearn.git
cd adaptlearn
```

### Step 2 — Create Virtual Environment
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac / Linux
source venv/bin/activate
```

### Step 3 — Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4 — Set Up Environment Variables

Create a `.env` file in the root folder:

```env
SECRET_KEY=your_secret_key_here
DATABASE_URL=postgresql://username:password@localhost:5432/adaptlearn
GROQ_API_KEY=your_groq_api_key_here
FLASK_ENV=development
```

### Step 5 — Initialize the Database
```bash
python db_init.py
```

### Step 6 — Run the Application
```bash
python app.py
```

Open your browser at **http://localhost:5000** 🚀

---

## 🐛 Bug Fixed

### Quiz Submit Button Not Working — Resolved ✅

**Problem:** The quiz submit button stayed disabled even after answering all 10 questions.

**Root Cause:** In `static/script.js`, the function `initQuizPage()` tried to call `.addEventListener()` on `summaryToggle` — a DOM element that does not exist on the quiz page. This threw an uncaught `TypeError: Cannot read properties of null`, crashing the entire script before the radio button listeners were registered.

**Fix:**

```javascript
// ❌ BEFORE — crashes entire script if element is missing
summaryToggle.addEventListener("click", () => {
    summaryBody.classList.toggle("hidden");
    toggleArrow.classList.toggle("open");
});

// ✅ AFTER — safe null check
if (summaryToggle) {
    summaryToggle.addEventListener("click", () => {
        if (summaryBody) summaryBody.classList.toggle("hidden");
        if (toggleArrow) toggleArrow.classList.toggle("open");
    });
}
```

---

## 🗺 Roadmap

### Short Term
- [ ] Tesseract OCR support for scanned PDFs
- [ ] Email revision reminders via SendGrid
- [ ] Faculty analytics dashboard with class-wide mastery heatmaps
- [ ] Adaptive question difficulty based on per-question success rates

### Long Term
- [ ] LSTM-based Deep Knowledge Tracing model (after real data collection)
- [ ] Gamification — badges, streaks, leaderboards
- [ ] Mobile Progressive Web App with offline quiz caching
- [ ] SCORM / xAPI adapter for Moodle and Canvas LMS integration
- [ ] Multi-modal PDF support (images, tables, diagrams)

---

## 👥 Team

| Name | Roll No |
|---|---|
| Siddhi Dara | C-35 |
| Shreyash Choudhary | C-28 |
| Syed Omar Kazi | C-42 |
| Shagun Gaikwad | C-24 |

**Guide:** Dr. Pranali Dandekar
**Department:** Artificial Intelligence & Cyber Security (AICS)
**Institute:** Shri Ramdeobaba College of Engineering & Management, Nagpur
**Academic Year:** 2025–2026 | VI Semester

---

## 📄 References

1. H. Ebbinghaus, *Memory: A Contribution to Experimental Psychology*, 1885
2. T. Chen and C. Guestrin, "XGBoost: A Scalable Tree Boosting System," ACM SIGKDD, 2016
3. C. Piech et al., "Deep Knowledge Tracing," NeurIPS, 2015
4. G. Kurdi et al., "A Systematic Review of Automatic Question Generation," IJAIED, 2020
5. N. J. Cepeda et al., "Distributed Practice in Verbal Recall Tasks," Psychological Bulletin, 2006

---

## 📜 License

This project was developed as part of the B.Tech (CSE-AIML) curriculum at RCOEM, Nagpur.

---

<div align="center">

Made with ❤️ by Group 03 — AICS Department, RCOEM Nagpur

⚡ **AdaptLearn** — *Study smarter, forget less.*

</div>
