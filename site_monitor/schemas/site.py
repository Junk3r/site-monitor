from pydantic import BaseModel


class Site(BaseModel):
    name: str
    url: str