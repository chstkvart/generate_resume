"""Короткий текст «О себе»: трудовой путь и навыки, без перечисления полей анкеты."""

import re
from datetime import date

from app.choices import ENGLISH_LEVELS
from app.models import Education, Experience, Resume
from app.services.career import total_experience_months

NOT_ENOUGH_DATA = (
    "Укажите должность, опыт, образование или навыки — по ним можно составить текст «О себе»."
)

_SKILL_LIMIT = 5
_HIGHLIGHT_LIMIT = 140
_PATH_LIMIT = 3


def generate_summary(resume: Resume, today: date | None = None) -> str | None:
    """Два-четыре предложения, которые представляют специалиста."""
    today = today or date.today()
    if not _has_substance(resume, today):
        return None
    sentences = [part for part in _sentences(resume, today) if part]
    return " ".join(sentences) or None


def resume_facts(resume: Resume, today: date | None = None) -> dict | None:
    """Факты для нейросети: без имени, контактов, фото и зарплаты."""
    today = today or date.today()
    if not _has_substance(resume, today):
        return None

    facts: dict = {}
    if resume.title.strip():
        facts["должность"] = resume.title.strip()
    experience = experience_label(total_experience_months(resume.experience, today))
    if experience:
        facts["стаж"] = experience
    skills = _clean_skills(resume.skills)[:15]
    if skills:
        facts["навыки"] = skills
    if resume.english_level in ENGLISH_LEVELS:
        facts["английский"] = ENGLISH_LEVELS[resume.english_level]
    if resume.employment:
        facts["формат_работы"] = list(resume.employment)
    if resume.location.strip():
        facts["город"] = resume.location.strip()

    roles = [_role_fact(item) for item in _roles(resume.experience)]
    roles = [item for item in roles if item]
    if roles:
        facts["опыт"] = roles
    else:
        notes = [
            note
            for note in (_fact_description(item.description) for item in resume.experience)
            if note
        ]
        if notes:
            facts["задачи"] = notes

    education = [_education_fact(item) for item in resume.education]
    education = [item for item in education if item]
    if education:
        facts["образование"] = education
    return facts or None


def experience_label(months: int) -> str:
    if months <= 0:
        return ""
    if months < 12:
        return "меньше года"
    return _years_phrase(months)


def _role_fact(item: Experience) -> dict:
    fact = {}
    if item.company.strip():
        fact["компания"] = item.company.strip()
    if item.position.strip():
        fact["должность"] = item.position.strip()
    period = _fact_period(item)
    if period:
        fact["период"] = period
    if item.current:
        fact["сейчас"] = True
    description = _fact_description(item.description)
    if description:
        fact["задачи"] = description
    return fact


def _education_fact(item: Education) -> dict:
    fact = {}
    if item.institution.strip():
        fact["учебное_заведение"] = item.institution.strip()
    if item.degree.strip():
        fact["специальность"] = item.degree.strip()
    years = " — ".join(part for part in (item.start.strip(), item.end.strip()) if part)
    if years:
        fact["годы"] = years
    return fact


def _fact_period(item: Experience) -> str:
    start = item.start.strip()
    end = "н. в." if item.current else item.end.strip()
    return " — ".join(part for part in (start, end) if part)


def _fact_description(description: str) -> str:
    text = " ".join(description.split())
    if len(text) <= 400:
        return text
    cut = text[:400].rsplit(" ", 1)[0]
    return (cut or text[:400]).rstrip(".,;:") + "…"


def _has_substance(resume: Resume, today: date) -> bool:
    if resume.title.strip() or _clean_skills(resume.skills):
        return True
    if total_experience_months(resume.experience, today):
        return True
    if any(item.position or item.company or item.description.strip() for item in resume.experience):
        return True
    return any(item.institution or item.degree for item in resume.education)


def _sentences(resume: Resume, today: date) -> list[str]:
    months = total_experience_months(resume.experience, today)
    roles = _roles(resume.experience)
    title = resume.title.strip()
    headline = title or (roles[-1].position.strip() if roles else "")
    lead = _lead(headline, months)
    path = _path(roles, title)
    # Одна прошлая роль, которая и так названа в первом предложении: компания рядом с ней.
    if _fold_company_into_lead(roles, title) and lead.endswith("."):
        lead = f"{lead[:-1]} в {roles[0].company.strip()}."
        path = ""

    sentences = [lead, path]
    if roles:
        sentences.append(_achievement(roles[-1].description))
    elif not title:
        for item in reversed(resume.experience):
            achievement = _achievement(item.description)
            if achievement:
                sentences.append(achievement)
                break
    sentences.append(_skills(resume.skills, worked=bool(roles or title)))
    if not roles:
        sentences.append(_education(resume.education))
    return sentences


def _fold_company_into_lead(roles: list[Experience], title: str) -> bool:
    if len(roles) != 1 or roles[0].current or not roles[0].company.strip():
        return False
    position = roles[0].position.strip()
    return not position or not title or position.casefold() == title.casefold()


def _lead(role: str, months: int) -> str:
    if months <= 0:
        return f"{role}." if role else ""
    duration = "с опытом меньше года" if months < 12 else f"с опытом {_years_phrase(months)}"
    if role:
        return f"{role} {duration}."
    return f"Опыт работы — {_span(months)}."


def _path(roles: list[Experience], title: str) -> str:
    if not roles:
        return ""
    if _one_company(roles) and _positions_change(roles):
        company = roles[0].company.strip()
        start = _lower_first(roles[0].position.strip())
        end = _lower_first(roles[-1].position.strip())
        link = "теперь" if roles[-1].current else "затем"
        return f"В {company} сначала как {start}, {link} как {end}."
    if len(roles) == 1:
        return _single_role(roles[0], title)

    shown = _milestones(roles)
    steps = [_step(item) for item in shown]
    link = "теперь" if roles[-1].current else "затем"
    if len(steps) == 2:
        return f"Сначала {steps[0]}, {link} {steps[1]}."
    return f"Сначала {steps[0]}, затем {steps[1]}, {link} {steps[2]}."


def _single_role(item: Experience, title: str) -> str:
    company = item.company.strip()
    position = item.position.strip()
    show_position = bool(position) and not _position_is_headline(position, title)
    pos = _lower_first(position) if show_position else ""
    if item.current:
        if company and pos:
            return f"Сейчас работаю в {company} как {pos}."
        if company:
            return f"Сейчас работаю в {company}."
        return f"Сейчас — {pos}." if pos else ""
    if company and pos:
        return f"Раньше — {company}, {pos}."
    if company:
        return f"Раньше — {company}."
    return ""


def _position_is_headline(position: str, title: str) -> bool:
    """Должность уже стоит в первом предложении — не повторять её."""
    if not title:
        return True
    return position.casefold() == title.casefold()


def _skills(skills: list[str], *, worked: bool) -> str:
    items = _clean_skills(skills)[:_SKILL_LIMIT]
    if not items:
        return ""
    listed = items[0] if len(items) == 1 else ", ".join(items[:-1]) + " и " + items[-1]
    verb = "Опираюсь на" if worked else "Умею работать с"
    return f"{verb} {listed}."


def _education(items: list[Education]) -> str:
    filled = [item for item in items if item.institution.strip() or item.degree.strip()]
    if not filled:
        return ""
    item = max(filled, key=lambda entry: entry.end or entry.start)
    parts = [part for part in (item.degree.strip(), item.institution.strip()) if part]
    return f"База — {', '.join(parts)}."


def _roles(items: list[Experience]) -> list[Experience]:
    """От раннего места к позднему, без пустых и подряд повторённых записей."""
    ordered = []
    for item in reversed(_recent_first(items)):
        if not (item.position.strip() or item.company.strip()):
            continue
        if ordered and _same_place(ordered[-1], item):
            continue
        ordered.append(item)
    return ordered


def _recent_first(items: list[Experience]) -> list[Experience]:
    def sort_key(item: Experience) -> tuple[bool, str, str]:
        end = "9999-99" if item.current else (item.end or item.start)
        return (item.current, end, item.start)

    return sorted(items, key=sort_key, reverse=True)


def _milestones(roles: list[Experience]) -> list[Experience]:
    if len(roles) <= _PATH_LIMIT:
        return roles
    middle = roles[len(roles) // 2]
    picked = [roles[0], middle, roles[-1]]
    unique: list[Experience] = []
    for item in picked:
        if not unique or not _same_place(unique[-1], item):
            unique.append(item)
    return unique


def _step(item: Experience) -> str:
    company = item.company.strip()
    position = _lower_first(item.position.strip()) if item.position.strip() else ""
    if company and position:
        return f"{company} как {position}"
    return company or position


def _one_company(roles: list[Experience]) -> bool:
    companies = {item.company.strip() for item in roles if item.company.strip()}
    return len(companies) == 1 and all(item.company.strip() for item in roles)


def _positions_change(roles: list[Experience]) -> bool:
    positions = [item.position.strip().casefold() for item in roles if item.position.strip()]
    return len(positions) >= 2 and positions[0] != positions[-1]


def _same_place(left: Experience, right: Experience) -> bool:
    return (
        left.company.strip().casefold() == right.company.strip().casefold()
        and left.position.strip().casefold() == right.position.strip().casefold()
    )


def _achievement(description: str) -> str:
    line = ""
    for raw in description.splitlines():
        cleaned = raw.strip().lstrip("-•–—* ").strip()
        if cleaned:
            line = cleaned
            break
    if len(line) < 10:
        return ""
    line = _cap_first(_clip(line, _HIGHLIGHT_LIMIT).rstrip(" .,;:"))
    return f"{line}."


def _years_phrase(months: int) -> str:
    years, rest = divmod(months, 12)
    if rest >= 6:
        return "больше " + _genitive_years(years)
    return _plural(years, "год", "года", "лет")


def _span(months: int) -> str:
    if months < 12:
        return "меньше года"
    return _years_phrase(months)


def _genitive_years(years: int) -> str:
    """Форма после «больше»: 1 года, 2 лет, 21 года."""
    if years % 10 == 1 and years % 100 != 11:
        return f"{years} года"
    return f"{years} лет"


def _plural(count: int, one: str, few: str, many: str) -> str:
    mod100 = count % 100
    mod10 = count % 10
    if 11 <= mod100 <= 14:
        word = many
    elif mod10 == 1:
        word = one
    elif 2 <= mod10 <= 4:
        word = few
    else:
        word = many
    return f"{count} {word}"


def _clean_skills(skills: list[str]) -> list[str]:
    items = []
    seen = set()
    for skill in skills:
        cleaned = re.sub(r"\s+", " ", skill).strip()
        key = cleaned.casefold()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        items.append(cleaned)
    return items


def _lower_first(text: str) -> str:
    first = text[:1]
    if first and ("А" <= first <= "я" or first == "Ё"):
        return first.lower() + text[1:]
    return text


def _cap_first(text: str) -> str:
    first = text[:1]
    if first and ("а" <= first <= "я" or first == "ё"):
        return first.upper() + text[1:]
    return text


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return (cut or text[:limit]).rstrip(".,;:") + "…"
