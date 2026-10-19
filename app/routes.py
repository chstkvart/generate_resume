"""HTTP-маршруты: форма резюме и генерация PDF."""

import re
from datetime import date
from io import BytesIO

from flask import Blueprint, current_app, jsonify, render_template, request, send_file
from werkzeug.datastructures import MultiDict
from werkzeug.exceptions import RequestEntityTooLarge

from app.choices import EMPLOYMENT_TYPES, ENGLISH_LEVELS
from app.models import Resume
from app.services.form_parser import parse_resume_form
from app.services.job_market import analyze
from app.services.pdf_generator import build_pdf
from app.services.summary import NOT_ENOUGH_DATA

bp = Blueprint("resume", __name__)

EDUCATION_FIRST_YEAR = 1960
EDUCATION_YEARS_AHEAD = 6  # чтобы можно было указать ожидаемый год выпуска


def _pdf_filename(full_name: str) -> str:
    slug = re.sub(r"[^\w\-]+", "_", full_name, flags=re.UNICODE).strip("_")
    return f"Резюме_{slug or 'resume'}.pdf"


@bp.app_context_processor
def inject_choices():
    current_year = date.today().year
    years = range(current_year + EDUCATION_YEARS_AHEAD, EDUCATION_FIRST_YEAR - 1, -1)
    return {
        "education_years": list(years),
        "employment_types": EMPLOYMENT_TYPES,
        "english_levels": ENGLISH_LEVELS,
    }


@bp.get("/")
def index():
    return render_template("index.html", resume=Resume(), errors=[])


@bp.post("/generate")
def generate():
    result = parse_resume_form(request.form, request.files)
    if not result.is_valid:
        return render_template("index.html", resume=result.resume, errors=result.errors), 400

    pdf = build_pdf(result.resume)
    return send_file(
        BytesIO(pdf),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=_pdf_filename(result.resume.full_name),
    )


@bp.post("/api/summary")
def summary_text():
    """Текст «О себе» по текущему состоянию формы."""
    result = parse_resume_form(request.form, MultiDict())
    written = current_app.extensions["summary_writer"].write(result.resume)
    if not written.text:
        return jsonify(summary="", message=NOT_ENOUGH_DATA, source="", retry_after=0)
    return jsonify(
        summary=written.text,
        message=written.message,
        source=written.source,
        retry_after=written.retry_after,
    )


@bp.post("/api/market")
def market():
    """Анализ рынка по текущему состоянию формы: подходящие вакансии и оценка зарплаты."""
    result = parse_resume_form(request.form, MultiDict())
    report = analyze(result.resume, current_app.extensions["vacancy_source"])
    return jsonify(report.to_dict())


@bp.app_errorhandler(RequestEntityTooLarge)
def too_large(_error):
    errors = ["Файл слишком большой. Максимальный размер — 5 МБ."]
    return render_template("index.html", resume=Resume(), errors=errors), 413
