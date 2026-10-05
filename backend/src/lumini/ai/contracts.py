"""The only shapes that cross the model boundary: redacted text plus approved facts."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Intent = Literal["service_info", "book", "browse", "human", "health", "other"]
Bounded = Annotated[str, StringConstraints(max_length=300)]


class ServiceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    category: str


class ClassifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: Bounded  # already redacted
    step: str
    services: list[ServiceRef] = Field(max_length=120)


class Classification(BaseModel):
    model_config = ConfigDict(extra="ignore")

    intent: Intent
    service_id: str | None = None
    confidence: float = Field(ge=0, le=1)


class ServiceFacts(BaseModel):
    """Approved, published content only (plus internal restrictions for the writer prompt)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    objectives: list[str]
    audience: str
    preparation: list[str]
    aftercare: list[str]
    human_guidance: str
    duration_minutes: int
    price_text: str
    restrictions: list[str]


class AnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: Bounded  # already redacted
    facts: ServiceFacts


class Answer(BaseModel):
    model_config = ConfigDict(extra="ignore")

    answer: Annotated[str, StringConstraints(max_length=700)]
    grounded: bool
