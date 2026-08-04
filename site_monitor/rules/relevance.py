from loguru import logger


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

INSTRUCTION = (
    "Rate each numbered vacancy for this candidate.\n"
    "Return JSON: {\"scores\": [{\"n\": <line number>, "
    "\"score\": <1-10>, \"reason\": \"<one short sentence>\"}]}. "
    "Include every line exactly once."
)

# по одной вакансии на запрос выходило 125 обращений к модели на скан
SCORE_BATCH_SIZE = 10


class RelevanceScorer:

    def __init__(
        self,
        client,
        model: str,
    ):
        self.client = client
        self.model = model


    async def score_many(
        self,
        opportunities: list,
    ):
        """Проставляет ai_score/ai_reason прямо в переданные объекты."""

        for start in range(0, len(opportunities), SCORE_BATCH_SIZE):

            batch = opportunities[start:start + SCORE_BATCH_SIZE]

            await self._score_batch(batch)

            logger.info(
                f"Scored {min(start + len(batch), len(opportunities))}"
                f"/{len(opportunities)}"
            )

        return opportunities


    async def _score_batch(
        self,
        batch: list,
    ):

        listing = "\n".join(
            f"{index + 1}. {item.site} — {item.title}"
            + (f" — {item.location}" if item.location else "")
            for index, item in enumerate(batch)
        )

        data = await self.client.chat_json(
            model=self.model,
            system=CANDIDATE_PROFILE + "\n" + SCORING_SCALE,
            user=f"{INSTRUCTION}\n\nVacancies:\n{listing}",
            label="scoring",
        )

        if not data:
            return


        scores = data.get("scores", [])

        if not isinstance(scores, list):
            return


        for entry in scores:

            if not isinstance(entry, dict):
                continue

            try:

                number = int(entry["n"])

                score = int(entry["score"])

            except (KeyError, TypeError, ValueError):
                continue

            if not 1 <= number <= len(batch):
                continue

            if not 1 <= score <= 10:
                continue

            item = batch[number - 1]

            item.ai_score = score
            item.ai_reason = str(entry.get("reason", ""))[:300]
