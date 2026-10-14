import type { Metadata } from "next";
import { headers } from "next/headers";

import { site } from "@/content/site";
import { getSiteContent } from "@/lib/public/site";

import { LEGAL_APPROVED, LegalPage } from "../_site/legal";

export const metadata: Metadata = {
  title: `Privacidade — ${site.name}`,
  robots: LEGAL_APPROVED ? undefined : { index: false, follow: false },
};

export default async function PrivacyPage() {
  await headers();
  const content = await getSiteContent();
  return (
    <LegalPage content={content} title="Política de privacidade">
      <p>
        Esta política explica como a {site.name} trata dados pessoais no site, no atendimento pelo WhatsApp e nos
        agendamentos, conforme a Lei Geral de Proteção de Dados (Lei 13.709/2018).
      </p>
      <h2>Quais dados usamos</h2>
      <ul>
        <li>Pedido de contato: nome, WhatsApp, cidade ou bairro (opcional), procedimento de interesse, período preferido e suas autorizações.</li>
        <li>Agendamento: nome, telefone, procedimento, profissional, horário e situação do sinal.</li>
        <li>WhatsApp: dados da conversa necessários para responder; o texto das mensagens é apagado dos nossos sistemas depois de lido pelo atendimento automático.</li>
      </ul>
      <p>
        <strong>Não pedimos informações de saúde pelo site nem pelo atendimento automático.</strong> Quando você
        menciona algo de saúde, a conversa passa para a profissional.
      </p>
      <h2>Para que usamos</h2>
      <ul>
        <li>Responder seu pedido e combinar avaliações e agendamentos (procedimentos preliminares e execução do serviço).</li>
        <li>Enviar avisos da sua reserva: confirmação, lembretes, link para alteração.</li>
        <li>Enviar novidades e promoções somente se você autorizar; responda STOP para parar.</li>
        <li>Segurança e prevenção de abuso dos nossos sistemas.</li>
      </ul>
      <h2>Inteligência artificial</h2>
      <p>
        Se o atendimento automático usar um modelo de linguagem para entender sua mensagem, ele recebe apenas o texto
        com telefones, e-mails, documentos e números removidos, e nunca seu nome ou dados de saúde. As respostas usam
        somente conteúdo aprovado pelas profissionais. Condições contratuais do provedor: pendente de verificação.
      </p>
      <h2>Com quem compartilhamos</h2>
      <p>
        Apenas com fornecedores necessários para operar o serviço (hospedagem, WhatsApp e agenda). Eventos na agenda
        das profissionais não contêm seu nome nem telefone. Não vendemos dados pessoais.
      </p>
      <h2>Por quanto tempo guardamos</h2>
      <ul>
        <li>Pedidos de contato que não viram agendamento: até 3 meses.</li>
        <li>Agendamentos, registros financeiros e consentimentos: conforme política de retenção específica (pendente de aprovação).</li>
      </ul>
      <h2>Seus direitos</h2>
      <p>
        Você pode pedir confirmação, acesso, correção, anonimização, portabilidade ou exclusão dos seus dados, além de
        revogar autorizações a qualquer momento.{" "}
        {content.legal_contact ? `Fale com a clínica: ${content.legal_contact}.` : "Canal de atendimento ao titular: pendente da clínica."}
      </p>
      <h2>Cookies e estatísticas</h2>
      <p>
        A medição de visitas pelo Plausible é opcional e só funciona depois de sua autorização em “Preferências de
        privacidade”, no rodapé, e da configuração pela clínica. Você pode recusar ou revogar a autorização ali. A
        escolha fica salva no armazenamento local deste navegador; não cria uma conta nem identifica você no nosso
        sistema. Se esse armazenamento estiver bloqueado, a escolha vale somente para a aba atual.
      </p>
      <p>
        A medição envia uma visita à página inicial, sem parâmetros da URL, e dados técnicos do navegador ao
        fornecedor. Não envia nome, telefone, conteúdo do formulário, mensagens ou dados de reserva. Não ocorre no
        painel, nas páginas de reserva, de atendimento ou de procedimentos. Ferramentas de publicidade permanecem
        desativadas; sua ativação exigirá autorização independente e revisão desta política.
      </p>
    </LegalPage>
  );
}
