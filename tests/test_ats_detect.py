import pytest

from site_monitor.fetchers.ats import detect


@pytest.mark.parametrize(
    "url, platform, key, value",
    [
        (
            "https://job-boards.eu.greenhouse.io/delasportbulgaria",
            "greenhouse",
            "token",
            "delasportbulgaria",
        ),
        (
            "https://job-boards.greenhouse.io/betsson",
            "greenhouse",
            "token",
            "betsson",
        ),
        (
            "https://jobs.ashbyhq.com/leovegasgroup",
            "ashby",
            "token",
            "leovegasgroup",
        ),
        (
            "https://apply.workable.com/novibet/",
            "workable",
            "token",
            "novibet",
        ),
        (
            "https://xtremepush.jobs.personio.com/",
            "personio",
            "token",
            "xtremepush",
        ),
        (
            "https://everymatrix.teamtailor.com/",
            "teamtailor",
            "host",
            "everymatrix.teamtailor.com",
        ),
        (
            "https://altenar.bamboohr.com/careers",
            "bamboohr",
            "token",
            "altenar",
        ),
        (
            "https://gig.pinpointhq.com/",
            "pinpoint",
            "host",
            "gig.pinpointhq.com",
        ),
        (
            "https://betmgminc.wd5.myworkdayjobs.com/BetMGM",
            "workday",
            "board",
            "BetMGM",
        ),
    ],
)
def test_detect_known_platforms(url, platform, key, value):

    detected = detect(url)

    assert detected is not None

    assert detected[0] == platform

    assert detected[1][key] == value


def test_workday_skips_locale_segment():
    """У части досок в пути стоит локаль — доской её считать нельзя."""

    _, params = detect(
        "https://acme.wd3.myworkdayjobs.com/en-US/CareerSite"
    )

    assert params["board"] == "CareerSite"

    assert params["tenant"] == "acme"


def test_workday_keeps_query_out_of_board():

    _, params = detect(
        "https://aristocrat.wd3.myworkdayjobs.com"
        "/AristocratExternalCareersSite/?hiringCompany=abc"
    )

    assert params["board"] == "AristocratExternalCareersSite"


@pytest.mark.parametrize(
    "url",
    [
        "https://careers.softswiss.com/vacancies/",
        "https://playson.com/career",
        "https://kendoo.peopleforce.io/careers",
        "https://greenhouse.io",
    ],
)
def test_detect_returns_none_for_unsupported(url):

    assert detect(url) is None
