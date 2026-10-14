# Checklist de lançamento (plano §15 e gates do `PLANO.md`)

Estado atualizado em 2026-10-14, retomada T12/T13. GitHub/CI e frontend protegido reais; aplicação completa ainda não publicada. Legenda: **Pronto (local)** = implementado e testado localmente com dados sintéticos; **Preparado** = construído, sem validação com o serviço real; **Pendente** = depende da clínica, de credenciais ou de acesso. Tarefas exatas em `PENDENCIAS.md`. Nenhum item “Pendente” pode ser marcado sem evidência.

| Critério | Estado | O que falta / evidência |
|---|---|---|
| Credenciais profissionais verificadas | Pronto (local) / Pendente | Verificação humana no painel (`VALIDACAO-002`); faltam nomes completos, conselhos e documentos de Munique e Michele |
| Matriz de procedimentos aprovada | Pronto (local) / Pendente | Fluxo rascunho → aprovação por profissional → publicação; falta a matriz real (~35 procedimentos) |
| Valores e sinais definidos | Pendente | Cadastro no painel pela clínica; preço só aparece conforme regra |
| Conteúdo clínico aprovado | Pendente | Cada profissional aprova o conteúdo da sua área no painel |
| Calendários conectados | Preparado | Adaptador Google e reconciliação (`VALIDACAO-004`); falta conta de serviço, compartilhamento dos calendários e teste real |
| Contatos de Munique e Michele | Pendente | Telefones/WhatsApp e e-mails Gmail/Workspace da allowlist |
| Política de privacidade e consentimentos | Preparado | Consentimentos implementados (contato obrigatório, marketing separado, STOP); páginas em **rascunho**, falta revisão jurídica e aprovação (`LEGAL_APPROVED`) |
| Retenção de dados | Pronto (local) / Pendente | Leads 3 meses e sessões de chat 1 dia automáticos; política de agendamentos/financeiro/consentimentos a aprovar |
| Evolution monitorada | Preparado | Estado da conexão e aviso no painel (`VALIDACAO-006`); falta instância e PoC real (`RUNBOOK-WHATSAPP.md`) |
| Modo humano confiável | Preparado | Distinção por id do envio + `#bot`/`#pausa`; PoC real obrigatória antes do número oficial |
| Processo de reconexão documentado | Pronto (documento) | `RUNBOOK-WHATSAPP.md`; ensaio real pendente |
| Backups funcionando | Pronto (local) / Pendente | Scripts e ensaio (`VALIDACAO-007`); falta backup automático do provedor e armazenamento criptografado em produção |
| Testes de agendamento, cancelamento e reagendamento | Pronto (local) | Integrações e `make e2e` versionado (7 cenários); aprovação da clínica no piloto pendente |
| Concorrência e idempotência | Pronto (local) | Restrição de exclusão, repetição em deadlock, 20 rodadas (`VALIDACAO-005`) |
| Simulação de expiração e de queda do WhatsApp | Pronto (local) | Testes de expiração, reenvio após queda, fila de avisos |
| Mobile e acessibilidade | Pronto (local) / Pendente | 390 px, teclado, foco, rótulos e CSP em `make e2e`; revisão pelas Web Interface Guidelines aplicada (`VALIDACAO-008`); falta teste com leitor de tela |
| Desempenho | Pendente | Medir no ambiente de produção (Core Web Vitals) |
| Login Google real no painel | Pendente | Client ID OAuth da clínica |
| IA (DeepSeek/Jev) | Pronto (local) / desligado | Jev específico e redator separados; bancada classificador/redator/fallback/custo disponível (ADR-021). Nenhuma chamada autenticada/modelo/fallback real validado; ligar só após bancada real e revisão da minimização |
| Textos do bot e dados do sinal (Pix) | Pronto (local) / Pendente | Painel edita12 textos operacionais e Pix sob revisão global; regras/saúde/STOP/reserva em processamento permanecem fixos. Aprovação real da clínica pendente |
| Decisões de produto abertas | Pendente | Antecedência mínima de 3 h; sinal zero com confirmação humana; lembretes em modo humano; conduta além do aviso quando há compromisso de terceiros sobre reserva (hoje só avisa no painel) |
| Conteúdo da landing | Pronto (local) / Pendente | Aba Site inclui fotos externas autorizadas/origens explícitas e mensagens; salva rascunho, revisão por todas as profissionais verificadas, publicação explícita e revogação real. Materiais/autorizações/storage da clínica pendentes |
| Analytics | Pronto (local) / desligado | Consentimento/recusa/revogação, medição mínima só na landing; nenhum fornecedor real configurado. Meta Pixel somente configuração preparada, sem runtime, aguardando campanha/consentimento separado |
| Domínio, HTTPS e deploy (Vercel/Supabase/Railway) | Frontend real protegido / resto bloqueado | GitHub público e frontend Vercel READY; sem API/banco/worker/Redis reais. Railway desconectado, organização/custo Supabase e variáveis reais pendentes. Indexação fechada |
| CI remoto | Real | GitHub Actions baseline 7fddf38 passou secrets/backend/frontend; resultado do commit final registrado em HANDOFF/TAREFAS |
| Métricas e comparecimento | Pronto (local) | Aba Resumo, marcação de comparecimento/falta, histórico de cada reserva (`VALIDACAO-008`) |
| Segurança | Pronto (local) / Pendente | `SEGURANCA.md`, teste de rotas; revisão independente sobre o ambiente publicado pendente |
| Piloto interno | Pendente | Após integrações reais: equipe usa o fluxo completo com clientes de teste |
| Aprovação final e substituição do Base44 | Pendente | `LUMINI_SITE_PUBLIC=true` e `LUMINI_SITE_STAGE=production` só após todos os itens acima |

## Auditoria do objetivo integral — T14b

O plano não é concluído por testes sintéticos ou por frontend protegido. Jev/DeepSeek/fallback e analytics são entregas aprovadas; consentimento facultativo da cliente não torna analytics uma feature dispensada. IA desligada é gate provisório de minimização/benchmark.

| Requisito do plano integral | Evidência que provaria conclusão | Estado atual |
|---|---|---|
| §§2/14: FastAPI, worker, PostgreSQL e Redis de produção | Serviços Lumini exclusivos saudáveis, banco migrado, fila/beat reais e fluxo frontend→API→banco/worker | Frontend/GitHub reais; backend e infraestrutura remota ausentes |
| §§6/7/14: dois calendários, reserva 2h, sinal humano, alteração e reconciliação | Ensaio sintético controlado nos calendários reais das duas profissionais, concorrência/idempotência e reparo de mudanças | Código/testes locais; contas/calendários reais ausentes |
| §§8/14: Evolution e atendimento humano confiável | PoC de número de teste, eco/manual/reentrega, pausa e #bot autorizado, queda/reconexão | Simulado; instância/número/credenciais ausentes |
| §§5/14: Jev, DeepSeek, privacidade, confiança e fallback | Modelos autenticados verificados, benchmark comparativo sintético com qualidade/segurança/latência/custo, minimização validada e fallback escolhido | Adaptadores/bancada; integração/benchmark reais não executados |
| §§10/12/14: analytics após consentimento | Conta/domínio da clínica, evento controlado no fornecedor depois do aceite, nenhuma chamada sem aceite/recusa/revogação ou em páginas sensíveis | Cliente/interceptação local; fornecedor real não configurado |
| §§9/10/16: conteúdo, profissionais, valores, mídia | Credenciais verificadas e matriz/conteúdo/material aprovado pelas profissionais no painel, storage real e autorizações | Ferramentas locais; insumos/revisão clínica reais ausentes |
| §§12/15: políticas e retenção | Política aprovada, retenções distintas e consentimentos revisados, sem transcrição indiscriminada | Mecanismos locais; política clínica/jurídica pendente |
| §§14/15: backup, acessibilidade/desempenho, piloto e aprovação final | Backup remoto restaurado em destino separado; revisão publicada/leitor de tela/métricas; piloto das profissionais e aprovação registrada | Ensaio/testes locais; verificações remotas/humanas pendentes |
| §§1/14/15: lançamento conjunto e Base44 | Fluxo completo real, domínio/origens válidas, conteúdo e gates aprovados, troca de entrada verificada | Frontend protegido parcial; Base44 preservado |

Nenhum requisito remoto/humano acima é marcado concluído. Não criar novos projetos ou ampliar escopo apenas para simular movimento diante dos acessos pendentes.
