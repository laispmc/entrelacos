"""Instâncias das extensões, criadas sem app e ligadas em create_app()."""
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from sqlalchemy import MetaData

# Convenção de nomes para as constraints (facilita leitura do schema)
convencao = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

db = SQLAlchemy(metadata=MetaData(naming_convention=convencao))
csrf = CSRFProtect()
login_manager = LoginManager()
login_manager.login_view = "admin.login"
login_manager.login_message = "Faça login para acessar a área administrativa."
login_manager.login_message_category = "warning"
