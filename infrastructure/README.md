# Infraestrutura — preparação, sem implantação

Alvos aprovados: Vercel (frontend), Railway (API/worker/Evolution/PostgreSQL/Redis), Google Calendar e storage desacoplado. Nenhum projeto de nuvem foi criado neste marco.

Antes do deploy:

1. Medir custo mínimo da topologia e definir ambientes separados.
2. Escolher e testar imagem/release da Evolution em instância de teste dedicada.
3. Configurar segredos em armazenamento do provedor, sem `.env` versionado ou credenciais de outros projetos.
4. Verificar PostgreSQL/Redis reais e aplicar migrações em banco de teste.
5. Implementar autorização, idempotência, outbox/reconciliação e backups antes de aceitar reservas reais.
6. Validar restauração, disponibilidade e pausa humana.

O Dockerfile do backend (quando presente) é receita de build; só considerar validado após construir e iniciar uma imagem. Docker ausente na máquina inicial. CI localmente preparado não significa execução remota aprovada.

Não incluir Evolution em um compose até verificar versão, requisitos e configuração oficial. Não herdar uma instância WhatsApp de outro projeto.
