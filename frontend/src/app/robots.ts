import type { MetadataRoute } from "next";

import { siteIndexable } from "@/content/site";

// Closed to search engines until the launch gate (LUMINI_SITE_PUBLIC=true).
export default function robots(): MetadataRoute.Robots {
  if (!siteIndexable()) return { rules: { userAgent: "*", disallow: "/" } };
  const origin = process.env.LUMINI_PUBLIC_SITE_URL;
  return {
    rules: { userAgent: "*", allow: "/", disallow: ["/admin", "/reserva"] },
    ...(origin ? { sitemap: `${origin.replace(/\/$/, "")}/sitemap.xml` } : {}),
  };
}
