import type { MetadataRoute } from "next";

import { siteIndexable } from "@/content/site";
import { getCatalog } from "@/lib/public/catalog";

export const dynamic = "force-dynamic";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const origin = process.env.LUMINI_PUBLIC_SITE_URL?.replace(/\/$/, "");
  if (!siteIndexable() || !origin) return [];
  const catalog = (await getCatalog()) ?? [];
  return [
    { url: `${origin}/`, changeFrequency: "weekly", priority: 1 },
    ...catalog.map((service) => ({ url: `${origin}/procedimentos/${service.slug}`, changeFrequency: "monthly" as const })),
  ];
}
