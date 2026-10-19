from io import BytesIO


def test_index_page(client):
    response = client.get("/")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Генератор резюме" in page
    assert '<select name="education_start">' in page


def test_selected_education_year_is_kept_on_error(client):
    response = client.post(
        "/generate",
        data={"education_institution": "МГУ", "education_start": "2016", "education_end": "2020"},
    )

    assert response.status_code == 400
    assert '<option value="2016" selected>' in response.get_data(as_text=True)


def test_generate_returns_pdf(client, photo_bytes):
    response = client.post(
        "/generate",
        data={
            "full_name": "Иван Петров",
            "title": "Python-разработчик",
            "experience_company": "ООО Ромашка",
            "experience_position": "Разработчик",
            "experience_start": "2020-01",
            "experience_end": "2023-05",
            "experience_current": "0",
            "experience_description": "- Писал код",
            "photo": (BytesIO(photo_bytes), "me.png"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.data.startswith(b"%PDF")
    assert "attachment" in response.headers["Content-Disposition"]


def test_generate_without_name_shows_errors(client):
    response = client.post("/generate", data={"title": "Разработчик"})

    assert response.status_code == 400
    page = response.get_data(as_text=True)
    assert "Укажите имя и фамилию." in page
    assert 'value="Разработчик"' in page  # введённые данные сохраняются


def test_summary_block_is_the_last_section(client):
    page = client.get("/").get_data(as_text=True)

    skills = page.index("<legend>Навыки и языки</legend>")
    about = page.index("<legend>О себе</legend>")
    submit = page.index("Скачать PDF")
    assert skills < about < submit
    assert 'name="summary"' not in page[: page.index("<legend>Формат работы и зарплата</legend>")]


def test_summary_api_builds_text(client):
    response = client.post(
        "/api/summary",
        data={"title": "Python-разработчик", "skills": "Python, Flask", "english_level": "B1"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["summary"] == "Python-разработчик. Опираюсь на Python и Flask."
    assert payload["message"] == ""


def test_summary_api_without_facts(client):
    payload = client.post("/api/summary", data={"full_name": "Иван"}).get_json()

    assert payload["summary"] == ""
    assert "должность" in payload["message"]


def test_market_api_returns_report(client):
    response = client.post(
        "/api/market",
        data={
            "title": "Python-разработчик",
            "skills": "Python, Django",
            "experience_start": "2023-01",
            "experience_end": "",
            "experience_current": "1",
        },
    )

    assert response.status_code == 200
    report = response.get_json()
    assert report["queries"] == ["Python-разработчик", "Python", "Django"]
    assert report["vacancies"][0]["title"] == "Middle Python-разработчик"
    assert report["salary"]["median"] > 0


def test_market_api_without_title(client):
    report = client.post("/api/market", data={}).get_json()

    assert report["vacancies"] == []
    assert report["message"]


def test_too_large_upload(app, client):
    app.config["MAX_CONTENT_LENGTH"] = 1024

    response = client.post(
        "/generate",
        data={"full_name": "Иван", "photo": (BytesIO(b"0" * 4096), "big.png")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 413
