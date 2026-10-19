"""Фабрика Flask-приложения."""

from flask import Flask

from app.config import Config
from app.services.summary_writer import LocalSummaryWriter, PollinationsSummaryWriter
from app.services.vacancy_sources.trudvsem import TrudvsemSource


def create_app(config_class: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.extensions["vacancy_source"] = TrudvsemSource(
        timeout=app.config["VACANCY_API_TIMEOUT"],
        cache_ttl=app.config["VACANCY_CACHE_TTL"],
    )
    if app.config.get("SUMMARY_BACKEND") == "local":
        app.extensions["summary_writer"] = LocalSummaryWriter()
    else:
        app.extensions["summary_writer"] = PollinationsSummaryWriter(
            url=app.config["SUMMARY_API_URL"],
            model=app.config["SUMMARY_MODEL"],
            timeout=app.config["SUMMARY_TIMEOUT"],
            min_interval=app.config["SUMMARY_MIN_INTERVAL"],
        )

    from app.routes import bp

    app.register_blueprint(bp)
    return app
