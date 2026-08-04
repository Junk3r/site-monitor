"""Публичные JSON API рекрутинговых платформ.

Даёт структурированные вакансии (заголовок, локация, отдел, прямая ссылка)
без запуска браузера. Всё, что не распознано, уходит в PlaywrightFetcher.
"""

import re

from urllib.parse import urlsplit

import httpx

from loguru import logger

from site_monitor.schemas.vacancy import Vacancy


TIMEOUT = 30

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
}

LOCALE_SEGMENT = re.compile(
    r"^[a-z]{2}(-[a-zA-Z]{2})?$"
)

WORKDAY_PAGE_SIZE = 20

WORKDAY_MAX_JOBS = 400


def _segments(url: str) -> list[str]:

    return [
        part
        for part in urlsplit(url).path.split("/")
        if part
    ]


def detect(url: str) -> tuple[str, dict] | None:
    """Определяет платформу по URL. Возвращает (platform, params) или None."""

    parts = urlsplit(url)

    host = parts.netloc.lower()

    segments = _segments(url)


    if "greenhouse.io" in host and segments:
        return "greenhouse", {"token": segments[0]}


    if "ashbyhq.com" in host and segments:
        return "ashby", {"token": segments[0]}


    if "workable.com" in host and segments:
        return "workable", {"token": segments[0]}


    if host.endswith(".jobs.personio.com"):
        return "personio", {"token": host.split(".")[0]}


    if host.endswith(".teamtailor.com"):
        return "teamtailor", {"host": host}


    if host.endswith(".bamboohr.com"):
        return "bamboohr", {"token": host.split(".")[0]}


    if host.endswith(".pinpointhq.com"):
        return "pinpoint", {"host": host}


    if ".myworkdayjobs.com" in host:

        board = [
            segment
            for segment in segments
            if not LOCALE_SEGMENT.match(segment)
        ]

        if board:
            return "workday", {
                "host": host,
                "tenant": host.split(".")[0],
                "board": board[0],
            }


    return None


async def _greenhouse(client, params, site_name):

    token = params["token"]

    response = await client.get(
        f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
    )

    response.raise_for_status()

    return [
        Vacancy(
            site=site_name,
            title=job.get("title", ""),
            url=job.get("absolute_url", ""),
            location=(job.get("location") or {}).get("name", ""),
            source="greenhouse",
            external_id=str(job.get("id", "")),
            published_at=job.get("first_published", "") or "",
            direct=True,
        )
        for job in response.json().get("jobs", [])
    ]


async def _ashby(client, params, site_name):

    token = params["token"]

    response = await client.get(
        f"https://api.ashbyhq.com/posting-api/job-board/{token}"
    )

    response.raise_for_status()

    return [
        Vacancy(
            site=site_name,
            title=job.get("title", ""),
            url=job.get("jobUrl", ""),
            location=job.get("location", "") or "",
            department=job.get("department", "") or "",
            source="ashby",
            external_id=str(job.get("id", "")),
            published_at=job.get("publishedAt", "") or "",
            direct=True,
        )
        for job in response.json().get("jobs", [])
        if job.get("isListed", True)
    ]


async def _workable(client, params, site_name):

    token = params["token"]

    response = await client.get(
        f"https://apply.workable.com/api/v1/widget/accounts/{token}",
        params={"details": "true"},
    )

    response.raise_for_status()

    vacancies = []

    for job in response.json().get("jobs", []):

        location = ", ".join(
            value
            for value in (job.get("city"), job.get("country"))
            if value
        )

        vacancies.append(
            Vacancy(
                site=site_name,
                title=job.get("title", ""),
                url=job.get("url") or job.get("shortlink", ""),
                location=location,
                department=job.get("department", "") or "",
                source="workable",
                external_id=str(job.get("shortcode", "")),
                published_at=job.get("published_on", "") or "",
                direct=True,
            )
        )

    return vacancies


async def _personio(client, params, site_name):

    token = params["token"]

    response = await client.get(
        f"https://{token}.jobs.personio.com/search.json"
    )

    response.raise_for_status()

    return [
        Vacancy(
            site=site_name,
            title=job.get("name", ""),
            url=(
                f"https://{token}.jobs.personio.com"
                f"/job/{job.get('id', '')}"
            ),
            location=job.get("office", "") or "",
            department=job.get("department", "") or "",
            source="personio",
            external_id=str(job.get("id", "")),
            direct=True,
        )
        for job in response.json()
    ]


async def _teamtailor(client, params, site_name):

    host = params["host"]

    response = await client.get(
        f"https://{host}/jobs.json"
    )

    response.raise_for_status()

    vacancies = []

    for item in response.json().get("items", []):

        posting = item.get("_jobposting") or {}

        # jobLocation приходит списком Place-объектов (schema.org)
        places = posting.get("jobLocation") or []

        if isinstance(places, dict):
            places = [places]

        address = (
            places[0].get("address") or {}
            if places
            else {}
        )

        location = ", ".join(
            value
            for value in (
                address.get("addressLocality"),
                address.get("addressRegion"),
            )
            if value
        )

        vacancies.append(
            Vacancy(
                site=site_name,
                title=item.get("title", ""),
                url=item.get("url", ""),
                location=location,
                source="teamtailor",
                external_id=str(item.get("id", "")),
                published_at=item.get("date_published", "") or "",
                direct=True,
            )
        )

    return vacancies


async def _bamboohr(client, params, site_name):

    token = params["token"]

    response = await client.get(
        f"https://{token}.bamboohr.com/careers/list"
    )

    response.raise_for_status()

    vacancies = []

    for job in response.json().get("result", []):

        place = job.get("location") or {}

        location = ", ".join(
            value
            for value in (place.get("city"), place.get("state"))
            if value
        )

        job_id = job.get("id", "")

        vacancies.append(
            Vacancy(
                site=site_name,
                title=job.get("jobOpeningName", ""),
                url=f"https://{token}.bamboohr.com/careers/{job_id}",
                location=location,
                department=job.get("departmentLabel", "") or "",
                source="bamboohr",
                external_id=str(job_id),
                direct=True,
            )
        )

    return vacancies


async def _pinpoint(client, params, site_name):

    host = params["host"]

    response = await client.get(
        f"https://{host}/postings.json"
    )

    response.raise_for_status()

    vacancies = []

    for job in response.json().get("data", []):

        place = job.get("location") or {}

        location = ", ".join(
            value
            for value in (place.get("city"), place.get("name"))
            if value
        )

        vacancies.append(
            Vacancy(
                site=site_name,
                title=job.get("title", ""),
                url=job.get("url", ""),
                location=location,
                source="pinpoint",
                external_id=str(job.get("id", "")),
                direct=True,
            )
        )

    return vacancies


async def _workday(client, params, site_name):

    host = params["host"]
    tenant = params["tenant"]
    board = params["board"]

    endpoint = (
        f"https://{host}/wday/cxs/{tenant}/{board}/jobs"
    )

    vacancies = []

    offset = 0

    while offset < WORKDAY_MAX_JOBS:

        response = await client.post(
            endpoint,
            json={
                "appliedFacets": {},
                "limit": WORKDAY_PAGE_SIZE,
                "offset": offset,
                "searchText": "",
            },
            headers={"Content-Type": "application/json"},
        )

        response.raise_for_status()

        payload = response.json()

        postings = payload.get("jobPostings", [])

        if not postings:
            break

        for job in postings:

            path = job.get("externalPath", "")

            vacancies.append(
                Vacancy(
                    site=site_name,
                    title=job.get("title", ""),
                    url=f"https://{host}/{board}{path}",
                    location=job.get("locationsText", "") or "",
                    source="workday",
                    external_id=(job.get("bulletFields") or [""])[0],
                    published_at=job.get("postedOn", "") or "",
                    direct=True,
                )
            )

        offset += WORKDAY_PAGE_SIZE

        if offset >= payload.get("total", 0):
            break

    return vacancies


ADAPTERS = {
    "greenhouse": _greenhouse,
    "ashby": _ashby,
    "workable": _workable,
    "personio": _personio,
    "teamtailor": _teamtailor,
    "bamboohr": _bamboohr,
    "pinpoint": _pinpoint,
    "workday": _workday,
}


class ATSFetcher:

    def __init__(self):

        self.client = None


    async def start(self):

        self.client = httpx.AsyncClient(
            timeout=TIMEOUT,
            headers=HEADERS,
            follow_redirects=True,
        )


    async def close(self):

        if self.client:

            await self.client.aclose()

            self.client = None


    def supports(self, url: str) -> bool:

        return detect(url) is not None


    async def fetch(self, site) -> list[Vacancy] | None:
        """Возвращает вакансии, или None если платформа не распознана
        либо API не ответил — тогда сайт обрабатывает браузер."""

        detected = detect(site.url)

        if detected is None:
            return None

        platform, params = detected

        try:

            vacancies = await ADAPTERS[platform](
                self.client,
                params,
                site.name,
            )

        except Exception as e:

            logger.warning(
                f"ATS {platform} for {site.name} failed: {e}, "
                f"falling back to browser"
            )

            return None


        vacancies = [
            vacancy
            for vacancy in vacancies
            if vacancy.title.strip() and vacancy.url.strip()
        ]

        if not vacancies:

            logger.warning(
                f"ATS {platform} for {site.name} returned no jobs, "
                f"falling back to browser"
            )

            return None


        logger.info(
            f"ATS {platform}: {site.name} -> {len(vacancies)} vacancies"
        )

        return vacancies
