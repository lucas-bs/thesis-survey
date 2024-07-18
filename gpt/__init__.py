from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
import os

app = Flask(__name__)

app.config.from_object('config')


db = SQLAlchemy(app)

socketio = SocketIO(app)

from .models import *
import gpt.views
