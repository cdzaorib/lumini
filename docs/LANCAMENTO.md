# Checklist de lançamento (plano §15 e gates do `PLANO.md`)

Estado em 2026-10-05, ao fim da T10. Legenda: **Pronto (local)** = implementado e testado localmente com dados sintéticos; **Preparado** = construído, sem validação com o serviço real; **Pendente** = depende da clínica, de credenciais ou de autorização. Nenhum item “Pendente” pode ser marcado sem evidência.

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
| Testes de agendamento, cancelamento e reagendamento | Pronto (local) | Integrações e E2E (`VALIDACAO-003/005/006`); aprovação da clínica no piloto pendente |
| Concorrência e idempotência | Pronto (local) | Restrição de exclusão, repetição em deadlock, 20 rodadas (`VALIDACAO-005`) |
| Simulação de expiração e de queda do WhatsApp | Pronto (local) | Testes de expiração, reenvio após queda, fila de avisos |
| Mobile e acessibilidade | Pronto (local) / Pendente | 390 px, teclado, foco, rótulos e CSP nos E2E; falta revisão com leitor de tela e auditoria completa |
| Desempenho | Pendente | Medir no ambiente de produção (Core Web Vitals) |
| Login Google real no painel | Pendente | Client ID OAuth da clínica |
| IA (DeepSeek/Jev) | Preparado, desligado | Ligar só após a bancada sintética com o provedor escolhido aprovar minimização (ADR-018); Jev sem adaptador até a API ser verificada |
| Textos do bot e dados do sinal (Pix) | Pendente | Aprovar `backend/src/lumini/whatsapp/texts.py`; instruções reais do sinal |
| Decisões de produto abertas | Pendente | Antecedência mínima de 3 h; sinal zero com confirmação humana; lembretes em modo humano; alerta de compromisso de terceiros sobre reserva confirmada |
| Conteúdo da landing | Pendente | Endereço, horários, WhatsApp, diferenciais, perguntas frequentes, fotos e depoimentos autorizados (`frontend/src/content/site.ts`) |
| Domínio, HTTPS e deploy (Vercel/Railway) | Pendente | Autorização específica do usuário; variáveis no gerenciador de segredos |
| CI remoto | Preparado | Workflow com testes e gitleaks; sem remoto Git |
| Piloto interno | Pendente | Após integrações reais: equipe usa o fluxo completo com clientes de teste |
| Aprovação final e substituição do Base44 | Pendente | `LUMINI_SITE_PUBLIC=true` e `LUMINI_SITE_STAGE=production` só após todos os itens acima |
