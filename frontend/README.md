# Frontend Lumini

Fundação **real local** em Next.js App Router, TypeScript e Tailwind. A rota `/` é uma prévia interna de preparação, sem catálogo, chatbot, agendamento, login ou integração com backend. O link para o site atual é real; não existe captação de dados nesta etapa.

## Executar

Use Node 22.23.2 ou uma versão posterior da linha 22 e npm. Na pasta `frontend/`:

```bash
npm ci
npm run dev
```

A prévia abre em `http://127.0.0.1:3000`. O servidor escuta apenas loopback por padrão.

```bash
npm run lint
npm run typecheck
npm run build
npm start
```

`npm start` serve o build local; não publica nada. O script `typecheck` gera os tipos de rotas antes de executar o TypeScript para funcionar também em um checkout limpo.

## Decisões desta fundação

- Server Components por padrão; esta página não precisa de estado ou código interativo próprio no cliente.
- Tipografia de sistema, sem chamadas externas ou download de fontes durante o build.
- Layout rosa suave, vinho e detalhe dourado; o painel abstrato em CSS não representa uma foto da clínica nem um logo aprovado.
- A prévia não deve ser indexada: metadados, `robots.txt` e cabeçalho `X-Robots-Tag`. Essas diretivas não substituem controle de acesso e não tornam uma implantação privada.
- Sem analytics, pixels, cookies próprios ou segredos.
- Headers básicos contra MIME sniffing e enquadramento, política de referrer e permissões de câmera/microfone/localização desativadas.
- Um proxy de backend será criado quando existir uma necessidade real. Esta página não deve depender da API para renderizar.

Consulte `../docs/HANDOFF.md` antes de continuar. Antes do lançamento, o conteúdo e visual completo passarão por aprovação; a alteração das diretivas de indexação deve ser explícita e acompanhada dos controles de publicação.
