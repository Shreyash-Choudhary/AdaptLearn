"""
db_init.py - Database initialization script
Run this once to create all tables in the database
"""
import os
from app import app, db
from models import User, Document, Concept, Question, Attempt, ConceptMastery, RevisionSchedule

def init_db():
    """Create all database tables"""
    with app.app_context():
        print("[INFO] Creating database tables...")
        db.create_all()
        print("[SUCCESS] Database tables created successfully!")
        print("[INFO] Tables created:")
        print("  - users")
        print("  - documents")
        print("  - concepts")
        print("  - questions")
        print("  - attempts")
        print("  - concept_mastery")
        print("  - revision_schedules")


def drop_db():
    """Drop all database tables (WARNING: This deletes all data)"""
    with app.app_context():
        confirm = input("[WARNING] This will DELETE all tables and data. Type 'yes' to confirm: ")
        if confirm.lower() == "yes":
            print("[INFO] Dropping all tables...")
            db.drop_all()
            print("[SUCCESS] All tables dropped!")
        else:
            print("[CANCELLED] Operation cancelled.")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "drop":
        drop_db()
    else:
        init_db()
