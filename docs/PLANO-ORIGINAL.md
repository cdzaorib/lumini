# Plano integral aprovado (texto do grill-me)

Registrado em 2026-10-01 a pedido do usuário: **“esse é o plano a ser feito, só o backend que troquei por python e fastapi”**.

Leitura obrigatória junto com `PLANO.md`:

- **Única substituição aprovada:** onde este texto diz Node.js/TypeScript/Fastify e BullMQ, vale **Python/FastAPI** com **Celery/Redis** (ADR-001). Todo o restante do escopo continua valendo.
- `PLANO.md` é o resumo operacional; `DECISOES.md` acrescenta detalhes técnicos conservadores. Eles refinam, mas **não reduzem** o escopo abaixo. Em dúvida, este texto prevalece quanto ao *que* entregar.
- O trecho “Nenhuma implementação foi iniciada” e o “Próximo passo” são históricos (o plano foi aprovado e a implementação começou).
- Itens deste texto ausentes do resumo estão listados em `PLANO.md`, seção “Itens do plano integral a não perder”.

---

Encerramos o `grill-me` com todas as recomendações 56–70 aprovadas. Este é o plano consolidado para sua revisão. Nenhuma implementação foi iniciada.

# Plano do projeto Lumini

## 1. Objetivo

Substituir completamente o site atual da Lumini por uma landing page premium, rápida e confiável, integrada a um bot capaz de:

- Responder dúvidas sobre procedimentos;
- Apresentar possibilidades de tratamento sem diagnosticar;
- Capturar e qualificar leads;
- Agendar avaliações e procedimentos;
- Reservar horários por duas horas;
- Cancelar e reagendar;
- Direcionar casos sensíveis para Munique ou Michele;
- Funcionar na landing page e no WhatsApp;
- Permitir atendimento humano pelo próprio WhatsApp.

O lançamento público acontecerá somente quando landing page, bot, calendários e fluxo de reserva estiverem funcionando juntos.

## 2. Stack recomendada

### Frontend

- Next.js com TypeScript;
- Tailwind CSS e componentes acessíveis;
- Landing page, chat e painel administrativo no mesmo projeto;
- Hospedagem inicial na Vercel;
- Domínio próprio quando for adquirido.

### Backend

- Node.js com TypeScript e Fastify; **→ substituído por Python/FastAPI (aprovado pelo usuário)**
- API e worker inicialmente no Railway;
- PostgreSQL no Railway;
- Redis para filas, reservas temporárias e lembretes;
- BullMQ ou equivalente para tarefas agendadas; **→ Celery (equivalente em Python)**
- Armazenamento de imagens aprovado e desacoplado do frontend.

### Integrações

- Google Calendar como fonte oficial da agenda;
- Evolution API por QR Code/Baileys no lançamento;
- Interface pronta para futura migração à API oficial do WhatsApp;
- DeepSeek para linguagem natural;
- Jev para decisões classificatórias restritas;
- Provedor de fallback selecionado depois de testes comparativos.

A lógica crítica ficará no código. Nenhum modelo poderá confirmar horários, mexer diretamente no calendário, validar pagamentos ou aplicar políticas sozinho.

## 3. Arquitetura funcional

```text
Landing page / WhatsApp
          ↓
      API do bot
          ↓
Regras determinísticas
  ├─ Agenda e disponibilidade
  ├─ Reserva de duas horas
  ├─ Cancelamento/reagendamento
  ├─ Consentimentos e privacidade
  └─ Escalonamento humano
          ↓
Camada de decisão
  ├─ Jev: intenção, serviço, profissional e risco
  └─ DeepSeek: conversa e explicações
          ↓
PostgreSQL + Redis + Google Calendar
```

O sistema terá adaptadores independentes para WhatsApp, modelos de IA, agenda e armazenamento. Isso permitirá trocar fornecedores sem reconstruir o produto.

## 4. Regras do bot

### O bot poderá

- Explicar o que é cada procedimento;
- Explicar objetivos comuns e para quem ele pode ser interessante;
- Apresentar procedimentos relacionados ao objetivo informado;
- Responder perguntas usando conteúdo previamente aprovado;
- Consultar horários;
- Criar uma reserva temporária;
- Cancelar ou reagendar dentro das regras;
- Enviar instruções aprovadas;
- Encaminhar a conversa para uma profissional.

### O bot não poderá

- Diagnosticar;
- Fazer triagem clínica;
- Afirmar que um tratamento é adequado para aquela pessoa;
- Prometer resultados;
- Interpretar uma condição de saúde;
- Substituir uma avaliação profissional;
- Criar orientações clínicas não aprovadas;
- Alterar regras, valores ou horários por decisão da IA.

Se a cliente mencionar condição de saúde, dúvida clínica ou baixa confiança na classificação, o bot interromperá o fluxo automatizado e oferecerá o contato apropriado.

## 5. Uso dos modelos

### Jev

Será limitado a decisões estruturadas:

- Identificar intenção;
- Identificar o serviço;
- Selecionar profissional conforme o catálogo;
- Detectar necessidade de esclarecimento;
- Detectar necessidade de atendimento humano;
- Aplicar guardrails.

Não será usado para definir indicação clínica.

### DeepSeek

Será usado para:

- Explicar procedimentos;
- Responder FAQs aprovadas;
- Fazer perguntas naturais;
- Reformular respostas;
- Explicar regras de agendamento.

Nome, telefone, condição de saúde e outros identificadores não serão enviados aos modelos. A IA receberá apenas o contexto mínimo e anonimizado.

### Fallback

DeepSeek e alternativas serão avaliados com conversas sintéticas. A seleção considerará:

- Qualidade em português;
- Seguimento de instruções;
- Uso correto de ferramentas;
- Latência;
- Custo;
- Taxa de respostas inseguras;
- Disponibilidade do provedor.

## 6. Fluxo de agendamento

1. Cliente escolhe um procedimento ou descreve seu objetivo.
2. Bot esclarece dúvidas usando conteúdo aprovado.
3. Sistema identifica o profissional responsável.
4. Bot pergunta se existe alguma condição que precise ser conversada com a profissional.
5. Havendo condição ou dúvida clínica, o fluxo é encaminhado para atendimento humano.
6. Não havendo, o sistema consulta o Google Calendar.
7. Cliente escolhe um horário.
8. Sistema faz nova validação para evitar conflito.
9. É criado um evento temporário no calendário.
10. Horário fica reservado por duas horas.
11. Bot envia instruções para o sinal.
12. A clínica confirma manualmente o pagamento.
13. Evento temporário torna-se confirmado.
14. Sem confirmação em duas horas, a reserva é removida e o horário volta a ficar disponível.

Uma trava por profissional e horário evitará que duas pessoas reservem simultaneamente o mesmo período.

## 7. Cancelamento e reagendamento

- Com mais de 24 horas: autoatendimento;
- Com menos de 24 horas: atendimento humano;
- Um reagendamento preserva o sinal;
- Segundo reagendamento, exceções e reembolsos: decisão humana;
- Acesso por link temporário seguro ou confirmação pelo mesmo WhatsApp;
- Toda modificação terá registro de auditoria.

## 8. Atendimento humano no WhatsApp

Quando uma profissional responder pelo WhatsApp:

- A conversa entra automaticamente em `human_mode`;
- O bot para de responder;
- Não haverá retomada automática;
- O comando `#bot` devolverá a conversa à automação;
- A equipe continuará usando o próprio WhatsApp, sem precisar assumir a conversa no painel.

Essa capacidade será validada logo no início com uma prova de conceito da Evolution API. Se a distinção entre mensagens humanas e automáticas não for confiável, criaremos um mecanismo explícito de pausa, mantendo a experiência no WhatsApp.

## 9. Catálogo e profissionais

Será criada uma matriz com uma linha para cada procedimento:

- Categoria;
- Nome;
- Descrição aprovada;
- Objetivos;
- Para quem pode ser interessante;
- Profissional responsável;
- Credencial correspondente;
- Duração;
- Intervalo de 15 minutos;
- Agendamento direto ou avaliação;
- Preço ou “a partir de”;
- Valor do sinal;
- Preparação;
- Recomendações posteriores;
- Restrições de comunicação;
- Status: rascunho, aprovado ou publicado.

Procedimentos sem responsável, credencial ou conteúdo aprovado não serão publicados.

Publicidade de enfermagem exige identificação profissional e não pode insinuar resultado garantido. Essas regras serão tratadas como bloqueadores de lançamento. [Resolução Cofen 554/2017](https://www.cofen.gov.br/resolucao-cofen-no-05542017/) A habilitação de cada procedimento também será validada antes da publicação. [Orientação do Cofen sobre enfermagem estética](https://www.cofen.gov.br/nota-de-esclarecimento-e-orientacao-sobre-a-atuacao-de-enfermeiros-na-area-de-estetica/)

## 10. Landing page

Estrutura definida:

1. Hero com “Tire suas dúvidas e agende sua avaliação”;
2. Categorias e objetivos;
3. Procedimentos em destaque;
4. Como funciona o atendimento;
5. Perfis e credenciais de Munique e Michele;
6. Diferenciais da clínica;
7. Perguntas frequentes;
8. Políticas de agendamento;
9. Localização e horários;
10. CTA final;
11. Privacidade, termos e contatos.

Também teremos:

- Widget de chat;
- Botão para WhatsApp;
- Página dedicada de atendimento;
- SEO para Mangaratiba e Costa Verde/RJ;
- Fotos reais e autorizadas;
- Depoimentos somente com autorização;
- Sem antes/depois na primeira versão;
- Preço ou “a partir de” nos serviços padronizados;
- Valor após avaliação nos procedimentos variáveis.

## 11. Painel administrativo

O painel terá acesso por Google, restrito a e-mails autorizados.

Funções previstas:

- Dashboard de leads e agendamentos;
- Visualização de reservas temporárias;
- Confirmação manual de sinal;
- Cadastro de procedimentos e valores;
- Definição de duração e intervalo;
- Definição de agendamento direto ou avaliação;
- Associação entre serviço e profissional;
- Publicação e aprovação de conteúdo;
- Configuração de recomendações;
- Acompanhamento de cancelamentos e reagendamentos;
- Histórico de mudanças;
- Métricas e conversões;
- Configuração das mensagens;
- Estado das integrações.

O painel não terá uma caixa própria para assumir conversas.

## 12. Dados e privacidade

Serão armazenados principalmente:

- Dados estruturados do lead;
- Consentimentos;
- Resumo da conversa;
- Interesse e procedimento;
- Preferência de horário;
- Reserva e agendamento;
- Estado do sinal;
- Histórico de eventos e atendimento humano.

Não manteremos uma cópia indiscriminada de toda a conversa.

Retenção:

- Lead não convertido: três meses;
- Agendamentos, consentimentos e registros financeiros: política separada;
- Marketing: consentimento independente;
- Descadastro por `STOP` ou equivalente;
- Analytics somente após consentimento;
- Meta Pixel preparado, mas desativado até o início das campanhas.

## 13. Notificações

Mensagens automáticas previstas:

- Reserva criada;
- Instruções do sinal;
- Lembrete antes da expiração;
- Horário confirmado;
- Reserva expirada;
- Lembrete de 24 horas;
- Lembrete de duas horas;
- Recomendações aprovadas;
- Link para cancelar ou reagendar;
- Encaminhamento para atendimento humano.

## 14. Fases de execução

### Fase 0 — Preparação

- Abrir o projeto em sessão separada;
- Conectar Claude e validar o controle remoto;
- Criar pasta e repositório exclusivos para a Lumini;
- Criar documentação das decisões;
- Preparar ambientes de desenvolvimento e produção;
- Definir contratos das integrações;
- Fazer a prova de conceito da Evolution API.

### Fase 1 — Fundação

- Estrutura Next.js/TypeScript;
- API Fastify; **→ API FastAPI**
- PostgreSQL e migrações;
- Redis e filas;
- Autenticação Google;
- Modelo de permissões;
- CI, testes, logs seguros e verificação de segredos.

### Fase 2 — Agenda

- Catálogo e profissionais;
- Integração com dois calendários;
- Consulta de disponibilidade;
- Durações e intervalos;
- Reservas por duas horas;
- Confirmação de sinal;
- Cancelamento e reagendamento;
- Trabalhador de expiração e lembretes.

### Fase 3 — WhatsApp e bot

- Evolution API;
- Webhooks idempotentes;
- Máquina de estados;
- Modo humano;
- Comando `#bot`;
- Links temporários;
- Recuperação após desconexão;
- Alerta para novo QR Code.

### Fase 4 — Inteligência

- Base de conteúdo aprovada;
- Redação das respostas;
- Classificação com Jev;
- Conversação com DeepSeek;
- Redação/remoção de dados identificáveis;
- Avaliação de confiança;
- Benchmark do fallback;
- Testes sintéticos de segurança.

### Fase 5 — Landing page e painel

- Identidade visual premium e acolhedora;
- Estrutura completa da landing;
- Catálogo;
- Widget;
- Painel administrativo;
- Conteúdo, políticas e consentimentos;
- SEO local;
- Analytics condicionado ao consentimento.

### Fase 6 — Validação e lançamento

- Testes de ponta a ponta;
- Testes mobile e acessibilidade;
- Testes de concorrência de agenda;
- Simulação de expiração;
- Simulação de queda do WhatsApp;
- Backup e restauração;
- Piloto interno;
- Aprovação da clínica;
- Configuração do domínio;
- Substituição do Base44.

Estimativa: quatro a seis semanas, desde que materiais, credenciais e conteúdo sejam entregues sem bloqueios.

## 15. Critérios para lançamento

O lançamento ficará bloqueado até termos:

- Credenciais profissionais verificadas;
- Matriz de procedimentos aprovada;
- Calendários conectados;
- Valores e sinais definidos;
- Conteúdo clínico aprovado;
- Contatos de Munique e Michele;
- Política de privacidade e consentimentos;
- Evolution monitorada;
- Processo de reconexão documentado;
- Backups funcionando;
- Testes de agendamento, cancelamento e reagendamento aprovados;
- Testes mobile, acessibilidade e desempenho aprovados;
- Aprovação final da clínica.

## 16. Materiais que serão necessários durante o projeto

- Logo e identidade visual;
- Fotos autorizadas;
- Nome completo e credenciais das profissionais;
- Relação final de procedimentos;
- Duração, valor e sinal de cada serviço;
- Preparação e recomendações;
- Chave Pix e texto de pagamento;
- Contatos profissionais;
- Contas do Google Calendar;
- E-mails autorizados no painel;
- Horários e endereço confirmados;
- Acesso à hospedagem e ao domínio quando chegar a fase correspondente.

## 17. Fora da primeira versão

- Pagamento automático;
- Campanhas em massa;
- Diagnóstico ou triagem clínica;
- Consulta profissional pelo bot;
- Antes/depois;
- Aplicativo móvel;
- Integração imediata com a API oficial da Meta;
- Funcionalidades complexas de CRM.

## Próximo passo (histórico)

Se o plano estiver correto, responda apenas **“Aprovo o plano”**. A partir daí começaremos pela Fase 0, em uma sessão e repositório separados, sem mexer no projeto Tecnoarte.
