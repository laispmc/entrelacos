"""Ponto de entrada. A Vercel procura a variável `app` neste arquivo.

Localmente: flask --app main run
"""
from app import create_app

app = create_app()
