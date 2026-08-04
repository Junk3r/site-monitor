from urllib.parse import urljoin, urlsplit

from selectolax.parser import HTMLParser

from site_monitor.schemas.vacancy import Vacancy, normalize_url


# страницы антибот-защиты возвращают HTTP 200 и немного осмысленного
# текста, поэтому по одной только длине их не отличить от нормальных
BLOCK_MARKERS = (
    "performing security verification",
    "checking your browser",
    "just a moment",
    "enable javascript and cookies to continue",
    "verify you are human",
    "cf-browser-verification",
    "ddos protection by",
    "attention required! | cloudflare",
    "access denied",
    "request unsuccessful",
)


def looks_blocked(text: str) -> bool:

    lowered = text[:2000].lower()

    return any(
        marker in lowered
        for marker in BLOCK_MARKERS
    )


MIN_TITLE_LENGTH = 5

MAX_TITLE_LENGTH = 120

MIN_LINKS_FOR_LINK_MODE = 3

SKIP_SCHEMES = (
    "#",
    "mailto:",
    "tel:",
    "javascript:",
)

# типовые пункты навигации, которые иначе уезжают в LLM как кандидаты
NAV_STOPWORDS = {
    "home",
    "about",
    "about us",
    "contact",
    "contact us",
    "careers",
    "career",
    "jobs",
    "all jobs",
    "open positions",
    "vacancies",
    "apply",
    "apply now",
    "read more",
    "learn more",
    "view all",
    "see all",
    "show more",
    "load more",
    "next",
    "previous",
    "privacy policy",
    "cookie policy",
    "cookies",
    "terms",
    "terms of use",
    "imprint",
    "legal",
    "login",
    "log in",
    "sign in",
    "sign up",
    "search",
    "news",
    "blog",
    "products",
    "solutions",
    "partners",
    "投資家",
}


class GenericParser:

    def parse_title(self, html: str) -> str:
        tree = HTMLParser(html)

        title = tree.css_first("title")

        if title:
            return title.text()

        return "No title found"


    def parse_text(self, html: str) -> str:
        tree = HTMLParser(html)

        for node in tree.css(
            "script, style, noscript, svg, template, nav, footer"
        ):
            node.decompose()

        root = tree.body or tree.root

        if root is None:
            return ""

        raw = root.text(separator="\n")

        lines = []

        for line in raw.splitlines():
            normalized = " ".join(line.split())

            if normalized:
                lines.append(normalized)

        return "\n".join(lines)


    def parse_vacancies(
        self,
        html: str,
        base_url: str,
        site_name: str,
    ) -> list[Vacancy]:
        """Вакансии со страницы. Сначала пробуем ссылки — они дают прямой
        URL на вакансию; если ссылок нет, откатываемся на строки текста."""

        links = self.parse_links(
            html,
            base_url,
            site_name
        )

        if len(links) >= MIN_LINKS_FOR_LINK_MODE:
            return links


        return [
            Vacancy(
                site=site_name,
                title=line,
                url=base_url,
                source="text",
                direct=False,
            )
            for line in self.parse_text(html).splitlines()
            if MIN_TITLE_LENGTH <= len(line) <= MAX_TITLE_LENGTH
        ]


    def parse_links(
        self,
        html: str,
        base_url: str,
        site_name: str,
    ) -> list[Vacancy]:

        tree = HTMLParser(html)

        for node in tree.css(
            "script, style, noscript, svg, template"
        ):
            node.decompose()


        page = normalize_url(base_url)

        seen = set()

        vacancies = []

        for node in tree.css("a[href]"):

            href = (node.attributes.get("href") or "").strip()

            if not href or href.startswith(SKIP_SCHEMES):
                continue

            title = " ".join(node.text().split())

            if not (
                MIN_TITLE_LENGTH
                <= len(title)
                <= MAX_TITLE_LENGTH
            ):
                continue

            if title.lower() in NAV_STOPWORDS:
                continue


            url = urljoin(base_url, href)

            if urlsplit(url).scheme not in ("http", "https"):
                continue

            key = normalize_url(url)

            # ссылка на саму же страницу — это навигация, не вакансия
            if key == page or key in seen:
                continue

            seen.add(key)

            vacancies.append(
                Vacancy(
                    site=site_name,
                    title=title,
                    url=url,
                    source="link",
                    direct=True,
                )
            )


        return vacancies
