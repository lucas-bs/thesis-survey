# access with gpt.config['NAME']

DEBUG = True

import os

#uri = os.getenv("DATABASE_URL")  # or other relevant config var
#if uri.startswith("postgres://"):
#    uri = uri.replace("postgres://", "postgresql://", 1)

SQLALCHEMY_DATABASE_URI = "sqlite:///data.db"

SECRET_KEY = "d32rsdfn121dmkao11q422da1LLLo"


OPENAI_MODEL = "gpt-4o"
