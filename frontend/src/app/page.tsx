export default function HomePage() {
  return (
    <div className="preview-shell">
      <header className="site-header">
        <div className="brand">
          <span className="brand-name">lumini</span>
          <span className="brand-description">Estética e Saúde</span>
        </div>
        <p className="preview-label">Prévia interna</p>
      </header>

      <main id="conteudo" className="preparation" tabIndex={-1}>
        <div className="preparation-copy">
          <p className="eyebrow">Um novo capítulo da Lumini</p>
          <h1>Estamos preparando um novo espaço para cuidar de você.</h1>
          <p className="description">
            Nossa nova experiência digital está em construção.
            Enquanto isso, você pode visitar o site atual da clínica.
          </p>
          <a className="site-link" href="https://lumini-contato.base44.app/">
            Visitar site atual
            <span aria-hidden="true">↗</span>
          </a>
        </div>

        <div className="light-study" aria-hidden="true">
          <div className="light-outline" />
          <div className="light-doorway" />
          <span className="light-caption">lumini</span>
        </div>
      </main>

      <footer className="site-footer">
        <p>Em desenvolvimento</p>
        <p>Agendamentos e atendimento ainda não estão disponíveis nesta prévia.</p>
      </footer>
    </div>
  );
}
