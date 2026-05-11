# Database Queries - AI Adaptive Learning System

This document contains all SQL queries for viewing, analyzing, and managing the PostgreSQL database.

---

## 🔐 IMPORTANT: Authentication System Active

**Status:** User authentication is now fully enabled. 
- Users must register/login before accessing the platform
- Each user's quiz attempts are tracked individually
- Faculty and student roles are supported

### Verify Authentication:
Run Query 2.7 to see all registered users
Run Query 2.8 to see per-user statistics

---

## 🎯 NEW: My Documents Feature

**Status:** Users can now view all their uploaded PDFs and take quizzes multiple times.
- Each user has a personal "My Documents" page at `/my-documents`
- Upload a PDF once, generate infinite quiz variations
- Each quiz generation creates new random questions from the same summary
- Track quiz history and attempt counts per document

**User Journey:**
1. Upload PDF → Auto-generates first quiz
2. Go to "My Documents" → See all uploads with stats
3. Click "Take Quiz" → Fresh questions generated from same PDF
4. Multiple attempts tracked with `attempt_number` incrementing

**Database Impact:**
- Documents stored with `uploader_id` linking to user
- Questions can be regenerated per document
- Attempts properly linked to user_id + question_id for ML training

---

## Quick Start

### Connect to Database in pgAdmin
1. Open pgAdmin (http://localhost:5050)
2. Open Query Tool
3. Copy and paste any query below
4. Click Execute (or press F5)

---

## 1. View All Data

### 1.1 All Users
```sql
SELECT * FROM users;
```
**Shows:** User accounts (students/faculty), email, role, creation date

---

### 1.2 All Documents (Uploaded PDFs)
```sql
SELECT id, title, filename, file_size, created_at FROM documents;
```
**Shows:** All uploaded PDFs, their filenames, sizes, upload dates

---

### 1.3 All Concepts (Text Chunks)
```sql
SELECT id, document_id, title, chunk_index, difficulty_level FROM concepts;
```
**Shows:** Text chunks extracted from PDFs, linked to documents

---

### 1.4 All Questions (Quiz Questions)
```sql
SELECT id, concept_id, question_text, question_type, correct_answer FROM questions;
```
**Shows:** Auto-generated quiz questions, linked to concepts

---

### 1.5 All Attempts (Quiz Answer History) ⭐ MOST IMPORTANT
```sql
SELECT id, user_id, question_id, is_correct, response_time_seconds, days_since_last_attempt, attempted_at 
FROM attempts 
ORDER BY attempted_at DESC;
```
**Shows:** Every quiz attempt, whether correct, time taken, days since last review

**Used for:** Training ML forgetting prediction model

---

### 1.6 All Concept Mastery Scores
```sql
SELECT user_id, concept_id, mastery_score, total_attempts, correct_attempts, last_attempted_at 
FROM concept_mastery;
```
**Shows:** Per-student understanding of each concept (0-1 score)

---

### 1.7 All Revision Schedules (Predicted Next Review Dates)
```sql
SELECT user_id, concept_id, next_revision_date, forgetting_probability, interval_days 
FROM revision_schedules;
```
**Shows:** When student should next review each concept (populated by ML model)

---

## 2. Analysis Queries

### 2.1 Student Performance Summary
```sql
SELECT 
  u.username,
  COUNT(DISTINCT a.id) as total_attempts,
  ROUND(100.0 * SUM(CASE WHEN a.is_correct THEN 1 ELSE 0 END) / COUNT(a.id), 2) as accuracy_percent,
  ROUND(AVG(a.response_time_seconds), 2) as avg_response_time_seconds,
  MAX(a.attempted_at) as last_attempt_at
FROM users u
LEFT JOIN attempts a ON u.id = a.user_id
GROUP BY u.id, u.username
ORDER BY total_attempts DESC;
```
**Shows:** Overall performance of each student

---

### 2.2 Concept Difficulty (Based on Student Performance)
```sql
SELECT 
  c.id,
  c.title,
  COUNT(a.id) as total_attempts,
  ROUND(100.0 * SUM(CASE WHEN a.is_correct THEN 1 ELSE 0 END) / COUNT(a.id), 2) as success_rate_percent,
  ROUND(AVG(c.difficulty_level), 2) as difficulty_level
FROM concepts c
LEFT JOIN questions q ON c.id = q.concept_id
LEFT JOIN attempts a ON q.id = a.question_id
GROUP BY c.id, c.title
ORDER BY success_rate_percent ASC;
```
**Shows:** Which concepts are hardest (lowest success rate)

---

### 2.3 Student Mastery by Concept (Heatmap Data)
```sql
SELECT 
  u.username,
  c.title,
  cm.mastery_score,
  cm.total_attempts,
  cm.last_attempted_at
FROM concept_mastery cm
JOIN users u ON cm.user_id = u.id
JOIN concepts c ON cm.concept_id = c.id
ORDER BY u.username, c.title;
```
**Shows:** Student-Concept mastery matrix (for dashboard heatmap)

---

### 2.4 Study Patterns - Time Between Reviews
```sql
SELECT 
  user_id,
  question_id,
  ROUND(AVG(COALESCE(days_since_last_attempt, 0)), 2) as avg_days_between_attempts,
  COUNT(*) as total_attempts,
  MAX(attempted_at) as last_attempted
FROM attempts
WHERE days_since_last_attempt IS NOT NULL
GROUP BY user_id, question_id
ORDER BY avg_days_between_attempts DESC;
```
**Shows:** How long students wait between reviewing concepts

---

### 2.5 Questions by Difficulty
```sql
SELECT 
  id,
  question_text,
  difficulty_score,
  COUNT(DISTINCT a.id) as times_attempted,
  ROUND(100.0 * SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) / COUNT(a.id), 2) as success_rate
FROM questions q
LEFT JOIN attempts a ON q.id = a.question_id
GROUP BY q.id, q.question_text, q.difficulty_score
ORDER BY success_rate ASC;
```
**Shows:** Hardest and easiest questions

---

### 2.6 Documents with Stats
```sql
SELECT 
  d.id,
  d.title,
  d.file_size,
  d.created_at,
  COUNT(DISTINCT c.id) as concept_count,
  COUNT(DISTINCT q.id) as question_count,
  COUNT(DISTINCT a.id) as total_attempts
FROM documents d
LEFT JOIN concepts c ON d.id = c.document_id
LEFT JOIN questions q ON c.id = q.concept_id
LEFT JOIN attempts a ON q.id = a.question_id
GROUP BY d.id, d.title, d.file_size, d.created_at
ORDER BY d.created_at DESC;
```
**Shows:** Each PDF with number of concepts, questions, and student attempts

---

### 2.7 User Registration & Authentication Status
```sql
SELECT 
  id,
  username,
  email,
  full_name,
  role,
  created_at,
  updated_at
FROM users
ORDER BY created_at DESC;
```
**Shows:** All registered users with their authentication details

---

### 2.8 Per-User Quiz Statistics
```sql
SELECT 
  u.id,
  u.username,
  u.email,
  COUNT(DISTINCT d.id) as total_documents_uploaded,
  COUNT(DISTINCT a.id) as total_quiz_attempts,
  ROUND(100.0 * SUM(CASE WHEN a.is_correct THEN 1 ELSE 0 END) / NULLIF(COUNT(a.id), 0), 2) as overall_accuracy_percent,
  COUNT(DISTINCT cm.concept_id) as concepts_attempted,
  ROUND(AVG(cm.mastery_score), 3) as avg_mastery_score,
  MAX(a.attempted_at) as last_quiz_attempt
FROM users u
LEFT JOIN documents d ON u.id = d.uploader_id
LEFT JOIN concepts c ON d.id = c.document_id
LEFT JOIN questions q ON c.id = q.concept_id
LEFT JOIN attempts a ON u.id = a.user_id AND q.id = a.question_id
LEFT JOIN concept_mastery cm ON u.id = cm.user_id
GROUP BY u.id, u.username, u.email
ORDER BY total_quiz_attempts DESC;
```
**Shows:** Complete statistics for each logged-in user (NEW - requires authentication)

---

### 2.9 Faculty vs Student Breakdown
```sql
SELECT 
  role,
  COUNT(*) as user_count,
  COUNT(DISTINCT CASE WHEN role = 'student' THEN id END) as total_students
FROM users
GROUP BY role;
```
**Shows:** Number of faculty and student accounts in the system

---

### 2.10 My Documents - User's Upload Stats (for /my-documents page)
```sql
SELECT 
  d.id,
  d.title,
  d.filename,
  d.file_size,
  d.created_at,
  d.summary,
  COUNT(DISTINCT c.id) as concept_count,
  COUNT(DISTINCT q.id) as question_count,
  COUNT(DISTINCT a.id) as total_attempts,
  COUNT(CASE WHEN a.is_correct THEN 1 END) as correct_attempts,
  ROUND(100.0 * COUNT(CASE WHEN a.is_correct THEN 1 END) / NULLIF(COUNT(a.id), 0), 2) as accuracy_percent,
  MAX(a.attempted_at) as last_attempt_at
FROM documents d
LEFT JOIN concepts c ON d.id = c.document_id
LEFT JOIN questions q ON c.id = q.concept_id
LEFT JOIN attempts a ON q.id = a.question_id AND a.user_id = d.uploader_id
WHERE d.uploader_id = %(user_id)s
GROUP BY d.id, d.title, d.filename, d.file_size, d.created_at, d.summary
ORDER BY d.created_at DESC;
```
**Shows:** All documents for a specific user with stats (concepts, questions, attempts) - used by /my-documents page
**Parameters:** Replace `%(user_id)s` with the logged-in user's ID

---

## 3. Data Quality Checks
```sql
-- Questions without concepts
SELECT * FROM questions WHERE concept_id IS NULL;

-- Attempts without linked question
SELECT * FROM attempts WHERE question_id NOT IN (SELECT id FROM questions);

-- Orphaned concepts (concepts with no questions)
SELECT c.* FROM concepts c 
LEFT JOIN questions q ON c.id = q.concept_id 
WHERE q.id IS NULL;
```
**Shows:** Data integrity issues

---

### 3.2 Extract PDF Text for Review
```sql
SELECT id, title, 
  SUBSTRING(extracted_text FROM 1 FOR 500) as text_preview,
  LENGTH(extracted_text) as text_length
FROM documents;
```
**Shows:** Preview of extracted text from PDFs

---

### 3.3 Extract PDF Summary
```sql
SELECT id, title, 
  SUBSTRING(summary FROM 1 FOR 1000) as summary_preview,
  LENGTH(summary) as summary_length
FROM documents;
```
**Shows:** Summary/abstract of each PDF

---

## 4. ML Training Data Export

### 4.1 Export for Forgetting Curve Model
```sql
SELECT 
  a.id as attempt_id,
  a.user_id,
  a.question_id,
  q.concept_id,
  c.difficulty_level,
  a.is_correct,
  a.response_time_seconds,
  a.days_since_last_attempt,
  a.attempt_number,
  m.mastery_score,
  a.attempted_at
FROM attempts a
JOIN questions q ON a.question_id = q.id
JOIN concepts c ON q.concept_id = c.id
LEFT JOIN concept_mastery m ON a.user_id = m.user_id AND c.id = m.concept_id
ORDER BY a.attempted_at;
```
**Shows:** All data needed to train the ML forgetting prediction model

---

## 5. Updates & Maintenance

### 5.1 Update Question Difficulty Based on Performance
```sql
UPDATE questions q
SET difficulty_score = (
  SELECT 1.0 - COALESCE(ROUND(100.0 * SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) / 100, 0.5)
  FROM attempts a
  WHERE a.question_id = q.id
)
WHERE id IN (SELECT question_id FROM attempts GROUP BY question_id);
```
**Does:** Auto-update question difficulty based on student success rate

---

### 5.2 Update Concept Difficulty
```sql
UPDATE concepts c
SET difficulty_level = (
  SELECT 1.0 - COALESCE(ROUND(100.0 * SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) / 100, 0.5)
  FROM questions q
  JOIN attempts a ON q.id = a.question_id
  WHERE q.concept_id = c.id
)
WHERE id IN (SELECT DISTINCT concept_id FROM questions);
```
**Does:** Auto-update concept difficulty based on student success rate

---

## 6. Data Deletion (Use with Caution!)

### 6.1 Delete All Attempts (Keep structure)
```sql
DELETE FROM attempts WHERE 1=1;
```
**Warning:** This deletes ALL quiz attempt history!

---

### 6.2 Clear All Data for Fresh Start
```sql
DELETE FROM concept_mastery;
DELETE FROM revision_schedules;
DELETE FROM attempts;
DELETE FROM questions;
DELETE FROM concepts;
DELETE FROM documents;
DELETE FROM users;
```
**Warning:** This completely clears the database!

---

## 7. Database Info

### 7.1 Table Sizes
```sql
SELECT 
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```
**Shows:** How much disk space each table uses

---

### 7.2 Column Info
```sql
SELECT 
  table_name,
  column_name,
  data_type,
  is_nullable
FROM information_schema.columns
WHERE table_schema = 'public'
ORDER BY table_name, ordinal_position;
```
**Shows:** All columns in all tables with their data types

---

## 8. Setting up pgAdmin Connection Locally

**Database:** `adaptive_learning`
**User:** `postgres`
**Host:** `localhost`
**Port:** `5432`
**Password:** (your PostgreSQL password)

---

## Notes

- ⭐ **Most Important Table:** `attempts` - Contains all learning behavior data
- ⭐ **Authentication:** `users` table - Registered student/faculty accounts
- ⭐ **My Documents:** `documents` table - User-uploaded PDFs with regenerable quizzes
- **For Authentication:** Use Query 2.7 (View Users) and Query 2.8 (Per-User Stats)
- **For My Documents Page:** Use Query 2.10 (User's Documents & Stats)
- **For ML Training:** Use Query 4.1 (Export for Forgetting Curve Model)
- **For Analytics:** Use Section 2 (Analysis Queries)
- **For Dashboards:** Use Query 2.3 (Mastery Heatmap), 2.8 (User Stats), or 2.10 (Documents)

---

## Recent Updates

**April 1, 2026 - My Documents Feature**
- Added `/my-documents` route to display user's uploaded PDFs with stats
- Added `/quiz-from-document/<id>` route to regenerate fresh quizzes
- New Query 2.10 for My Documents page statistics
- Users can now retake quizzes with new question variations
- `attempt_number` now properly increments across multiple quiz attempts
- Navigation added to all pages linking to My Documents

**April 1, 2026 - Authentication System**
- User registration & login system (Flask-Login)
- Password hashing with werkzeug.security
- Per-student data isolation
- New queries for user management (2.7, 2.8, 2.9)
- Ready for per-student ML model training

---

## Contact / Questions

If adding new tables or fields, update this file and the DATABASE_SETUP.md documentation.
