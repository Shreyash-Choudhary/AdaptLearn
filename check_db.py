from app import app
from models import User, Document, Attempt, Concept

with app.app_context():
    print("---- USERS ----")
    users = User.query.all()
    for u in users:
        print(u.id, u.username, u.email)

    print("\n---- DOCUMENTS ----")
    docs = Document.query.all()
    for d in docs:
        print(d.id, d.title)

    print("\n---- ATTEMPTS ----")
    attempts = Attempt.query.all()
    for a in attempts:
        print(a.user_id, a.question_id, a.is_correct)

    print("\n---- CONCEPTS ----")
    concepts = Concept.query.all()
    for c in concepts:
        print(c.id, c.title)