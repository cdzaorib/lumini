# Lumini — instruções para qualquer agente

## Antes de começar

Leia `docs/HANDOFF.md`, `docs/PLANO.md` e `docs/DECISOES.md`. Inspecione o Git e os processos antes de assumir trabalho iniciado por outro agente. Este projeto é independente do Tecnoarte; não reutilize dados, segredos, configurações ou infraestrutura daquele projeto.

## Continuidade obrigatória

O usuário pediu handoff atualizado **a cada tarefa concluída ou bloqueada**. Antes de considerar uma tarefa encerrada:

1. Registre a mudança, arquivos e evidência de validação em `docs/TAREFAS.md`.
2. Atualize `docs/HANDOFF.md` com estado atual, limitações, processos ativos e próximo passo executável.
3. Atualize `docs/DECISOES.md` se houver uma decisão técnica nova. Não reabra as decisões de produto já aprovadas sem causa concreta.
4. Diferencie **real local**, **mock**, **apenas preparado** e **não iniciado**. Um build ou teste com fake não valida um fornecedor real.
5. Em trabalho paralelo, cada agente produz seu relatório de tarefa; o coordenador atualiza o handoff para evitar edições concorrentes.

## Regras do produto

- Backend Python/FastAPI; frontend Next.js/TypeScript; PostgreSQL no Railway; Celery/Redis. O worker compartilha o pacote Python do backend.
- Regras de horário, reserva, sinal e cancelamento são determinísticas. LLMs não têm acesso direto ao banco nem ao calendário.
- Todo horário exige revalidação, controle de concorrência e idempotência. Reserva de 2h e intervalo de 15min. Google Calendar é referência de disponibilidade; PostgreSQL mantém estado transacional de reservas e operações pendentes.
- Não considere uma trava Redis suficiente para integridade. Não declare atomicidade distribuída entre Postgres e Google Calendar; implemente reconciliação e falha conservadora.
- Bot informa e apresenta possibilidades; não diagnostica, não faz triagem clínica nem garante resultados. Condição de saúde/dúvida clínica deve ir à profissional, sem interpretação pelo modelo.
- Dados identificáveis e informações de saúde não vão para modelos. Testes usam dados sintéticos. Não registrar corpo de mensagens, prompts, telefones, tokens, URLs com segredos ou conteúdo clínico em logs.
- Conteúdo só fica público após revisão e credenciais verificadas. Não inventar preços, credenciais, fotos, avaliações ou telefone.
- Assumir conversa humana pausa o bot até comando `#bot` **de remetente autorizado**. O cliente não pode reativar o bot durante atendimento humano.
- Autorização de administradores ocorre no backend; esconder botão não protege endpoint.
- Nunca confirmar sinal automaticamente, por comprovante ou mensagem de cliente. Confirmação é humana e autenticada.

## Operação

- Nunca colocar segredos em Git ou compartilhar em chat/logs. Não criar `.env` contendo segredos; usar gerenciador de segredos ou ambiente de processo. Exemplos devem conter apenas placeholders.
- Não fazer push, deploy, migração em produção ou compra de serviços sem autorização específica. Desenvolvimento local e testes sintéticos estão aprovados.
- Antes de commit local: revisar diff, conferir arquivos ignorados/segredos e executar os checks relevantes. Staging explícito por caminho, nunca `git add .`/`-A`.
- Não iniciar dois agentes gravando nos mesmos arquivos. Claude fica aguardando o usuário enquanto Codex estiver implementando.
- Para continuidade no PyCharm: abrir a raiz ou `backend/` e selecionar `backend/.venv/bin/python`.

## Qualidade

Backend: Ruff, mypy e pytest. Frontend: ESLint, TypeScript e build. Dependências com lockfiles. Testes de regras críticas devem cobrir bordas de horário, concorrência e duplicação. Registrar checks que não puderam rodar, sem apresentar como sucesso.
