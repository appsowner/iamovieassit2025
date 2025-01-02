from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
import os

load_dotenv()


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)


def db_config(app):
    DB_USER = os.environ.get("DB_USER")
    DB_PASSWORD = os.environ.get("DB_PASSWORD")
    DB_HOST = os.environ.get("DB_HOST")
    DB_PORT = os.environ.get("DB_PORT")
    DB_NAME = os.environ.get("DB_NAME")

    print(f"{DB_USER}-{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
    db_url = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?client_encoding=utf8"
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    db.init_app(app)
