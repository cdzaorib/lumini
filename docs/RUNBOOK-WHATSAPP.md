# Manual de operação — WhatsApp (Evolution API)

Para a equipe da clínica e quem administra a infraestrutura. Nenhum segredo neste arquivo: chaves e tokens ficam só no gerenciador de segredos.

## Como o bot se comporta

- O bot responde clientes no número da clínica com opções numeradas: conhecer procedimentos aprovados, agendar, falar com a equipe.
- **Quando alguém da equipe responde pelo WhatsApp** (celular ou WhatsApp Web), o bot para naquela conversa, sem prazo para voltar.
- **`#bot`** enviado pela equipe *na própria conversa* devolve a conversa ao bot. A cliente não consegue reativar o bot.
- **`#pausa`** (ou `#humano`) enviado pela equipe pausa o bot sem precisar responder outra coisa.
- Mensagens da cliente sobre saúde (gravidez, remédios, doenças, cirurgia, dor…) ou pedidos de “atendente/equipe” passam a conversa para a equipe. O bot não pergunta detalhes.
- `STOP`/`PARAR` desliga mensagens promocionais; avisos de reserva continuam.
- Avisos de reserva (reserva criada, sinal, confirmação, lembretes, link de alteração) **não são enviados enquanto a conversa está com a equipe**: o outbox registra `human_mode`. Envie `#bot` quando terminar para que os próximos avisos voltem a sair.
- A aba **Integrações** do painel mostra o estado da conexão e quantas conversas estão com a equipe.

## Queda de conexão / novo QR Code

O painel mostra um aviso no topo quando a Evolution informa `close` ou pede um novo QR Code. Enquanto isso, o bot não responde e os avisos ficam na fila (são enviados depois, sem duplicar).

1. Uma pessoa autorizada (lista curta, definida pela clínica) abre o gerenciador da Evolution da instância da Lumini.
2. Gera o QR Code da instância e lê com o celular da clínica: WhatsApp → Aparelhos conectados → Conectar um aparelho.
3. Confirma no painel (Integrações) que o estado voltou a **Conectado**.
4. Se o número foi banido ou trocado, **não** reconecte outro número sem avisar a clínica: as conversas e o histórico mudam.

Reconectar não reenvia mensagens antigas: o sistema ignora histórico com mais de 24 horas e cada mensagem é registrada uma única vez.

## Configuração (infraestrutura)

Variáveis da API **e** do worker, pelo gerenciador de segredos:

| Variável | Conteúdo |
|---|---|
| `LUMINI_EVOLUTION_BASE_URL` | Endereço HTTPS da Evolution |
| `LUMINI_EVOLUTION_INSTANCE` | Nome da instância (letras, números, `_`/`-`) |
| `LUMINI_EVOLUTION_API_KEY` | Chave da instância (segredo) |
| `LUMINI_EVOLUTION_WEBHOOK_TOKEN` | Valor aleatório com 32+ caracteres (segredo) |

Webhook da instância (`POST /webhook/set/{instância}` na Evolution): URL `https://<api>/api/webhooks/evolution`, eventos `MESSAGES_UPSERT`, `SEND_MESSAGE`, `CONNECTION_UPDATE`, `QRCODE_UPDATED`, e **cabeçalho** `Authorization: Bearer <LUMINI_EVOLUTION_WEBHOOK_TOKEN>`. Sem o cabeçalho certo a API responde 401 e nada é processado.

## PoC com instância de teste (pendente — bloqueia lançamento)

Fazer com um número de teste, nunca o número oficial, antes de ligar o bot para clientes:

1. Confirmar que a versão da Evolution envia o cabeçalho customizado do webhook.
2. Enviar mensagem pela API e conferir que o `key.id` da resposta é o mesmo do eco `messages.upsert` (`fromMe: true`). É a base para distinguir bot de equipe.
3. Responder pelo celular e pelo WhatsApp Web: a conversa deve ir para a equipe em segundos.
4. `#bot` e `#pausa` pelo celular; `#bot` enviado pela cliente não deve ter efeito.
5. Número com e sem o nono dígito; contato com endereçamento `@lid`.
6. Derrubar a conexão e reconectar: aviso no painel, fila enviada depois, nada duplicado nem respondido fora de hora.
7. Reentrega do mesmo webhook (mesmo `key.id`) não gera segunda resposta.

Se o passo 2 ou 3 falhar, usar o mecanismo explícito do plano: a equipe pausa com `#pausa` antes de responder.
