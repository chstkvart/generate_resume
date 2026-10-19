from datetime import date

from app.models import Education, Experience, Resume
from app.services.summary import generate_summary


def test_summary_sells_path_and_skills():
    resume = Resume(
        title="Python-разработчик",
        location="Москва",
        email="ivan@example.com",
        salary_from=180000,
        skills=["Python", "Flask", "PostgreSQL", "Docker", "Git", "pytest"],
        english_level="B2",
        employment=["Полная занятость", "Удалённо"],
        experience=[
            Experience(
                "ООО Ромашка",
                "Разработчик",
                "2022-01",
                "",
                "- Разработал API заказов",
                current=True,
            ),
            Experience("Студия Веб", "Стажёр", "2020-01", "2021-12", ""),
        ],
        education=[Education("МГУ", "Прикладная математика", "2016", "2020")],
    )

    text = generate_summary(resume, today=date(2024, 1, 1))

    assert text == (
        "Python-разработчик с опытом 4 года. "
        "Сначала Студия Веб как стажёр, теперь ООО Ромашка как разработчик. "
        "Разработал API заказов. "
        "Опираюсь на Python, Flask, PostgreSQL, Docker и Git."
    )
    assert "ivan@example.com" not in text
    assert "180000" not in text
    assert "Москва" not in text
    assert "Удалённо" not in text
    assert "МГУ" not in text


def test_past_job_stays_in_one_sentence():
    resume = Resume(
        experience=[Experience("ООО Ромашка", "Аналитик", "2020-01", "2021-01")],
    )

    text = generate_summary(resume, today=date(2024, 1, 1))

    assert text == "Аналитик с опытом 1 год в ООО Ромашка."


def test_growth_inside_one_company():
    resume = Resume(
        title="Разработчик",
        experience=[
            Experience("ООО Ромашка", "Стажёр", "2020-01", "2021-12"),
            Experience("ООО Ромашка", "Разработчик", "2022-01", "", current=True),
        ],
    )

    text = generate_summary(resume, today=date(2024, 1, 1))

    assert text == (
        "Разработчик с опытом 4 года. "
        "В ООО Ромашка сначала как стажёр, теперь как разработчик."
    )


def test_years_are_rounded_for_reading():
    def phrase(start: str, end: str) -> str:
        return generate_summary(
            Resume(title="Аналитик", experience=[Experience("А", "Б", start, end)]),
            today=date(2030, 1, 1),
        )

    short = phrase("2024-01", "2024-05")
    assert "с опытом меньше года" in short
    assert "месяц" not in short
    assert "с опытом 1 год." in phrase("2023-01", "2023-12")
    assert "с опытом 2 года." in phrase("2022-01", "2023-12")
    assert "с опытом 5 лет." in phrase("2020-01", "2024-12")
    assert "с опытом 11 лет." in phrase("2014-01", "2024-12")
    assert "с опытом 21 год." in phrase("2004-01", "2024-12")
    assert "с опытом больше 4 лет." in phrase("2020-01", "2024-08")
    assert "с опытом больше 1 года." in phrase("2023-01", "2024-08")


def test_skills_without_job_stay_plain():
    text = generate_summary(Resume(skills=["Python", "Flask"]))

    assert text == "Умею работать с Python и Flask."


def test_education_fills_in_when_there_is_no_job():
    text = generate_summary(
        Resume(
            title="Аналитик",
            education=[Education("МГУ", "Прикладная математика", "2016", "2020")],
        )
    )

    assert text == "Аналитик. База — Прикладная математика, МГУ."


def test_empty_profile_is_not_enough():
    resume = Resume(full_name="Иван Петров", email="ivan@example.com", location="Москва")

    assert generate_summary(resume) is None
