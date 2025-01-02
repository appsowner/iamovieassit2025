from app import app
from config.db.db import db
from config.models.models import User, Message, Profile
from datetime import datetime


with app.app_context():

    db.create_all()

    user = User(email="carl.sanchez@guc.cl", is_active=True, is_admin=True, rol="Admin")

    # Crear perfil asociado
    profile = Profile(
        user=user,
        favorite_movie_genres=["terror", "ciencia ficcion", "comedia"],
    )
    db.session.add(profile)

    message = Message(
        content="Hola! Soy iA MovieAssist, IA que te ayuda a encontrar y recomendar las mejores peliculas. ¿En qué te puedo ayudar?",
        author="assistant",
        user=user,
    )

    db.session.add(user)
    db.session.add(message)
    db.session.add(profile)
    db.session.commit()
