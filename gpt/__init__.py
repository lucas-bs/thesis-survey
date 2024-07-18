from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO

app = Flask(__name__)

app.config.from_object('config')

uri = os.getenv('DATABASE_URL')
if uri.startswith('postgres://'):
    uri = uri.replace('postgres://', 'postgresql://', 1)

db = SQLAlchemy(app)

socketio = SocketIO(app)

from .models import *
import gpt.views
