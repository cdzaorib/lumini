"""WhatsApp texts. DRAFTS pending clinic approval (docs/HANDOFF.md): wording may change, rules
may not. They never carry clinical advice, invented prices, payment keys or phone numbers; service
facts come only from the approved, published catalog.
"""

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
HOLD_REQUESTED = (
    "Estou reservando seu horário. Em instantes você recebe a confirmação da reserva e as "
    "orientações sobre o sinal."
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
