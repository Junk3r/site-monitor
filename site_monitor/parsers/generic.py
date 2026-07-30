from selectolax.parser import HTMLParser


class GenericParser:

    def parse_title(self, html: str) -> str:
        tree = HTMLParser(html)

        title = tree.css_first("title")

        if title:
            return title.text()

        return "No title found"