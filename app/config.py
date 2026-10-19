"""Настройки приложения."""

import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev")
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # ограничение размера запроса (фото) — 5 МБ
    VACANCY_API_TIMEOUT = 30  # секунд; API «Работа России» отвечает за 10–15 с
    VACANCY_CACHE_TTL = 600  # результаты поиска по одной должности кэшируются на 10 минут
    # Бесплатная модель Pollinations, ключ не нужен. Анонимный лимит — один запрос примерно в 30 с.
    SUMMARY_API_URL = "https://text.pollinations.ai/openai"
    SUMMARY_MODEL = "openai-fast"
    SUMMARY_TIMEOUT = 25
    SUMMARY_MIN_INTERVAL = 30


class TestConfig(Config):
    TESTING = True
    SUMMARY_BACKEND = "local"  # тесты не ходят в нейросеть
