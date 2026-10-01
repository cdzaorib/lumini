# Plano aprovado — Lumini Estética e Saúde

Status: aprovado pelo usuário em 2026-10-01, com backend revisado para Python/FastAPI. Desenvolvimento autorizado; publicação, compras e configurações em produção ficam para etapa específica.

**Texto integral aprovado: `PLANO-ORIGINAL.md`** — o usuário reafirmou em 2026-10-01 que aquele é o plano a ser feito, com a única troca do backend para Python/FastAPI (Celery no lugar de BullMQ). Este arquivo é o resumo operacional e não reduz aquele escopo.

## Objetivo e escopo

Substituir `https://lumini-contato.base44.app/` por landing premium/acolhedora com credibilidade clínica, captura de leads como conversão principal, bot no site e WhatsApp, agenda e painel. Público: mulheres interessadas em estética facial/corporal, emagrecimento saudável e saúde integrativa. SEO local: Mangaratiba e Costa Verde/RJ. Lançamento conjunto de landing, bot e calendário após piloto.

## Experiência pública

Hero com “Tire suas dúvidas e agende sua avaliação”; categorias/objetivos, procedimentos em destaque, como funciona, profissionais e credenciais, diferenciais, FAQ, políticas, localização/horários, CTA final e privacidade/termos. Widget, WhatsApp e página dedicada ao atendimento. FAQ anônimo; dados de contato somente quando necessários para agendar/encaminhar.

Visual premium e suave inspirado no rosa/dourado da marca, mobile-first, teclado/foco/contraste, redução de movimento e imagens otimizadas. Apenas materiais autorizados da clínica. Sem antes/depois no MVP. Depoimentos somente autorizados. Serviços padronizados mostram preço ou “a partir de”; demais, valor após avaliação. Conteúdo incompleto/aprovação ausente fica oculto.

## Catálogo e profissionais

Todos os procedimentos aprovados entram. A referência atual tem cerca de 35 procedimentos; inventário e habilitação ainda serão validados. Campos: nome, categoria, descrição, objetivos, público em linguagem cautelosa, profissional, credencial, duração, intervalo de 15min, modo avaliação/direto, preço, sinal variável por serviço, preparação, cuidados posteriores, condições que exigem contato humano, status de revisão e aprovador/data.

Mapeamento aprovado: estética/injetáveis/capilar/emagrecimento/saúde → Munique; massoterapia/bem-estar → Michele; ambos quando realmente habilitados. Credenciais, atribuições e especialidades devem ser fornecidas e verificadas. Telefones serão fornecidos depois. Cada profissional aprova o conteúdo da sua área. Publicação: rascunho → aprovado → publicado. Qualquer alteração de conteúdo clínico exige nova aprovação.

## Bot e atendimento humano

Conversa natural com árvore aprovada. Explica procedimentos e apresenta opções relacionadas ao objetivo, sem diagnóstico/triagem clínica/prescrição/promessa ou declaração de elegibilidade individual. Pergunta se existe condição a conversar com a profissional; em caso afirmativo, oferece encaminhamento, sem pedir detalhes de saúde nem interpretá-los. Contato humano também disponível para qualquer dúvida não resolvida.

Resposta manual autorizada pelo WhatsApp pausa a automação. Retomada somente por `#bot` autorizado, nunca por timeout. Validar com PoC se Evolution permite distinguir mensagem manual de mensagem do bot. O painel não inclui caixa de atendimento humano própria.

Jev limitado a intenção, serviço, profissional, esclarecimento, encaminhamento e guardrails. Alta confiança segue rota; média pede esclarecimento; baixa/condição de saúde encaminha ao humano. Thresholds devem ser calibrados com dados sintéticos, não inventados como precisão demonstrada. DeepSeek gera texto a partir de conteúdo aprovado. Provedores e modelos específicos exigem verificação de contrato e benchmark; fallback ainda não escolhido. Sem dados pessoais ou de saúde nos modelos.

## Agenda e sinal

Google Calendar é fonte de disponibilidade, com calendários separados por profissional. Bot filtra profissional pelo serviço. PostgreSQL mantém reservas transacionais e histórico; reconciliação trata mudanças manuais no Google.

Fluxo: objetivo/serviço → conteúdo aprovado → profissional → encaminhamento se necessário → horários → revalidação → reserva por 2h → instruções do sinal → confirmação humana autenticada → agendamento confirmado. Sem confirmação até expiração, liberar horário. Mensagem explica as 2h. Resolver confirmação atrasada/conflitos de agenda conservadoramente com humano.

Cancelamento/reagendamento acima de 24h via autoatendimento; abaixo disso ou no limite exato de 24h, humano (detalhe conservador de implementação). Um reagendamento mantém sinal; segundo/exceções/reembolso são humanos. Verificação pelo mesmo WhatsApp ou link temporário seguro. Auditoria das alterações.

Notificações: reserva, instruções do sinal, lembrete de expiração, confirmação, expiração, lembretes 24h e 2h, recomendações aprovadas, link de alteração, encaminhamento. Mensagens idempotentes. Horários em America/Sao_Paulo; instantes persistidos em UTC.

## Painel

Google login com allowlist de e-mails e autorização backend. Leads, reservas, confirmações de sinal, catálogo/preços/durações, profissionais, conteúdo/revisão, recomendações, auditoria, mensagens, métricas e saúde das integrações. Métricas: leads, reservas, sinais, agendamentos, faltas, origem, demanda por procedimento e encaminhamentos.

## Dados e consentimento

Coleta: nome, telefone, cidade/bairro, interesse, procedimento, preferência de horário e consentimento. Preferir dados estruturados e resumo mínimo a histórico bruto integral. Resumos também precisam de minimização. Leads não convertidos: 3 meses; retenção de agendamento/consentimento/financeiro será política separada validada antes do lançamento. Consentimento transacional separado de marketing, com STOP. Analytics com consentimento; Meta Pixel preparado e desligado até campanhas.

## Stack e operação

- Frontend/painel: Next.js/TypeScript/Tailwind, Vercel.
- Backend: Python/FastAPI/Pydantic, SQLAlchemy/Alembic, uv, pytest/Ruff/mypy.
- API e worker: Railway; PostgreSQL Railway; Redis/Celery; worker no mesmo pacote backend.
- WhatsApp: Evolution QR/Baileys, número dedicado, alerta de desconexão e reconexão manual restrita. Adapter pronto para futura API oficial. Risco operacional do QR foi aceito; site deve seguir disponível nas quedas.
- IA: DeepSeek conversacional + Jev classificatório, adaptadores e fallback a selecionar.
- Google Calendar; storage de mídia desacoplado; desenvolvimento e produção separados.
- Domínio/contas pertencem à clínica; acesso individual, segredos protegidos, backups.
- Faixa-alvo mensal de infraestrutura R$100–300, **não validada como orçamento garantido**; custos de provedores e uso serão medidos antes de produção.

## Fases e entregáveis

0. Preparação: repositório separado, handoff vivo, instruções Claude, ambiente local, sessão Claude/Remote Control, contratos de integração e PoC Evolution quando houver instância de teste.
1. Fundação: backend/frontend, configurações, banco/migrações, filas, autenticação, CI e higiene de logs. Validar cada componente separadamente, sem fingir integração externa.
2. Agenda: catálogo, durações, Google Calendar, reserva, sinal, expiração, cancelamento/reagendamento, concorrência/idempotência e reconciliação.
3. Bot/WhatsApp: webhooks, estados, modo humano, links seguros, reconexão e contingência.
4. IA: conteúdo aprovado, adaptadores, privacidade, confiança, benchmark e fallback.
5. Experiência: landing completa, painel, chat, políticas/SEO/analytics e acessibilidade.
6. Piloto/lancamento: testes ponta a ponta, concorrência, quedas, backup/restauração, aprovação clínica, domínio e substituição gradual do Base44.

Estimativa de planejamento: 4–6 semanas, dependente de conteúdo/acessos e descoberta técnica; não prazo garantido. Base44 permanece até a solução nova ser validada. Redirecionamento do subdomínio Base44 depende dos recursos da plataforma/conta; se impossível, usar aviso/link e atualizar pontos de entrada.

## Dependências para produção

Logo/fotos/depoimentos autorizados; nomes completos/conselhos/especialidades; catálogo/preços/durações/sinais aprovados; preparação/cuidados; instruções Pix; contatos; calendários; e-mails autorizados; endereço/horários confirmados; contas de provedores/domínio/hospedagem. Não solicitar segredos por chat.

Gates: credenciais e conteúdo aprovados, políticas válidas, integrações reais testadas, modo humano confiável, idempotência/concorrência testadas, backups restaurados em teste, fluxo completo validado, responsividade/acessibilidade, autorização final de publicação.

Fora do MVP: pagamento automático, campanhas em massa, diagnóstico/triagem, consulta pelo bot, antes/depois, app móvel, CRM avançado e migração obrigatória imediata à API oficial.

## Itens do plano integral a não perder

Presentes em `PLANO-ORIGINAL.md` e ausentes ou só implícitos no resumo acima; cada um tem fase/tarefa dona.

- **Evento temporário no calendário** ao reservar (passo 9): o hold de 2h também cria evento provisório no Google Calendar, que vira confirmado após o sinal ou é removido na expiração. PostgreSQL continua sendo o estado transacional (ADR-003/008). → T08.
- **Fallback do modo humano**: se a PoC mostrar que a Evolution não distingue mensagem humana de automática com confiabilidade, criar mecanismo explícito de pausa operado pelo próprio WhatsApp (sem caixa no painel). → T09.
- **Restrições de comunicação** por procedimento (matriz, seção 9): campo próprio no conteúdo do serviço, uso interno (guardrails do bot e revisão de publicidade), sob a mesma aprovação. → T07b.
- **Publicidade de enfermagem**: identificação profissional obrigatória e nenhuma insinuação de resultado; bloqueador de lançamento e insumo da revisão de conteúdo. → T07b/T10.
- **Verificação de segredos no CI** (Fase 1). → pendente, ainda não implementada.
- **Critérios de lançamento adicionais**: Evolution monitorada, processo de reconexão documentado, contatos de Munique e Michele. → Fase 6.
- **Resumo da conversa e histórico de atendimento humano** como dados armazenados (seção 12), com minimização. → Fases 3–4.
- **Painel**: configuração de mensagens, recomendações e estado das integrações além do catálogo. → entregues por fase, junto com os respectivos backends.

## Referências consultadas no planejamento (revalidar antes de publicar)

- Cofen: https://www.cofen.gov.br/resolucao-cofen-no-05542017/
- Qualificação: https://www.cofen.gov.br/nota-de-esclarecimento-e-orientacao-sobre-a-atuacao-de-enfermeiros-na-area-de-estetica/
- Evolution: https://github.com/evolution-foundation/evolution-api
- DeepSeek: https://api-docs.deepseek.com/quick_start/pricing/
- Jev: https://api.typesafe.ai/docs

Links de fornecedores são pontos de verificação, não evidência de integração local funcionando.
