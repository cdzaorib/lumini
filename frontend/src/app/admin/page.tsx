import type { Metadata } from "next";
import { headers } from "next/headers";

import { readAdminConfig } from "@/lib/admin/config";

import { AdminApp } from "./admin-app";

export const metadata: Metadata = {
  title: "Painel — Lumini",
  robots: { index: false, follow: false, nocache: true },
};

// Rendered per request so the CSP nonce from proxy.ts reaches every script.
export default async function AdminPage() {
  const nonce = (await headers()).get("x-nonce") ?? undefined;
  const config = readAdminConfig(
    process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID,
    process.env.NEXT_PUBLIC_API_BASE_URL,
    process.env.NODE_ENV,
  );
  return <AdminApp config={config} nonce={nonce} />;
}
