from typing import Optional

from pydantic import BaseModel


class ArticleFilterParams(BaseModel):
    sentiment: Optional[str] = None
    topic: Optional[str] = None
    risk_level: Optional[str] = None
