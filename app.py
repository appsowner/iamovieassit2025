from flask import Flask, render_template, request, redirect, url_for, flash, session
import os
import pandas as pd
from flask_bootstrap import Bootstrap5
from openai import OpenAI
from dotenv import load_dotenv
from config.db.db import db_config, db
from config.models.models import User, Message, Profile


load_dotenv()

client = OpenAI()
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "default_key")
bootstrap = Bootstrap5(app)
db_config(app)


@app.errorhandler(403)
def forbidden(e):
    return render_template("403.html"), 403


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        session["user_id"] = 1

        # Cargar el perfil del usuario en la sesión
        profile = Profile.query.filter_by(user_id=session["user_id"]).first()
        if email == "demo@iA MovieAssist.com" and password == "demo":
            Profile.query.filter_by(user_id=session["user_id"]).first()
            session["profile"] = {
                "language": profile.language,
                "topics_of_interest": profile.topics_of_interest,
                "report_rentability_12_months": profile.report_rentability_12_months,
                "report_evolution_utility_5_years": profile.report_evolution_utility_5_years,
                "experience_level": profile.experience_level,
                "company_favorite": profile.company_favorite,
                "report_industry_summary": profile.report_industry_summary,
                "indicator_roe": profile.indicator_roe,
                "indicator_roa": profile.indicator_roa,
                "indicator_leverage": profile.indicator_leverage,
                "indicator_sales": profile.indicator_sales,
            }
            print(session)
            return redirect("/chat")
        else:
            error = "Credenciales invalidas. Intenta nuevamente"
    return render_template("index.html", error=error)


@app.route("/chat", methods=["GET", "POST"])
def chat():
    # Obtener el usuario
    user = db.session.query(User).first()

    # Cargar el perfil del usuario en la sesión
    profile = Profile.query.filter_by(user_id=session["user_id"]).first()
    session["profile"] = {
        "language": profile.language,
        "topics_of_interest": profile.topics_of_interest,
        "report_rentability_12_months": profile.report_rentability_12_months,
        "report_evolution_utility_5_years": profile.report_evolution_utility_5_years,
        "report_industry_summary": profile.report_industry_summary,
        "experience_level": profile.experience_level,
        "company_favorite": profile.company_favorite,
        "indicator_roe": profile.indicator_roe,
        "indicator_roa": profile.indicator_roa,
        "indicator_leverage": profile.indicator_leverage,
        "indicator_sales": profile.indicator_sales,
    }

    print(session["profile"])
    intents = {}

    # Crear intents basados en los temas de interés del usuario
    for topic in session["profile"]["topics_of_interest"]:
        intents[f"Quiero saber más sobre {topic}"] = f"Quiero saber más sobre {topic}"

    # Agregar un intent para enviar un mensaje
    intents["Enviar"] = request.form.get("message")

    # Crear el contexto del perfil del usuario para pasarlo al modelo LLM
    if "profile" in session:
        profile_context = (
            f"El usuario tiene un nivel de experiencia '{session['profile']['experience_level']}', "
            f"está interesado en los temas '{', '.join(session['profile']['topics_of_interest'])}', "
            f"y su compañía favorita es '{session['profile']['company_favorite']}'."
        )
    print(profile_context)

    if request.method == "GET":
        # Pasar los intents al template para que se muestren como botones
        return render_template("chat.html", messages=user.messages, intents=intents)

    # Procesar el intent si se envió uno
    intent = request.form.get("intent")

    if intent in intents:
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
            messages=messages_for_llm, model="gpt-4o", temperature=1
        )

        model_recommendation = chat_completion.choices[0].message.content

        # Guardar la respuesta del modelo (asistente) en la base de datos
        db.session.add(
            Message(content=model_recommendation, author="assistant", user=user)
        )
        db.session.commit()

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
            "content": "Eres un chatbot que recomienda películas, te llamas 'Next Moby'. Tu rol es responder recomendaciones de manera breve y concisa. No repitas recomendaciones.",
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
    # Obtener el perfil del usuario (esto depende de tu implementación)
    profile = db.session.query(Profile).first()

    # Leer el archivo Excel y obtener las empresas distintas
    file_path = "data/fecu_cmf.xlsx"
    df = pd.read_excel(file_path)
    companies = df["Razónsocial"].dropna().unique()
    company_list = companies.tolist()
    print(company_list)

    if request.method == "POST":
        # Obtener los valores del formulario
        language = request.form["language"]
        experience_level = request.form["experience_level"]
        company_favorite = request.form["company_favorite"]
        topics_of_interest = request.form["topics_of_interest"].split(",")

        # Obtener valores de reportes financieros
        report_rentability_12_months = "report_rentability_12_months" in request.form
        report_evolution_utility_5_years = (
            "report_evolution_utility_5_years" in request.form
        )
        report_industry_summary = "report_industry_summary" in request.form

        # Obtener valores de indicadores
        indicator_roe = "indicator_roe" in request.form
        indicator_roa = "indicator_roa" in request.form
        indicator_leverage = "indicator_leverage" in request.form
        indicator_sales = "indicator_sales" in request.form

        # Actualizar el perfil del usuario
        profile.language = language
        profile.company_favorite = company_favorite
        profile.experience_level = experience_level
        profile.topics_of_interest = [topic.strip() for topic in topics_of_interest]

        # Actualizar los campos de reportes financieros
        profile.report_rentability_12_months = report_rentability_12_months
        profile.report_evolution_utility_5_years = report_evolution_utility_5_years
        profile.report_industry_summary = report_industry_summary

        # Actualizar los campos de indicadores
        profile.indicator_roe = indicator_roe
        profile.indicator_roa = indicator_roa
        profile.indicator_leverage = indicator_leverage
        profile.indicator_sales = indicator_sales

        # Guardar los cambios en la base de datos
        db.session.commit()

        # Redirigir o mostrar un mensaje de éxito
        flash("Perfil actualizado con éxito", "success")
        return redirect(url_for("editar_perfil"))  # Redirigir a la página de perfil

    return render_template(
        "editar_perfil.html", profile=profile, company_list=company_list
    )
