# Superfície de ataque e controles

Para quem revisa o sistema antes do lançamento. Estado em 2026-10-05; o teste `backend/tests/test_route_guards.py` falha se surgir rota pública nova ou rota administrativa sem login.

## Rotas públicas (sem login)

| Rota | Proteções |
|---|---|
| `GET /health/live`, `/health/ready` | Sem dados; estado das dependências sem detalhes |
| `GET /api/catalog/services` | Só conteúdo publicado e aprovado; sem restrições internas nem dados de revisão |
| `GET /api/public/site` | Sem instruções do sinal e sem registros de autorização de depoimentos |
| `POST /api/public/leads` | Sem texto livre, consentimento obrigatório, armadilha de robô, limite por endereço, 422 sem eco |
| `POST /api/public/chat/session` e `/messages` | Token aleatório (só o hash no banco), recusa antes do banco, limites por endereço e sessão, nada do texto gravado, expira em 24 h |
| `GET/POST /api/public/booking*` | Link HMAC com validade, erros indistinguíveis, recusa antes do banco, limite por link, regras do ator `client` |
| `POST /api/webhooks/evolution` | Token em cabeçalho (comparação em tempo constante) antes de qualquer dependência, instância conferida, corpo ≤ 1 MB, `key.id` registrado uma vez |

## Painel (`/api/admin/*`)

Google ID token verificado (assinatura, audiência, emissor, validade, e-mail verificado, Gmail/Workspace) e allowlist a cada requisição; autenticação antes de abrir sessão de banco. Aprovação de conteúdo restrita à profissional atribuída. Versões otimistas em toda ação. Contato de clientes só aqui.

## Frontend

CSP por nonce em todas as páginas (`script-src 'nonce' 'strict-dynamic'`, `connect-src` só a API, `frame-ancestors 'none'`, `base-uri 'none'`), `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy` (`no-referrer` no painel e na reserva), `Permissions-Policy`, `noindex` até o lançamento. Token do Google e token do link só em memória; token do link no fragmento da URL. Requisições com `credentials: "omit"` e `redirect: "error"`; o painel só chama caminhos de uma lista fixa.

## Dados e segredos

Segredos só por variáveis de ambiente (`SecretStr`, nunca em `repr`/erros); validação de chaves (conta de serviço com `token_uri` do Google, segredos com tamanho mínimo). Logs sem telefone, nome, texto de mensagens, tokens ou ids de conversa (testado). Modelos de IA desligados por padrão; quando ligados, recebem só texto redigido (ADR-018). Evento no Google sem dados da cliente. Retenção automática: leads 90 dias, sessões de chat 1 dia, texto de cliente apagado após leitura. Backup com checksum e permissões restritas. Varredura de segredos (gitleaks) no histórico.

## Pendências antes do lançamento

Revisão independente (`security-review`) sobre o ambiente publicado; configuração de HTTPS, CORS e proxies reais (o limite por endereço depende do IP visto atrás do proxy da plataforma); política de rotação de segredos; backups criptografados do provedor; teste de restauração em produção; monitoramento de erros sem dados pessoais.
