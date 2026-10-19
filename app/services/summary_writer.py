"""Текст «О себе» через бесплатную модель Pollinations, с черновиком на случай сбоя."""

import json
import math
import re
import threading
import time
from dataclasses import dataclass

import requests

from app.models import Resume
from app.services.summary import generate_summary, resume_facts

API_URL = "https://text.pollinations.ai/openai"
MODEL = "openai-fast"
CACHE_LIMIT = 40


class RateLimited(Exception):
    """Бесплатный лимит модели: следующий запрос нужно отложить."""

DRAFT_MESSAGE = (
    "Нейросеть отвечает не чаще раза в полминуты. "
    "Пока в поле черновик, готовый текст подставится сам."
)
FAILURE_MESSAGE = "Нейросеть не ответила. В поле черновик по заполненным данным."

_SYSTEM_PROMPT = (
    "Ты помогаешь составить блок «О себе» для резюме на русском языке. "
    "Напиши 3–4 коротких предложения живым языком: кто это за специалист, "
    "какой путь прошёл и на какие навыки опирается. "
    "Каждое предложение должно следовать из переданных фактов. "
    "Не добавляй компании, должности, навыки, цифры и достижения, которых нет во входе. "
    "Не дописывай общие качества, если их нет в фактах: чистый код, ответственность, "
    "коммуникабельность, эффективная архитектура, стремление к развитию. "
    "Не упоминай телефон, почту, сайт и зарплату. "
    "Без списков, заголовков и кавычек вокруг всего ответа. Верни только готовый абзац."
)


@dataclass
class SummaryResult:
    text: str = ""
    source: str = ""  # "model" — ответ нейросети, "draft" — локальный черновик
    message: str = ""
    retry_after: int = 0


class LocalSummaryWriter:
    """Запасной писатель без сети: им пользуются тесты."""

    def write(self, resume: Resume) -> SummaryResult:
        text = generate_summary(resume) or ""
        if not text:
            return SummaryResult()
        return SummaryResult(text=text, source="draft")


class PollinationsSummaryWriter:
    def __init__(
        self,
        url: str = API_URL,
        model: str = MODEL,
        timeout: float = 25,
        min_interval: float = 30,
        post=None,
    ):
        self.url = url
        self.model = model
        self.timeout = timeout
        self.min_interval = min_interval
        self._post = post or _post_json
        self._cache: dict[str, str] = {}
        self._ready_at = 0.0
        self._lock = threading.Lock()

    def write(self, resume: Resume) -> SummaryResult:
        facts = resume_facts(resume)
        if not facts:
            return SummaryResult()
        key = json.dumps(facts, ensure_ascii=False, sort_keys=True)

        with self._lock:
            cached = self._cache.get(key)
            if cached:
                return SummaryResult(text=cached, source="model")
            wait = self._ready_at - time.monotonic()
            if wait > 0:
                return self._draft(resume, retry_after=max(1, math.ceil(wait)))
            self._ready_at = time.monotonic() + self.min_interval

        try:
            text = self._complete(facts)
        except RateLimited:
            return self._draft(resume)
        except (requests.RequestException, ValueError):
            return self._draft(resume, failure=True)
        if not text:
            return self._draft(resume, failure=True)

        with self._lock:
            self._cache.pop(key, None)
            self._cache[key] = text
            while len(self._cache) > CACHE_LIMIT:
                self._cache.pop(next(iter(self._cache)))
        return SummaryResult(text=text, source="model")

    def _complete(self, facts: dict) -> str:
        response = self._post(
            self.url,
            {
                "model": self.model,
                "temperature": 0.4,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": json.dumps(facts, ensure_ascii=False, indent=2),
                    },
                ],
            },
            self.timeout,
        )
        if response.status_code == 402:
            self._postpone(response.headers.get("Retry-After"))
            raise RateLimited
        response.raise_for_status()
        payload = response.json()
        choices = payload.get("choices") or []
        if not choices:
            return ""
        content = (choices[0].get("message") or {}).get("content") or ""
        return _usable_text(content)

    def _postpone(self, retry_after: str | None) -> None:
        try:
            delay = float(retry_after) if retry_after else self.min_interval
        except ValueError:
            delay = self.min_interval
        with self._lock:
            self._ready_at = max(self._ready_at, time.monotonic() + delay)

    def _draft(
        self, resume: Resume, *, failure: bool = False, retry_after: int = 0
    ) -> SummaryResult:
        text = generate_summary(resume) or ""
        if not text:
            return SummaryResult()
        if retry_after <= 0:
            with self._lock:
                retry_after = max(1, math.ceil(self._ready_at - time.monotonic()))
        return SummaryResult(
            text=text,
            source="draft",
            message=FAILURE_MESSAGE if failure else DRAFT_MESSAGE,
            retry_after=retry_after,
        )


def _post_json(url: str, payload: dict, timeout: float):
    return requests.post(url, json=payload, timeout=timeout)


def _usable_text(raw: str) -> str:
    text = (
        raw.strip()
        .replace("\u2011", "-")
        .replace("\u2010", "-")
        .replace("\u202f", " ")
        .replace("\u00a0", " ")
    )
    text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
    text = re.sub(r"\s*```$", "", text).strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        text = text[1:-1].strip()
    text = re.sub(r"\s*\n\s*", " ", text)
    text = re.sub(r" {2,}", " ", text).strip()
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return ""
    cyrillic = sum(1 for char in letters if "А" <= char <= "я" or char in "Ёё")
    if cyrillic / len(letters) < 0.6 or not 15 <= len(text) <= 900:
        return ""
    return text
