from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(100), nullable=False)
    email      = db.Column(db.String(150), unique=True, nullable=False)
    password   = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    results    = db.relationship('Result', backref='user', lazy=True)

class Result(db.Model):
    __tablename__ = 'results'
    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    filename     = db.Column(db.String(256))
    doc_type     = db.Column(db.String(80))
    extracted    = db.Column(db.Text)
    summary      = db.Column(db.Text)
    translation  = db.Column(db.Text)
    translate_to = db.Column(db.String(50))
    word_count   = db.Column(db.Integer)
    char_count   = db.Column(db.Integer)
    tokens_used  = db.Column(db.Integer)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
