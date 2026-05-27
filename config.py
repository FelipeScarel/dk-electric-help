import os
import sys
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def _parse_database_url():
    """Converte DATABASE_URL do Render (postgres://) para formato SQLAlchemy."""
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
    COMPANY_PHONE = os.environ.get("COMPANY_PHONE") or "(11) 99999-9999"
    COMPANY_EMAIL = os.environ.get("COMPANY_EMAIL") or "contato@dkelectric.com.br"
    PROPOSAL_VALIDITY_DAYS = int(os.environ.get("PROPOSAL_VALIDITY_DAYS", "15"))
