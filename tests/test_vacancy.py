from site_monitor.schemas.vacancy import Vacancy, normalize_url


def make(**kwargs):

    base = {
        "site": "Acme",
        "title": "Account Manager",
        "url": "https://acme.com/jobs/1",
    }

    base.update(kwargs)

    return Vacancy(**base)


def test_normalize_url_strips_tracking_and_trailing_slash():

    assert normalize_url(
        "https://Acme.com/jobs/1/?utm_source=x&gh_src=y"
    ) == "https://acme.com/jobs/1"


def test_normalize_url_keeps_meaningful_query():

    assert normalize_url(
        "https://acme.com/jobs?id=42"
    ) == "https://acme.com/jobs?id=42"


def test_same_posting_with_tracking_params_has_one_fingerprint():

    plain = make(direct=True)

    tracked = make(
        url="https://acme.com/jobs/1?utm_campaign=mail",
        direct=True,
    )

    assert plain.fingerprint == tracked.fingerprint


def test_different_postings_differ():

    assert make(direct=True).fingerprint != make(
        url="https://acme.com/jobs/2",
        direct=True,
    ).fingerprint


def test_non_direct_falls_back_to_site_title_location():
    """Без своего URL вакансии отпечаток берётся из полей, иначе все
    вакансии одной страницы схлопнулись бы в одну."""

    first = make(title="Account Manager", location="Malta")

    same = make(title="  account   manager ", location="malta")

    other = make(title="Account Manager", location="Cyprus")

    assert first.fingerprint == same.fingerprint

    assert first.fingerprint != other.fingerprint


def test_as_line_joins_available_fields():

    vacancy = make(location="Malta", department="Sales")

    assert vacancy.as_line() == "Account Manager — Malta — Sales"


def test_as_line_skips_empty_fields():

    assert make().as_line() == "Account Manager"
