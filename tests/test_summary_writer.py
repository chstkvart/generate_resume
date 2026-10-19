import json

import requests

from app.models import Resume
from app.services.summary import resume_facts
from app.services.summary_writer import PollinationsSummaryWriter


class Response:
    def __init__(self, payload, status=200, headers=None):
        self.status_code = status
        self._payload = payload
        self.headers = headers or {}

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            error = requests.HTTPError(response=self)
            raise error


def model_text():
    return "Python-разработчик с опытом в API и базах данных. Опираюсь на Python и Flask."


def ok(text=None):
    return Response({"choices": [{"message": {"content": text or model_text()}}]})


def test_model_answer_is_returned_and_cached():
    calls = []

    def post(url, payload, timeout):
        calls.append(payload)
        return ok()

    writer = PollinationsSummaryWriter(post=post, min_interval=30)
    resume = Resume(title="Python-разработчик", skills=["Python", "Flask"], email="a@b.c")

    first = writer.write(resume)
    second = writer.write(resume)

    assert first.source == "model"
    assert first.text == model_text()
    assert second.source == "model"
    assert second.text == first.text
    assert len(calls) == 1
    sent = json.dumps(calls[0], ensure_ascii=False)
    assert "a@b.c" not in sent
    assert "Python" in sent


def test_interval_returns_draft_without_second_request():
    calls = []

    def post(url, payload, timeout):
        calls.append(1)
        return ok()

    writer = PollinationsSummaryWriter(post=post, min_interval=30)
    writer.write(Resume(title="Аналитик", skills=["SQL"]))
    second = writer.write(Resume(title="Дизайнер", skills=["Figma"]))

    assert len(calls) == 1
    assert second.source == "draft"
    assert second.retry_after > 0
    assert "Дизайнер" in second.text
    assert "Figma" in second.text


def test_rate_limit_returns_draft():
    def post(url, payload, timeout):
        return Response({"error": "busy"}, status=402, headers={"Retry-After": "12"})

    writer = PollinationsSummaryWriter(post=post, min_interval=30)
    result = writer.write(Resume(title="Аналитик", skills=["SQL"]))

    assert result.source == "draft"
    assert "Аналитик" in result.text
    assert result.retry_after > 0


def test_network_error_falls_back_to_draft():
    def post(url, payload, timeout):
        raise requests.ConnectionError("down")

    writer = PollinationsSummaryWriter(post=post, min_interval=30)
    result = writer.write(Resume(title="Аналитик", skills=["SQL"]))

    assert result.source == "draft"
    assert "Аналитик" in result.text
    assert result.retry_after > 0


def test_foreign_language_answer_is_rejected():
    def post(url, payload, timeout):
        return ok("This is an English explanation of the prompt and not a resume.")

    writer = PollinationsSummaryWriter(post=post, min_interval=30)
    result = writer.write(Resume(title="Аналитик", skills=["SQL"]))

    assert result.source == "draft"
    assert "Аналитик" in result.text


def test_facts_skip_contacts_and_salary():
    facts = resume_facts(
        Resume(
            title="Аналитик",
            email="a@b.c",
            phone="+7999",
            website="example.com",
            salary_from=180000,
            skills=["SQL"],
        )
    )

    blob = json.dumps(facts, ensure_ascii=False)
    assert facts["должность"] == "Аналитик"
    assert "a@b.c" not in blob
    assert "+7999" not in blob
    assert "example.com" not in blob
    assert "180000" not in blob
