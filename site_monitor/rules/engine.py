import inspect


class RuleEngine:

    def __init__(self, rules=None):
        self.rules = rules or []


    async def evaluate(
        self,
        site: str,
        url: str,
        old_content: str,
        new_content: str,
    ):

        events = []

        for rule in self.rules:
            result = rule.check(
                site=site,
                url=url,
                old_content=old_content,
                new_content=new_content,
            )

            if inspect.isawaitable(result):
                result = await result

            if result:
                events.append(result)

        return events
