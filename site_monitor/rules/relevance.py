import json

import httpx

from loguru import logger

from site_monitor.rules.models import OpportunityEvent


CANDIDATE_PROFILE = (
    "Candidate profile:\n"
    "- Mid/senior Account Manager / Customer Success Manager\n"
    "- Current: CSM at Sumsub (KYC/KYB verification SaaS), managing "
    "~2.2M EUR ARR portfolio, 80+ clients, MENA region, 92% retention\n"
    "- Past: Business Development Manager in Crypto (exchange listings, "
    "KOL partnerships, negotiations with top-100 exchanges), "
    "senior IP lawyer (gaming industry)\n"
    "- Strong domains: iGaming, Crypto, SaaS, KYC/compliance-adjacent\n"
    "- Skills: retention, upsell/cross-sell, QBRs, churn recovery, "
    "negotiation, partnerships, stakeholder management\n"
    "- Languages: English C1, Russian native\n"
    "- Location: Belgrade, Serbia. Open to remote, hybrid, or on-site "
    "in Europe/UAE. NOT open to positions located in Russia\n"
)

SCORING_SCALE = (
    "Score meaning:\n"
    "1-3: wrong profile (technical, junior, unrelated function)\n"
    "4-6: adjacent role or unclear fit (right function but wrong "
    "seniority/domain, or too little information)\n"
    "7-8: direct fit in role OR domain (AM/CSM/BizDev title, or "
    "strong-domain company with relevant commercial role)\n"
    "9-10: direct fit in role AND domain, plus remote/Europe/UAE "
    "or Russian-speaking market focus\n"
)


class RelevanceScorer:

    def __init__(
        self,
        base_url: str,
        model: str,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model


    async def score(
        self,
        event: OpportunityEvent
    ) -> OpportunityEvent:

        vacancy = "\n".join(
            event.matched_lines
        )

        prompt = (
            f"Company: {event.site}\n"
            f"Vacancy (lines scraped from careers page):\n{vacancy}\n\n"
            f"Rate how well this vacancy fits the candidate. "
            f"Return JSON: {{\"score\": <1-10>, \"reason\": "
            f"\"<one short sentence>\"}}"
        )

        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "messages": [
                {
                    "role": "system",
                    "content": CANDIDATE_PROFILE + "\n" + SCORING_SCALE,
                },
                {"role": "user", "content": prompt},
            ],
        }

        try:

            async with httpx.AsyncClient(
                timeout=180
            ) as client:

                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                )

                response.raise_for_status()

                content = response.json()["message"]["content"]

            data = json.loads(content)

            score = int(data["score"])

            if not 1 <= score <= 10:
                raise ValueError(f"score out of range: {score}")

            event.ai_score = score
            event.ai_reason = str(data.get("reason", ""))[:300]

        except Exception as e:

            logger.error(
                f"Relevance scoring for {event.site} failed: {e}"
            )

        return event
