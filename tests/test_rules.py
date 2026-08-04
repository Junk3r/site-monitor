from site_monitor.rules.keyword import KeywordRule
from site_monitor.rules.semantic import SemanticRule
from site_monitor.rules.relevance import RelevanceScorer
from site_monitor.schemas.vacancy import Vacancy


INCLUDE = ["account manager", "customer success", "business development"]

EXCLUDE = ["developer", "engineer", "russia"]

LOCATIONS = ["malta", "remote", "london"]


def rule():

    return KeywordRule(
        include=INCLUDE,
        exclude=EXCLUDE,
        locations=LOCATIONS,
    )


def vacancy(title, location="", department=""):

    return Vacancy(
        site="Acme",
        title=title,
        url="https://acme.com/jobs/1",
        location=location,
        department=department,
    )


def test_include_match():

    assert rule().check(vacancy("Account Manager")) is not None


def test_exclude_wins_over_include():

    assert rule().check(
        vacancy("Account Manager", location="Moscow, Russia")
    ) is None


def test_unrelated_title_ignored():

    assert rule().check(vacancy("Backend Engineer")) is None


def test_word_boundary_prevents_substring_hits():

    assert rule().check(vacancy("Accounts Payable Clerk")) is None


def test_department_can_trigger_the_match():
    """Роль внутри Customer Success ловится по отделу, даже если
    заголовок сам по себе нейтральный."""

    assert rule().check(
        vacancy("Project Manager", department="Customer Success")
    ) is not None


def test_location_bonus_applies_only_on_real_location():

    matched = rule().check(vacancy("Account Manager", location="Malta"))

    unmatched = rule().check(vacancy("Account Manager", location="Tokyo"))

    assert matched.confidence > unmatched.confidence


def test_match_reports_keywords():

    match = rule().check(vacancy("Senior Account Manager"))

    assert match.keywords == ["account manager"]

    assert match.via == "keyword"


def test_match_many_returns_only_hits():

    matches = rule().match(
        [
            vacancy("Account Manager"),
            vacancy("Backend Engineer"),
            vacancy("Customer Success Lead"),
        ]
    )

    assert len(matches) == 2


class FakeClient:
    """Подменяет Ollama: считает вызовы и отдаёт заготовленные ответы."""

    def __init__(self, answers=None):
        self.answers = list(answers or [])
        self.batch_sizes = []
        self.calls = 0

    async def chat_json(self, model, system, user, label=""):
        self.calls += 1
        self.batch_sizes.append(len(user.strip().splitlines()))
        return self.answers.pop(0) if self.answers else {"matches": []}


async def test_semantic_batches_long_lists_instead_of_truncating():
    """Раньше список резался до 50 строк и остаток молча терялся."""

    client = FakeClient(
        answers=[{"matches": [1]}, {"matches": [1]}, {"matches": []}]
    )

    semantic = SemanticRule(
        client=client,
        model="test",
        skip_keywords=[],
        exclude=[],
    )

    candidates = [
        vacancy(f"Some Role Number {index}")
        for index in range(120)
    ]

    matches = await semantic.match("Acme", candidates)

    assert client.calls == 3

    assert client.batch_sizes == [50, 50, 20]

    assert len(matches) == 2


async def test_semantic_survives_broken_llm_reply():

    client = FakeClient(answers=[None])

    semantic = SemanticRule(
        client=client,
        model="test",
        skip_keywords=[],
        exclude=[],
    )

    assert await semantic.match("Acme", [vacancy("Some Role Here")]) == []


async def test_semantic_ignores_out_of_range_line_numbers():

    client = FakeClient(answers=[{"matches": [1, 99, -3, "x"]}])

    semantic = SemanticRule(
        client=client,
        model="test",
        skip_keywords=[],
        exclude=[],
    )

    matches = await semantic.match("Acme", [vacancy("Some Role Here")])

    assert len(matches) == 1


class Row:

    def __init__(self, title):
        self.site = "Acme"
        self.title = title
        self.location = ""
        self.ai_score = None
        self.ai_reason = ""


async def test_scorer_applies_scores_to_rows():

    client = FakeClient(
        answers=[
            {
                "scores": [
                    {"n": 1, "score": 9, "reason": "great"},
                    {"n": 2, "score": 3, "reason": "poor"},
                ]
            }
        ]
    )

    rows = [Row("Account Manager"), Row("Backend Engineer")]

    await RelevanceScorer(client=client, model="test").score_many(rows)

    assert rows[0].ai_score == 9

    assert rows[0].ai_reason == "great"

    assert rows[1].ai_score == 3


async def test_scorer_skips_invalid_entries():

    client = FakeClient(
        answers=[
            {
                "scores": [
                    {"n": 1, "score": 42},
                    {"n": 9, "score": 5},
                    "junk",
                ]
            }
        ]
    )

    rows = [Row("Account Manager")]

    await RelevanceScorer(client=client, model="test").score_many(rows)

    assert rows[0].ai_score is None


async def test_scorer_batches_by_ten():

    client = FakeClient()

    rows = [Row(f"Role {index}") for index in range(25)]

    await RelevanceScorer(client=client, model="test").score_many(rows)

    assert client.calls == 3
