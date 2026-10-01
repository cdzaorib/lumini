# T03 — Fundação do frontend

Data: 2026-10-01. Escopo exclusivo de `frontend/`; integração no handoff geral pelo coordenador.

## Resultado e status

**Real local:** app Next.js executável com App Router, TypeScript estrito, Tailwind, página de preparação Lumini, 404 própria e `robots.txt`. A página explicita “Prévia interna” e que agendamentos/atendimento não estão disponíveis. Seu único CTA externo aponta para o site Base44 informado pelo usuário.

**Não iniciado nesta tarefa:** catálogo publicado, landing completa, bot/chat, agenda, painel, login, chamadas ao backend, analytics, pixels, imagens clínicas e implantação. Não há controles simulando funcionalidades futuras.

## Arquivos

- `package.json` e `package-lock.json`: dependências pinadas e instalação reproduzível via npm.
- `tsconfig.json`, `eslint.config.mjs`, `postcss.config.mjs`, `next.config.ts`: ferramentas, tipos estritos e headers.
- `src/app/layout.tsx`: idioma pt-BR, título de prévia, metadados noindex/nofollow e link de pular conteúdo.
- `src/app/page.tsx` e `globals.css`: prévia responsiva, link real ao site atual, foco visível e redução de movimento.
- `src/app/robots.ts`: bloqueio de rastreamento da prévia.
- `src/app/not-found.tsx`: 404 com retorno funcional para `/`.
- `README.md` e `.gitignore`: instruções locais e exclusão do arquivo gerado `next-env.d.ts`.

## Versões verificadas

Registry consultado em 2026-10-01. Runtime de validação: Node **22.23.2**.

| Componente | Versão |
|---|---|
| Next.js / eslint-config-next | 16.3.8 |
| React / React DOM | 19.3.0 |
| Tailwind / PostCSS adapter | 4.3.3 |
| TypeScript | 6.0.3 |
| ESLint | 9.39.5 |
| @types/node | 22.20.4 |
| @types/react / @types/react-dom | 19.3.0 |

**Pendência de tooling:** os releases latest consultados eram ESLint 10.11.0 e TypeScript 7.0.2. Os peers de `eslint-plugin-react`/`eslint-plugin-jsx-a11y` ainda limitam ESLint a 9, e `typescript-eslint` limita TypeScript a `<6.1.0`. Foram escolhidas as últimas versões compatíveis, sem `--force`/`--legacy-peer-deps`. O registry marca ESLint 9.39.5 como sem suporte; acompanhar a atualização dos plugins e migrar para ESLint 10 assim que possível. `npm ci` emite esse aviso de depreciação. O lint local passa sem warnings de código.

## Direção visual

Público e tarefa da página: revisão interna da nova identidade digital da clínica. Paleta: papel rosa `#f5edef`, tinta `#422c36`, rosa profundo `#704956`, texto secundário `#725d66`, dourado `#a18454` e branco rosado `#fffafa`. Serif de sistema para marca/títulos e sans de sistema para leitura/controles, sem tráfego para fontes externas nem dependência de rede no build.

O elemento de destaque é um estudo abstrato de luz em uma abertura arqueada, feito em CSS. Ele não é fotografia da clínica, não representa um procedimento nem substitui o logo autorizado. O restante mantém espaçamento e tipografia contidos. O dourado é decorativo; texto usa os tons escuros. Mobile empilha o conteúdo sem esconder mensagens de status.

## Evidências de validação

- `npm ci --no-fund`: sucesso; 373 pacotes auditados, **0 vulnerabilidades reportadas naquele momento**. Aviso de ESLint descrito acima.
- `npm run lint`: sucesso, zero warnings.
- `NEXT_TELEMETRY_DISABLED=1 npm run typecheck`: sucesso, geração de tipos + `tsc --noEmit`.
- `NEXT_TELEMETRY_DISABLED=1 npm run build`: sucesso; rotas `/`, `/_not-found`, `/robots.txt` pré-renderizadas.
- `next.config.ts` fixa `turbopack.root` na pasta frontend para não usar um lockfile fora do repositório.
- Smoke HTTP do build em `127.0.0.1:3113`: `/` retorna 200; rota inexistente retorna 404; `robots.txt` retorna `User-Agent: *` e `Disallow: /`.
- Headers observados no HTTP: `nosniff`, `X-Frame-Options: DENY`, `strict-origin-when-cross-origin`, câmera/microfone/geolocalização desativados, `X-Robots-Tag: noindex, nofollow, noarchive`; sem `X-Powered-By`.
- Não foram adicionados testes unitários que apenas repitam o HTML estático. Verificação visual em navegador será registrada pelo coordenador; não está comprovada por este relatório.

## Limitações e continuidade

- `noindex`/`robots.txt` não são autenticação nem tornam uma URL privada. O servidor escuta loopback por padrão; nenhuma implantação foi feita.
- Headers básicos não representam auditoria completa; CSP e política HTTPS precisam acompanhar o desenho de autenticação e integrações na fase correspondente.
- Sem proxy de health: a prévia não depende do backend. Introduzir contratos de API quando houver o primeiro consumidor real, sem publicar status interno na landing.
- Sem política legal inventada nem informações clínicas, credenciais, preços, telefones, avaliações ou fotos não aprovadas.
- Antes de publicar: seguir os gates do plano, revisar conteúdo/identidade e só então mudar explicitamente as diretivas de indexação.
- Processo temporário do smoke em `127.0.0.1:3113`, sessão `26228`, encerrado após a validação. O coordenador mantém sua própria sessão de revisão na porta 3000; estado final desse processo pertence ao handoff geral.

Referências técnicas consultadas: [instalação Next.js](https://nextjs.org/docs/app/getting-started/installation), [headers Next.js](https://nextjs.org/docs/app/api-reference/config/next-config-js/headers), metadados npm dos pacotes e peers.
