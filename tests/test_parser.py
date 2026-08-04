from site_monitor.parsers.generic import GenericParser, looks_blocked


PARSER = GenericParser()

BASE = "https://acme.com/careers"


def test_links_become_vacancies_with_their_own_url():

    html = """
      <a href="/careers/jobs/1">Account Manager</a>
      <a href="/careers/jobs/2">Customer Success Manager</a>
      <a href="/careers/jobs/3">Backend Engineer</a>
    """

    vacancies = PARSER.parse_vacancies(html, BASE, "Acme")

    assert [v.title for v in vacancies] == [
        "Account Manager",
        "Customer Success Manager",
        "Backend Engineer",
    ]

    assert vacancies[0].url == "https://acme.com/careers/jobs/1"

    assert all(v.direct for v in vacancies)

    assert all(v.source == "link" for v in vacancies)


def test_navigation_and_self_links_are_dropped():

    html = """
      <a href="/careers">Careers</a>
      <a href="https://acme.com/careers">Open positions</a>
      <a href="#main">Skip to content</a>
      <a href="mailto:hr@acme.com">Contact us</a>
      <a href="/privacy">Privacy policy</a>
      <a href="/careers/jobs/1">Account Manager</a>
      <a href="/careers/jobs/2">Customer Success Manager</a>
      <a href="/careers/jobs/3">Partnerships Lead</a>
    """

    titles = [
        v.title
        for v in PARSER.parse_vacancies(html, BASE, "Acme")
    ]

    assert titles == [
        "Account Manager",
        "Customer Success Manager",
        "Partnerships Lead",
    ]


def test_duplicate_urls_collapse():

    html = """
      <a href="/careers/jobs/1">Account Manager</a>
      <a href="/careers/jobs/1/">Account Manager</a>
      <a href="/careers/jobs/2">Client Relations Lead</a>
      <a href="/careers/jobs/3">Growth Manager</a>
    """

    assert len(PARSER.parse_vacancies(html, BASE, "Acme")) == 3


def test_falls_back_to_text_when_page_has_no_links():

    html = """
      <body>
        <h1>Open roles</h1>
        <p>Account Manager</p>
        <p>Customer Success Manager</p>
      </body>
    """

    vacancies = PARSER.parse_vacancies(html, BASE, "Acme")

    assert [v.source for v in vacancies] == ["text", "text", "text"]

    assert not vacancies[0].direct

    assert vacancies[0].url == BASE


def test_parse_text_drops_scripts_and_blank_lines():

    html = """
      <body>
        <script>var x = 1;</script>
        <p>Account   Manager</p>
        <p>   </p>
        <style>.a{}</style>
        <p>Malta</p>
      </body>
    """

    assert PARSER.parse_text(html) == "Account Manager\nMalta"


def test_parse_title():

    assert PARSER.parse_title("<title>Careers</title>") == "Careers"

    assert PARSER.parse_title("<body>no title</body>") == "No title found"


def test_looks_blocked_catches_protection_pages():
    """Заслон отдаёт 200 и осмысленный текст: Playson так проходил
    порог длины с 317 символами."""

    playson = (
        "playson.com\nPerforming security verification\n"
        "This website uses a security service to protect against "
        "malicious bots.\nRay ID:"
    )

    assert looks_blocked(playson)

    assert looks_blocked("Just a moment...")

    assert looks_blocked("Checking your browser before accessing")


def test_looks_blocked_leaves_real_pages_alone():

    assert not looks_blocked(
        "Open roles\nAccount Manager\nMalta\nApply now"
    )
