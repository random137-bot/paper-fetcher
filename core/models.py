from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date


@dataclass
class Paper:
    title: str
    authors: list[str] = field(default_factory=list)
    date: date | None = None
    doi: str | None = None
    citations: int | None = None
    source: str = ""
    url: str = ""
    abstract: str = ""
    pub_url: str = ""
    eprint_url: str = ""


@dataclass
class TopicInfo:
    path: str
    keywords: list[str]
    paper_count: int
    last_updated: str
