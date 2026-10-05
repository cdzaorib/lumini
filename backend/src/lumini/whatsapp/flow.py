"""Deterministic WhatsApp flow (plan §4/§6): numbered choices over the approved catalog.

The bot only shows published content, never interprets health information and never decides
prices or times: slots and holds come from the booking service. Anything about health, a request
for a person, or a booking the rules do not allow goes to the team (human mode).

State keeps ids and the visible options only; the name typed for a reservation stays there just
until the hold is created.
"""

import hashlib
import re
import unicodedata
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from lumini.ai.assistant import Assistant
from lumini.ai.contracts import AnswerRequest, ClassifyRequest, ServiceFacts, ServiceRef
from lumini.ai.redaction import redact
from lumini.booking.calendar import (
    CalendarAdapter,
    CalendarNotConfigured,
    CalendarRejected,
    CalendarUnavailable,
)
from lumini.booking.policy import CLINIC_TZ, DEFAULT_POLICY
from lumini.booking.service import (
    BookingError,
    HoldRequest,
    InvalidBookingRequest,
    NotBookable,
    SlotUnavailable,
    available_slots,
    create_hold,
)
from lumini.catalog.schemas import PublicService
from lumini.catalog.service import list_public_services
from lumini.leads.service import brazilian_phone
from lumini.models import Service
from lumini.whatsapp import texts

DAYS_AHEAD = 14
MAX_DAY_OPTIONS = 6
MAX_TIME_OPTIONS = 12

_OPT_OUT = {"stop", "parar", "sair", "descadastrar", "nao quero receber"}
_HUMAN = ("equipe", "atendente", "humano", "humana", "uma pessoa", "falar com alguem")
_GREETING = {"0", "menu", "inicio", "voltar", "oi", "ola", "bom dia", "boa tarde", "boa noite"}
# Conservative: any mention sends the person to the team; the bot never asks for details.
_HEALTH = (
    "gravida",
    "gestante",
    "gestacao",
    "amamenta",
    "lactante",
    "diabet",
    "hipertens",
    "pressao alta",
    "alergi",
    "alergic",
    "remedio",
    "medicament",
    "anticoagul",
    "doenca",
    "cancer",
    "quimioterapia",
    "cirurgia",
    "operei",
    "operada",
    "marcapasso",
    "epilep",
    "convuls",
    "tireoide",
    "infeccao",
    "ferida",
    "lesao",
    "queloide",
    "herpes",
    "dermatite",
    "isotretinoina",
    "roacutan",
    "trombose",
    "varize",
    "dor ",
    "doi ",
    "sangra",
    "inflama",
    "tratamento medico",
    "minha medica",
    "meu medico",
)


@dataclass
class Reply:
    text: str
    state: dict[str, Any]
    handoff: str | None = None  # reason: the conversation goes to the team after this reply
    opt_out: bool = False


@dataclass
class Context:
    session: AsyncSession
    calendar: CalendarAdapter | None
    conversation_id: uuid.UUID
    phone: str | None
    now: datetime
    assistant: Assistant | None = None
    high_confidence: float = 0.85
    medium_confidence: float = 0.6
    _catalog: list[PublicService] | None = field(default=None, repr=False)

    async def catalog(self) -> list[PublicService]:
        if self._catalog is None:
            async with self.session.begin():
                self._catalog = await list_public_services(self.session)
        return self._catalog

    async def service(self, service_id: str | None) -> PublicService | None:
        return next((item for item in await self.catalog() if str(item.id) == service_id), None)


def normalize(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text.lower())
    plain = "".join(char for char in folded if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", plain).strip()


def choice(text: str, count: int) -> int | None:
    """1-based option from replies like "2", "2.", "opção 2", "2) Agendar"."""
    match = re.fullmatch(r"(?:opcao\s*)?(\d{1,2})\s*[.)\-]?(?:\s.*)?", normalize(text))
    if match is None:
        return None
    number = int(match.group(1))
    return number if 1 <= number <= count else None


def _handoff(text: str = texts.HANDOFF, reason: str = "requested") -> Reply:
    return Reply(text, {}, handoff=reason)


def _bookable(item: PublicService) -> bool:
    return item.booking_mode == "direct" and bool(item.professionals)


def local_route(text: str) -> str | None:
    """Decisions taken before any model sees the text (ADR-007): opt-out, health, a person."""
    plain = normalize(text)
    if plain in _OPT_OUT:
        return "opt_out"
    if any(word in f" {plain} " for word in _HEALTH):
        return "health"
    if any(word in plain for word in _HUMAN):
        return "human"
    return None


async def step(ctx: Context, state: dict[str, Any], text: str | None) -> Reply:
    if text is None or not text.strip():
        return Reply(texts.NON_TEXT, state)
    plain = normalize(text)
    local = local_route(text)
    if local == "opt_out":
        return Reply(texts.OPT_OUT, state, opt_out=True)
    if local == "health":
        return _handoff(texts.HEALTH_HANDOFF, "health_condition")
    if local == "human":
        return _handoff()
    current = state.get("step")
    if plain in _GREETING or current is None:
        return Reply(texts.MENU, {"step": "menu"})
    handler = _STEPS.get(str(current))
    if handler is None:
        return Reply(texts.MENU, {"step": "menu"})
    reply = await handler(ctx, state, text)
    if reply is None and ctx.assistant is not None and current in _ASSISTED:
        # Free text where a number was expected: let the model suggest a route (ADR-018).
        reply = await _assisted(ctx, state, text)
    if reply is not None:
        return reply
    misses = int(state.get("misses", 0)) + 1
    return Reply(texts.NOT_UNDERSTOOD, {**state, "misses": misses})


async def _menu(ctx: Context, state: dict[str, Any], text: str) -> Reply | None:
    picked = choice(text, 3)
    if picked == 3:
        return _handoff()
    if picked in (1, 2):
        return await _categories(ctx, "book" if picked == 2 else "browse")
    return None


async def _categories(ctx: Context, intent: str) -> Reply:
    services = [item for item in await ctx.catalog() if intent == "browse" or _bookable(item)]
    if not services:
        return _handoff(
            "Ainda não há procedimentos disponíveis por aqui. " + texts.HANDOFF, "no_catalog"
        )
    categories = sorted({item.category for item in services})
    if len(categories) == 1:
        return _services(services, intent, categories[0])
    return Reply(
        "Qual área te interessa?\n" + texts.numbered(categories),
        {"step": "categories", "intent": intent, "options": categories},
    )


def _services(services: list[PublicService], intent: str, category: str) -> Reply:
    chosen = sorted(
        (item for item in services if item.category == category), key=lambda item: item.name
    )
    return Reply(
        "Escolha o procedimento:\n" + texts.numbered([item.name for item in chosen]),
        {
            "step": "services",
            "intent": intent,
            "category": category,
            "options": [str(item.id) for item in chosen],
        },
    )


async def _pick_category(ctx: Context, state: dict[str, Any], text: str) -> Reply | None:
    options = list(state.get("options", []))
    picked = choice(text, len(options))
    if picked is None:
        return None
    intent = str(state.get("intent", "browse"))
    services = [item for item in await ctx.catalog() if intent == "browse" or _bookable(item)]
    return _services(services, intent, options[picked - 1])


async def _pick_service(ctx: Context, state: dict[str, Any], text: str) -> Reply | None:
    options = list(state.get("options", []))
    picked = choice(text, len(options))
    if picked is None:
        return None
    item = await ctx.service(options[picked - 1])
    if item is None:
        return Reply(texts.MENU, {"step": "menu"})  # unpublished meanwhile
    return _detail(item)


_SERVICE_OPTIONS = texts.numbered(["Agendar", "Ver outros procedimentos", "Falar com a equipe"])


def _detail(item: PublicService) -> Reply:
    lines = [item.name, "", item.description]
    if item.content.objectives:
        lines += ["", "Objetivos: " + "; ".join(item.content.objectives) + "."]
    lines += [
        "",
        f"Duração aproximada: {item.duration_minutes} minutos. "
        + texts.price_line(item.content.price_kind, item.price_brl),
    ]
    if item.booking_mode != "direct":
        lines += ["", "Este procedimento começa com uma avaliação, combinada com a equipe."]
    lines += ["", _SERVICE_OPTIONS]
    return Reply("\n".join(lines), {"step": "service", "service_id": str(item.id)})


async def _service_action(ctx: Context, state: dict[str, Any], text: str) -> Reply | None:
    picked = choice(text, 3)
    if picked is None:
        return None
    if picked == 3:
        return _handoff()
    if picked == 2:
        return await _categories(ctx, "browse")
    item = await ctx.service(state.get("service_id"))
    if item is None:
        return Reply(texts.MENU, {"step": "menu"})
    if not _bookable(item):
        return _handoff(texts.HANDOFF, "evaluation")
    return Reply(texts.HEALTH_QUESTION, {"step": "health", "service_id": str(item.id)})


async def _health(ctx: Context, state: dict[str, Any], text: str) -> Reply | None:
    picked = choice(text, 2)
    if picked is None:
        return None
    if picked == 1:
        return _handoff(texts.HEALTH_HANDOFF, "health_condition")
    item = await ctx.service(state.get("service_id"))
    if item is None or not _bookable(item):
        return Reply(texts.MENU, {"step": "menu"})
    if len(item.professionals) == 1:
        return await _days(ctx, str(item.id), str(item.professionals[0].id))
    people = sorted(item.professionals, key=lambda person: person.display_name)
    return Reply(
        "Com qual profissional?\n" + texts.numbered([person.display_name for person in people]),
        {
            "step": "professional",
            "service_id": str(item.id),
            "options": [str(person.id) for person in people],
        },
    )


async def _pick_professional(ctx: Context, state: dict[str, Any], text: str) -> Reply | None:
    options = list(state.get("options", []))
    picked = choice(text, len(options))
    if picked is None:
        return None
    return await _days(ctx, str(state.get("service_id")), options[picked - 1])


async def _slots(ctx: Context, service_id: str, professional_id: str) -> list[datetime] | Reply:
    if ctx.calendar is None:
        return _handoff(texts.HANDOFF, "calendar_not_configured")
    today = ctx.now.astimezone(CLINIC_TZ).date()
    try:
        return await available_slots(
            ctx.session,
            ctx.calendar,
            service_id=uuid.UUID(service_id),
            professional_id=uuid.UUID(professional_id),
            first_day=today,
            last_day=today + timedelta(days=DAYS_AHEAD - 1),
            now=ctx.now,
        )
    except CalendarUnavailable:
        return Reply(texts.CALENDAR_DOWN, {"step": "menu"})
    except (CalendarNotConfigured, CalendarRejected, NotBookable):
        return _handoff(texts.HANDOFF, "agenda_unavailable")


async def _days(ctx: Context, service_id: str, professional_id: str) -> Reply:
    found = await _slots(ctx, service_id, professional_id)
    if isinstance(found, Reply):
        return found
    by_day: OrderedDict[str, int] = OrderedDict()
    for slot in found:
        key = slot.astimezone(CLINIC_TZ).date().isoformat()
        by_day[key] = by_day.get(key, 0) + 1
    days = list(by_day)[:MAX_DAY_OPTIONS]
    if not days:
        return Reply(texts.NO_SLOTS, {"step": "menu"})
    labels = [
        f"{texts.day(datetime.fromisoformat(day + 'T12:00:00').replace(tzinfo=CLINIC_TZ))}"
        f" ({by_day[day]} horários)"
        for day in days
    ]
    return Reply(
        "Escolha o dia:\n" + texts.numbered(labels),
        {
            "step": "days",
            "service_id": service_id,
            "professional_id": professional_id,
            "options": days,
        },
    )


def _spread(slots: list[datetime], limit: int) -> list[datetime]:
    if len(slots) <= limit:
        return slots
    stride = len(slots) / limit
    return [slots[int(index * stride)] for index in range(limit)]


async def _times(ctx: Context, state: dict[str, Any], day: str, prefix: str = "") -> Reply:
    service_id, professional_id = str(state["service_id"]), str(state["professional_id"])
    found = await _slots(ctx, service_id, professional_id)
    if isinstance(found, Reply):
        return found
    chosen = _spread(
        [slot for slot in found if slot.astimezone(CLINIC_TZ).date().isoformat() == day],
        MAX_TIME_OPTIONS,
    )
    if not chosen:
        return await _days(ctx, service_id, professional_id)
    return Reply(
        (prefix + "\n" if prefix else "")
        + f"Horários livres ({texts.day(chosen[0])}):\n"
        + texts.numbered([texts.time(slot) for slot in chosen]),
        {
            "step": "times",
            "service_id": service_id,
            "professional_id": professional_id,
            "day": day,
            "options": [slot.isoformat() for slot in chosen],
        },
    )


async def _pick_day(ctx: Context, state: dict[str, Any], text: str) -> Reply | None:
    options = list(state.get("options", []))
    picked = choice(text, len(options))
    if picked is None:
        return None
    return await _times(ctx, state, options[picked - 1])


async def _pick_time(ctx: Context, state: dict[str, Any], text: str) -> Reply | None:
    options = list(state.get("options", []))
    picked = choice(text, len(options))
    if picked is None:
        return None
    return Reply(
        texts.ASK_NAME,
        {
            "step": "name",
            "service_id": state["service_id"],
            "professional_id": state["professional_id"],
            "day": state["day"],
            "slot": options[picked - 1],
        },
    )


async def _name(ctx: Context, state: dict[str, Any], text: str) -> Reply | None:
    name = " ".join(text.split())
    if not 2 <= len(name) <= 120 or "<" in name or ">" in name or name.isdigit():
        return Reply(texts.BAD_NAME, state)
    if ctx.phone is None:  # web chat: WhatsApp is where the reservation notices go
        return Reply(texts.ASK_PHONE, {**state, "step": "phone", "name": name})
    return await _summary(ctx, {**state, "name": name})


async def _phone(ctx: Context, state: dict[str, Any], text: str) -> Reply | None:
    try:
        phone = brazilian_phone(text)
    except ValueError:
        return Reply(texts.BAD_PHONE, state)
    return await _summary(ctx, {**state, "phone": phone})


async def _summary(ctx: Context, state: dict[str, Any]) -> Reply:
    item = await ctx.service(state.get("service_id"))
    if item is None:
        return Reply(texts.MENU, {"step": "menu"})
    person = next(
        (p for p in item.professionals if str(p.id) == state.get("professional_id")), None
    )
    slot = datetime.fromisoformat(str(state["slot"]))
    summary = (
        f"Confirmando: {item.name}"
        + (f" com {person.display_name}" if person else "")
        + f", {texts.day(slot)}, às {texts.time(slot)}. O horário fica reservado por 2 horas "
        f"para o pagamento do sinal de {texts.money(item.deposit_brl)}.\n"
        + texts.numbered(["Confirmar reserva", "Escolher outro horário"])
    )
    return Reply(summary, {**state, "step": "confirm"})


async def _confirm(ctx: Context, state: dict[str, Any], text: str) -> Reply | None:
    picked = choice(text, 2)
    if picked is None:
        return None
    if picked == 2:
        return await _times(ctx, state, str(state["day"]))
    phone = ctx.phone or state.get("phone")
    if ctx.calendar is None or not isinstance(phone, str):
        return _handoff(texts.HANDOFF, "no_phone" if phone is None else "agenda_unavailable")
    service_id, professional_id, slot = state["service_id"], state["professional_id"], state["slot"]
    # Same conversation + same choice = same key: repeating "1" never creates a second hold.
    raw = f"{ctx.conversation_id}:{service_id}:{professional_id}:{slot}"
    request = HoldRequest(
        idempotency_key="wa:" + hashlib.sha256(raw.encode()).hexdigest()[:40],
        service_id=uuid.UUID(str(service_id)),
        professional_id=uuid.UUID(str(professional_id)),
        starts_at=datetime.fromisoformat(str(slot)),
        contact_name=str(state.get("name", "")),
        contact_phone=phone,
    )
    try:
        await create_hold(ctx.session, ctx.calendar, request, now=ctx.now, policy=DEFAULT_POLICY)
    except SlotUnavailable:
        return await _times(ctx, state, str(state["day"]), texts.SLOT_TAKEN)
    except CalendarUnavailable:
        return Reply(texts.CALENDAR_DOWN, {k: v for k, v in state.items() if k != "name"})
    except (InvalidBookingRequest, CalendarNotConfigured, CalendarRejected, BookingError):
        return _handoff(texts.HANDOFF, "booking_refused")
    return Reply(texts.HOLD_REQUESTED, {"step": "menu"})


# Steps where free text may be interpreted by the model. Never name or confirmation.
_ASSISTED = {"menu", "categories", "services", "service"}


async def _assisted(ctx: Context, state: dict[str, Any], text: str) -> Reply | None:
    assistant = ctx.assistant
    if assistant is None:
        return None
    if state.get("step") == "service":
        answered = await _answer(ctx, assistant, state, text)
        if answered is not None:
            return answered
    catalog = await ctx.catalog()
    if not catalog:
        return None
    result = await assistant.classify(
        ctx.session,
        ClassifyRequest(
            text=redact(text),
            step=str(state.get("step")),
            services=[
                ServiceRef(id=str(item.id), name=item.name, category=item.category)
                for item in catalog
            ],
        ),
    )
    if result is None or result.confidence < ctx.medium_confidence:
        return None
    if result.intent == "health":
        return _handoff(texts.HEALTH_HANDOFF, "health_condition")
    if result.intent == "human":
        return _handoff()
    if result.intent == "browse":
        return await _categories(ctx, "browse")
    item = await ctx.service(result.service_id)
    if item is None or result.intent not in ("service_info", "book"):
        return None
    if result.confidence < ctx.high_confidence:
        return Reply(
            f"Você está falando de {item.name}?\n"
            + texts.numbered(["Sim", "Não, quero ver a lista"]),
            {"step": "clarify", "service_id": str(item.id), "intent": result.intent},
        )
    if result.intent == "book" and _bookable(item):
        return Reply(texts.HEALTH_QUESTION, {"step": "health", "service_id": str(item.id)})
    return _detail(item)


async def _clarify(ctx: Context, state: dict[str, Any], text: str) -> Reply | None:
    picked = choice(text, 2)
    if picked is None:
        return None
    if picked == 2:
        return await _categories(ctx, "browse")
    item = await ctx.service(state.get("service_id"))
    if item is None:
        return Reply(texts.MENU, {"step": "menu"})
    if state.get("intent") == "book" and _bookable(item):
        return Reply(texts.HEALTH_QUESTION, {"step": "health", "service_id": str(item.id)})
    return _detail(item)


NOT_IN_FACTS = (
    "Essa informação eu não tenho aprovada por aqui. A profissional pode explicar melhor: "
    "responda 3 para falar com a equipe.\n"
)


async def _answer(
    ctx: Context, assistant: Assistant, state: dict[str, Any], question: str
) -> Reply | None:
    item = await ctx.service(state.get("service_id"))
    if item is None:
        return None
    async with ctx.session.begin():
        stored = await ctx.session.get(Service, item.id)
    restrictions = list((stored.content if stored else {}).get("communication_restrictions", []))
    facts = ServiceFacts(
        name=item.name,
        description=item.description,
        objectives=item.content.objectives,
        audience=item.content.audience,
        preparation=item.content.preparation,
        aftercare=item.content.aftercare,
        human_guidance=item.content.human_guidance,
        duration_minutes=item.duration_minutes,
        price_text=texts.price_line(item.content.price_kind, item.price_brl),
        restrictions=[str(entry) for entry in restrictions],
    )
    answer = await assistant.answer(
        ctx.session, AnswerRequest(question=redact(question), facts=facts)
    )
    text = (answer + "\n\n") if answer else NOT_IN_FACTS
    return Reply(text + _SERVICE_OPTIONS, state)


_STEPS = {
    "menu": _menu,
    "categories": _pick_category,
    "services": _pick_service,
    "service": _service_action,
    "health": _health,
    "professional": _pick_professional,
    "days": _pick_day,
    "times": _pick_time,
    "name": _name,
    "phone": _phone,
    "confirm": _confirm,
    "clarify": _clarify,
}
