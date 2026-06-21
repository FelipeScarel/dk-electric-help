import os
import sys
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def _parse_database_url():
    """Converte DATABASE_URL para formato SQLAlchemy."""
    url = os.environ.get("DATABASE_URL")
    if url:
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url
    return f"sqlite:///{os.path.join(BASE_DIR, 'dk_electric.db')}"


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dk-electric-help-secret-key-change-in-production"
    SQLALCHEMY_DATABASE_URI = _parse_database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    PDF_OUTPUT_DIR = os.environ.get("PDF_OUTPUT_DIR") or os.path.join(BASE_DIR, "pdf_output")
    BASE_URL = os.environ.get("BASE_URL") or "http://localhost:5000"
    COMPANY_NAME = os.environ.get("COMPANY_NAME") or "DK Electric Help"
    COMPANY_PHONE = os.environ.get("COMPANY_PHONE") or "(19) 99624-5413"
    COMPANY_EMAIL = os.environ.get("COMPANY_EMAIL") or "Dkeletrichelp@gmail.com"
    COMPANY_CNPJ = os.environ.get("COMPANY_CNPJ") or "62.400.020/0001-07"
    PROPOSAL_VALIDITY_DAYS = int(os.environ.get("PROPOSAL_VALIDITY_DAYS", "15"))

    # Sessao
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    # Login do painel administrativo
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL") or "Dkelectrichelp@gmail.com"
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD") or "Deedks123@"

    # WhatsApp via Meta Cloud API (funciona, testado)
    META_WHATSAPP_TOKEN = os.environ.get("META_WHATSAPP_TOKEN") or "EAATJO13J2TgBRp9buxJJW736yqgHplyihPxZBp6y1dgVK2K6UZChzkvGDwiZAOnAp5qRGWoGqCYkZBAHDdjae33lrl93303zWvY3mYk6l6VVhGtb4LP5vnSKYD5ZA3EC3xczmFDGBf7mvEZAiGkpL6QYLVNDnZCZCAJfDbgLZAYM1YIRvmBpBOSRBGhXLiIfHZBM30nmRZB3I7WsFVb4yJhNdKf2y8rLqOkCgtiYdM5Wi1CpoxGzkGBdkFMO7aK3qecUGKg5cpGOqXOkWnM1mCsAU8x"
    META_WHATSAPP_PHONE_ID = os.environ.get("META_WHATSAPP_PHONE_ID") or "1125485747321060"

    # Numero que recebe notificacao de novos agendamentos
    WHATSAPP_NOTIFY = os.environ.get("WHATSAPP_NOTIFY") or "5519996245413"
