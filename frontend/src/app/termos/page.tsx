import type { Metadata } from "next";
import { headers } from "next/headers";

import { site } from "@/content/site";

import { LEGAL_APPROVED, LegalPage } from "../_site/legal";

export const metadata: Metadata = {
  title: `Termos e políticas de agendamento — ${site.name}`,
  robots: LEGAL_APPROVED ? undefined : { index: false, follow: false },
};

export default async function TermsPage() {
  await headers();
  return (
    <LegalPage title="Termos e políticas de agendamento">
      <h2>Informações do site</h2>
      <p>
        O conteúdo sobre procedimentos é informativo, aprovado pelas profissionais responsáveis, e não substitui uma
        avaliação. A indicação de qualquer procedimento para você é sempre decisão da profissional.
      </p>
      <h2>Reserva e sinal</h2>
      <ul>
        <li>O horário escolhido fica reservado por 2 horas para o pagamento do sinal.</li>
        <li>O sinal é conferido pela equipe; só então o agendamento é confirmado. Comprovantes enviados por mensagem não confirmam automaticamente.</li>
        <li>Sem confirmação no prazo, a reserva expira e o horário é liberado.</li>
        <li>Horários com menos de 3 horas de antecedência são combinados diretamente com a equipe.</li>
      </ul>
      <h2>Cancelamento e reagendamento</h2>
      <ul>
        <li>Com mais de 24 horas de antecedência, você pode cancelar ou reagendar pelo link pessoal enviado no WhatsApp.</li>
        <li>Com 24 horas ou menos, alterações são combinadas diretamente com a clínica.</li>
        <li>O primeiro reagendamento mantém o sinal. Um segundo reagendamento, exceções e reembolsos são decididos pela clínica.</li>
      </ul>
      <h2>Link pessoal</h2>
      <p>O link de alteração é pessoal e vale até o horário do atendimento. Não o compartilhe.</p>
      <h2>Atendimento automático</h2>
      <p>
        O atendimento automático informa e apresenta opções; não faz diagnóstico nem triagem. Você pode pedir para
        falar com a equipe a qualquer momento.
      </p>
    </LegalPage>
  );
}
