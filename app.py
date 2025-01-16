from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    jsonify,
)
import os
import pandas as pd
from flask_bootstrap import Bootstrap5
from openai import OpenAI
from dotenv import load_dotenv
from config.db.db import db_config, db
from config.models.models import User, Message, Profile
import json

from forms import ProfileForm, SignUpForm, LoginForm
from flask_wtf.csrf import CSRFProtect
from bot import search_movie_or_tv_show, where_to_watch
from flask_login import (
    LoginManager,
    login_required,
    login_user,
    current_user,
    logout_user,
)
from flask_bcrypt import Bcrypt
from flask import redirect, url_for
from langsmith.wrappers import wrap_openai


load_dotenv()


login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.login_message = "Inicia sesión para continuar"
client = wrap_openai(OpenAI())
client = OpenAI()
app = Flask(__name__)
csrf = CSRFProtect(app)
login_manager.init_app(app)
bcrypt = Bcrypt(app)

app.secret_key = os.environ.get("FLASK_SECRET_KEY", "default_key")
bootstrap = Bootstrap5(app)
db_config(app)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


tools = [
    {
        "type": "function",
        "function": {
            "name": "where_to_watch",
            "description": "Returns a list of platforms where a specified movie can be watched.",
            "parameters": {
                "type": "object",
                "required": ["name"],
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The name of the movie to search for",
                    }
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_movie_or_tv_show",
            "description": "Returns information about a specified movie or TV show.",
            "parameters": {
                "type": "object",
                "required": ["name"],
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The name of the movie/tv show to search for",
                    }
                },
                "additionalProperties": False,
            },
        },
    },
]


@app.errorhandler(403)
def forbidden(e):
    return render_template("403.html"), 403


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()

    if request.method == "POST":
        if form.validate_on_submit():
            email = form.email.data
            password = form.password.data
            user = db.session.query(User).filter_by(email=email).first()
            if user and bcrypt.check_password_hash(user.password_hash, password):
                login_user(user)
                return redirect("chat")

            flash("El correo o la contraseña es incorrecta.", "error")

    return render_template("index.html", form=form)


@app.route("/chat", methods=["GET", "POST"])
@login_required
def chat():
    # Obtener el usuario
    user = db.session.query(User).get(current_user.id)

    # Cargar el perfil del usuario en la sesión
    profile = Profile.query.filter_by(user_id=user.id).first()
    session["profile"] = {"favorite_movie_genres": profile.favorite_movie_genres}
    intents = {}

    # Crear intents basados en los temas de interés del usuario
    for topic in session["profile"]["favorite_movie_genres"]:
        intents[f"Quiero saber más sobre {topic}"] = f"Quiero saber más sobre {topic}"

    # Preparar el contexto para el modelo si hay géneros
    if intents:
        genres_text = ", ".join(session["profile"]["favorite_movie_genres"])
        profile_context = f"Recomendar películas de los siguientes géneros o tambien llamado perfil del usuario: {genres_text}."
    else:
        profile_context = "Recomendaciones de películas."

    # Agregar un intent para enviar un mensaje
    intents["Enviar"] = request.form.get("message")

    if request.method == "GET":
        # Pasar los intents al template para que se muestren como botones
        return render_template("chat.html", messages=user.messages, intents=intents)

    # Procesar el intent si se envió uno
    intent = request.form.get("intent")

    if intent and intent in intents:
        user_message = intents[intent]

        # Guardar nuevo mensaje en la base de datos
        db.session.add(Message(content=user_message, author="user", user=user))
        db.session.commit()
        # Preparar los mensajes para el LLM (modelo de lenguaje)
    messages_for_llm = [
        {
            "role": "system",
            "content": profile_context,
        }
    ]

    # Añadir los mensajes del chat
    for message in user.messages:
        messages_for_llm.append(
            {
                "role": message.author,
                "content": message.content,
            }
        )

    # Llamar al modelo para generar una recomendación
    chat_completion = client.chat.completions.create(
        messages=messages_for_llm,
        model="gpt-4o",
        temperature=1,
        tools=tools,
    )
    if chat_completion.choices[0].message.tool_calls:
        tool_call = chat_completion.choices[0].message.tool_calls[0]

        if tool_call.function.name == "where_to_watch":
            arguments = json.loads(tool_call.function.arguments)
            name = arguments["name"]
            model_recommendation = where_to_watch(client, name, user)
        elif tool_call.function.name == "search_movie_or_tv_show":
            arguments = json.loads(tool_call.function.arguments)
            name = arguments["name"]
            model_recommendation = search_movie_or_tv_show(client, name, user)
    else:
        model_recommendation = chat_completion.choices[0].message.content

        # model_recommendation = chat_completion.choices[0].message.content

        # Guardar la respuesta del modelo (asistente) en la base de datos
    db.session.add(Message(content=model_recommendation, author="assistant", user=user))
    db.session.commit()
    accept_header = request.headers.get("Accept")
    if accept_header and "application/json" in accept_header:
        last_message = user.messages[-1]
        return jsonify(
            {
                "author": last_message.author,
                "content": last_message.content,
            }
        )

    # Renderizar la plantilla con los nuevos mensajes
    return render_template("chat.html", messages=user.messages, intents=intents)


@app.post("/recommend")
def recommend():
    user = db.session.query(User).first()
    data = request.get_json()
    user_message = data["message"]
    new_message = Message(content=user_message, author="user", user=user)
    db.session.add(new_message)
    db.session.commit()

    messages_for_llm = [
        {
            "role": "system",
            "content": """
            Eres un chatbot que recomienda películas, te llamas iA FilamDORA. 
            Tu rol es responder recomendaciones de manera breve y concisa. No repitas recomendaciones.
            ademas debes considerar las preferencias del perfil del usuarios que tambien se pueden llamar generos de peliculas
            """,
        }
    ]

    for message in user.messages:
        messages_for_llm.append(
            {
                "role": message.author,
                "content": message.content,
            }
        )

    chat_completion = client.chat.completions.create(
        messages=messages_for_llm,
        model="gpt-4o",
    )

    message = chat_completion.choices[0].message.content

    return {
        "recommendation": message,
        "tokens": chat_completion.usage.total_tokens,
    }


@app.route("/editar-perfil", methods=["GET", "POST"])
def editar_perfil():
    user = db.session.query(User).get(current_user.id)
    # Cargar el perfil del usuario en la sesión
    profile = Profile.query.filter_by(user_id=user.id).first()

    if request.method == "POST":
        # Obtener los valores del formulario
        selected_genres = request.form.getlist("favorite_movie_genres")

        # Actualizar el perfil del usuario con los géneros seleccionados
        profile.favorite_movie_genres = selected_genres
        # Guardar los cambios en la base de datos
        db.session.commit()

        # Redirigir o mostrar un mensaje de éxito
        flash("Perfil actualizado con éxito", "success")
        return redirect(url_for("editar_perfil"))  # Redirigir a la página de perfil

    return render_template("editar_perfil.html", profile=profile)


@app.route("/sign-up", methods=["GET", "POST"])
def sign_up():
    form = SignUpForm()
    if request.method == "POST":
        if form.validate_on_submit():
            email = form.email.data
            password = form.password.data
            user = User(
                email=email,
                password_hash=bcrypt.generate_password_hash(password).decode("utf-8"),
            )
            db.session.add(user)
            profile = Profile(
                user=user,
                favorite_movie_genres=["terror", "ciencia ficcion", "comedia"],
            )
            message = Message(
                content="Hola! Soy iA FilamDORA, IA que te ayuda a encontrar y recomendar las mejores peliculas. ¿En qué te puedo ayudar?",
                author="assistant",
                user=user,
            )
            db.session.add(profile)
            db.session.add(message)
            db.session.commit()
            login_user(user)
            return redirect(url_for("chat"))
    return render_template("sign-up.html", form=form)


@app.get("/logout")
def logout():
    logout_user()
    return redirect("/")
