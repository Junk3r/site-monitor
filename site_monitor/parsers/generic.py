from selectolax.parser import HTMLParser


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