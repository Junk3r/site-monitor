import hashlib

from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit


TRACKING_PARAMS = (
    "utm_",
    "gh_src",
    "gh_jid",
    "source",
    "ref",
)


def normalize_url(url: str) -> str:
    """Убирает трекинговые параметры и хвостовой слеш, чтобы один и тот же
    URL вакансии всегда давал один и тот же fingerprint."""

    parts = urlsplit(url.strip())

    query = "&".join(
        chunk
        for chunk in parts.query.split("&")
        if chunk
        and not chunk.split("=")[0].lower().startswith(TRACKING_PARAMS)
    )

    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path.rstrip("/"),
            query,
            "",
        )
    )


@dataclass
class Vacancy:
    """Одна вакансия — из ATS API, из ссылки на странице или из строки текста."""

    site: str
    title: str
    url: str
    location: str = ""
    department: str = ""
    source: str = "text"
    external_id: str = ""
    published_at: str = ""
    direct: bool = False

    @property
    def fingerprint(self) -> str:

        if self.direct:
            key = normalize_url(self.url)

        else:
            key = "|".join(
                (
                    self.site.strip().lower(),
                    " ".join(self.title.split()).lower(),
                    " ".join(self.location.split()).lower(),
                )
            )

        return hashlib.sha1(
            key.encode("utf-8")
        ).hexdigest()

    def as_line(self) -> str:
        """Одна строка для правил и LLM — заголовок с контекстом."""

        parts = [
            " ".join(self.title.split())
        ]

        if self.location:
            parts.append(" ".join(self.location.split()))

        if self.department:
            parts.append(" ".join(self.department.split()))

        return " — ".join(parts)
