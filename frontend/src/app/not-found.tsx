import Link from "next/link";

export default function NotFound() {
  return (
    <main id="conteudo" className="not-found" tabIndex={-1}>
      <p className="eyebrow">Lumini Estética e Saúde</p>
      <h1>Página não encontrada.</h1>
      <p>Este endereço não existe ou o conteúdo foi retirado.</p>
      <Link className="site-link" href="/">Voltar ao início</Link>
    </main>
  );
}
