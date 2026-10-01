import Link from "next/link";

export default function NotFound() {
  return (
    <main id="conteudo" className="not-found" tabIndex={-1}>
      <p className="eyebrow">Lumini · prévia interna</p>
      <h1>Página não encontrada.</h1>
      <p>Este endereço não está disponível na prévia.</p>
      <Link className="site-link" href="/">Voltar ao início</Link>
    </main>
  );
}
