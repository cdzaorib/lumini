import type { Metadata } from "next";
import { headers } from "next/headers";

import { readApiOrigin } from "@/lib/api-origin";

import { SelfService } from "./self-service";

export const metadata: Metadata = {
  title: "Sua reserva — Lumini",
  robots: { index: false, follow: false, nocache: true },
};

// Rendered per request so the CSP nonce from proxy.ts reaches every script. The link token is in
// the URL fragment and never reaches this server.
export default async function BookingPage() {
  const nonce = (await headers()).get("x-nonce") ?? undefined;
  const apiOrigin = readApiOrigin(process.env.NEXT_PUBLIC_API_BASE_URL, process.env.NODE_ENV);
  return <SelfService apiOrigin={apiOrigin} nonce={nonce} />;
}
