from . import db
from sqlalchemy import func


class Users(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.String(10), primary_key=True)
    treatment_gpt = db.Column(db.Integer, nullable=False)
    finished = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    finished_at = db.Column(db.DateTime(timezone=True))

    chats = db.relationship('Chat', backref='user')


class Chat(db.Model):
    """Table matching users with conversations and pages"""
    __tablename__ = 'chats'
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    user_id = db.Column(db.String(10), db.ForeignKey('users.id'), nullable=False)
    task_number = db.Column(db.Integer)
    system_message = db.Column(db.Text)
    conversations = db.relationship('Conversation', backref='chat')


class Conversation(db.Model):
    """Table recording Chat messages sent and received"""
    __tablename__ = 'conversations'
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.Text)
    role = db.Column(db.String)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    chat_id = db.Column(db.Integer, db.ForeignKey('chats.id'), nullable=False)


class SurveyResponse(db.Model):
    __tablename__ = 'survey_responses'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(10), db.ForeignKey('users.id'), nullable=False)
    scale = db.Column(db.Text, nullable=False)
    task_number = db.Column(db.Integer, nullable=False)
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())

    user = db.relationship('Users', backref='survey_responses')


class BretResponses(db.Model):
    __tablename__ = 'bret_response'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(10), db.ForeignKey('users.id'), nullable=False)
    task_number = db.Column(db.Integer, nullable=False)
    is_trial = db.Column(db.Boolean, nullable=False)
    n_cards = db.Column(db.Integer, nullable=False)
    final_pay = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())

    user = db.relationship('Users', backref='bret_response')


class Demographics(db.Model):
    __tablename__ = 'demographics'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(10), db.ForeignKey('users.id'), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    gender = db.Column(db.String(50), nullable=False)
    education = db.Column(db.String(100), nullable=False)
    country = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())

    user = db.relationship('Users', backref='demographics')


class CompetitionEntry(db.Model):
    __tablename__ = 'competition_entries'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    amount_collected = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=func.now(), nullable=False)
