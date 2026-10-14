"""WhatsApp texts. DRAFTS pending clinic approval (docs/HANDOFF.md): wording may change, rules
may not. They never carry clinical advice, invented prices, payment keys or phone numbers; service
facts come only from the approved, published catalog.
"""

import re
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal

from lumini.booking.policy import CLINIC_TZ

_WEEKDAYS = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")


def money(value: Decimal) -> str:
    whole, cents = f"{value:.2f}".split(".")
    groups = f"{int(whole):,}".replace(",", ".")
    return f"R$ {groups},{cents}"


def day(instant: datetime) -> str:
    local = instant.astimezone(CLINIC_TZ)
    return f"{_WEEKDAYS[local.weekday()]}, {local:%d/%m}"


def time(instant: datetime) -> str:
    return f"{instant.astimezone(CLINIC_TZ):%H:%M}"


def numbered(options: list[str]) -> str:
    return "\n".join(f"{index}. {option}" for index, option in enumerate(options, start=1))


MENU = (
    "Olá! Este é o atendimento automático da Lumini Estética e Saúde.\n"
    "Responda com o número da opção:\n"
    + numbered(["Conhecer os procedimentos", "Agendar um horário", "Falar com a equipe"])
)
NOT_UNDERSTOOD = (
    "Desculpe, não entendi. Responda só com o número de uma das opções acima. "
    "Para voltar ao início, envie 0; para falar com a equipe, escreva “equipe”."
)
HANDOFF = (
    "Certo! Vou chamar alguém da equipe da Lumini para continuar com você por aqui. "
    "Pode deixar sua mensagem que respondemos assim que possível."
)
HEALTH_HANDOFF = (
    "Obrigada por avisar. Esse tipo de assunto é conversado diretamente com a profissional, "
    "sem passar pelo atendimento automático. Vou chamar a equipe para continuar com você."
)
HEALTH_QUESTION = (
    "Antes de ver os horários: existe alguma condição de saúde ou dúvida que você gostaria de "
    "conversar com a profissional antes do agendamento? Não precisa contar detalhes aqui.\n"
    + numbered(["Sim, quero conversar antes", "Não, quero ver os horários"])
)
OPT_OUT = (
    "Pronto: você não vai receber mensagens promocionais. Avisos sobre reservas e agendamentos "
    "continuam chegando normalmente."
)
NON_TEXT = "Por aqui eu só consigo ler mensagens de texto. Responda com o número da opção."
CALENDAR_DOWN = (
    "Não consegui consultar a agenda agora. Tente de novo em alguns minutos ou escreva “equipe” "
    "para falar com a clínica."
)
NO_SLOTS = (
    "Não encontrei horários livres para os próximos dias. Escreva “equipe” para combinar "
    "diretamente com a clínica ou envie 0 para voltar ao início."
)
SLOT_TAKEN = "Esse horário acabou de ser ocupado. Escolha outro, por favor:"
ASK_NAME = "Para reservar, qual nome devo colocar na reserva?"
BAD_NAME = "Envie só o nome, em texto simples (até 120 letras)."
ASK_PHONE = (
    "Qual é o seu WhatsApp com DDD? A confirmação da reserva, as orientações do sinal e os "
    "lembretes chegam por lá. Usamos esse número só para este atendimento (veja a privacidade "
    "no site)."
)
BAD_PHONE = "Envie o número com DDD, por exemplo (21) 9XXXX-XXXX."
HOLD_REQUESTED = (
    "Estou reservando seu horário. Em instantes você recebe pelo WhatsApp a confirmação da "
    "reserva e as orientações sobre o sinal."
)


def price_line(kind: str, price: Decimal | None) -> str:
    if kind == "fixed" and price is not None:
        return f"Valor: {money(price)}."
    if kind == "from" and price is not None:
        return f"A partir de {money(price)}."
    return "O valor é definido após a avaliação."


# Booking notifications (outbox events). Each receives only booking facts, never contact data.
NOTIFICATIONS = {
    "hold_created": (
        "Seu horário de {service} com {professional} em {day}, às {time}, está reservado por "
        "2 horas, até {deadline}. Para confirmar, falta o sinal de {deposit}."
    ),
    "deposit_instructions": (
        "Sobre o sinal de {deposit}: a equipe da clínica vai enviar os dados de pagamento por "
        "aqui. Depois do pagamento, a confirmação é feita pela clínica e você recebe uma mensagem."
    ),
    # Used instead of the one above when the clinic filled the instructions in the panel.
    "deposit_instructions_configured": (
        "Para confirmar, pague o sinal de {deposit}:\n{instructions}\nDepois do pagamento, a "
        "confirmação é feita pela clínica (comprovante não confirma sozinho) e você recebe uma "
        "mensagem."
    ),
    "hold_expiring": (
        "Sua reserva de {day}, às {time}, termina às {deadline}. Se você já pagou o sinal, a "
        "equipe está conferindo."
    ),
    "hold_expired": (
        "A reserva de {day}, às {time}, expirou e o horário foi liberado. Se quiser, envie 2 "
        "para ver novos horários."
    ),
    "booking_confirmed": (
        "Agendamento confirmado: {service} com {professional}, {day}, às {time}. Até lá!"
    ),
    "booking_rescheduled": (
        "Reagendamento confirmado: {service} com {professional}, {day}, às {time}. "
        "O sinal continua valendo."
    ),
    "manage_link": (
        "Para ver sua reserva e, com mais de 24 horas de antecedência, cancelar ou reagendar, use "
        "seu link pessoal (não compartilhe): {link}"
    ),
    "reminder_24h": "Lembrete: amanhã, {day}, às {time}, você tem {service} com {professional}.",
    "reminder_2h": "Lembrete: hoje às {time} você tem {service} com {professional}.",
    "aftercare": "Recomendações da profissional após {service}:\n{aftercare}",
    "booking_cancelled": "Sua reserva de {day}, às {time}, foi cancelada.",
    "human_handoff": (
        "Precisamos confirmar um detalhe sobre o seu horário de {day}, às {time}. A equipe da "
        "clínica vai falar com você por aqui."
    ),
}

# Clinic-editable operational copy only. Health, consent, reservation/payment rules,
# self-service limits and approved clinical aftercare remain fixed in code/catalog.
# Menu choices are injected from the deterministic flow, never from a custom template.
OPERATIONAL = {
    "menu": "Olá! Este é o atendimento automático da Lumini Estética e Saúde.\n{options}",
    "not_understood": NOT_UNDERSTOOD,
    "handoff": HANDOFF,
    "non_text": NON_TEXT,
    "calendar_down": CALENDAR_DOWN,
    "no_slots": NO_SLOTS,
    "ask_name": ASK_NAME,
    "bad_name": BAD_NAME,
    **{
        key: NOTIFICATIONS[key]
        for key in ("booking_confirmed", "booking_cancelled", "reminder_24h", "reminder_2h")
    },
}
OPERATIONAL_LABELS = {
    "menu": "Saudação e menu",
    "not_understood": "Opção não entendida",
    "handoff": "Encaminhamento para a equipe",
    "non_text": "Mensagem sem texto",
    "calendar_down": "Agenda indisponível",
    "no_slots": "Sem horários disponíveis",
    "ask_name": "Pedido do nome para a reserva",
    "bad_name": "Nome em formato inválido",
    "booking_confirmed": "Agendamento confirmado",
    "booking_cancelled": "Reserva cancelada",
    "reminder_24h": "Lembrete de 24 horas",
    "reminder_2h": "Lembrete de duas horas",
}
_PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")


def placeholders(template: str) -> set[str]:
    return set(_PLACEHOLDER.findall(template))


def validate_operational(key: str, template: str) -> None:
    """Only exact, required placeholders: no attributes, indexing, conversion or format specs."""
    original = OPERATIONAL.get(key)
    if original is None:
        raise ValueError("Unknown operational message")
    remaining = _PLACEHOLDER.sub("", template)
    if "{" in remaining or "}" in remaining or placeholders(template) != placeholders(original):
        raise ValueError("Use exactly the required message placeholders")
    if not template.strip() or len(template) > 1000:
        raise ValueError("Operational message must contain 1 to 1000 characters")


def render(template: str, values: Mapping[str, str]) -> str:
    """Single-pass literal substitution. Values containing braces are never interpreted."""
    return _PLACEHOLDER.sub(lambda match: values[match.group(1)], template)


def operational(
    key: str, overrides: Mapping[str, str], values: Mapping[str, str] | None = None
) -> str:
    template = overrides.get(key, OPERATIONAL[key])
    validate_operational(key, template)
    return render(template, values or {})


def customize_reply(text: str, overrides: Mapping[str, str]) -> str:
    # Exact matches keep clinical replies and dynamically assembled booking rules untouched.
    if text == MENU:
        options = "Responda com o número da opção:\n" + numbered(
            ["Conhecer os procedimentos", "Agendar um horário", "Falar com a equipe"]
        )
        if "menu" in overrides:
            options = "Este é o atendimento automático da Lumini Estética e Saúde.\n" + options
        return operational("menu", overrides, {"options": options})
    for key in (
        "not_understood",
        "handoff",
        "non_text",
        "calendar_down",
        "no_slots",
        "ask_name",
        "bad_name",
    ):
        if text == OPERATIONAL[key]:
            return operational(key, overrides)
    return text
