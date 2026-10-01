export type AdminIdentity = {
  subject: string;
  email: string;
  reviewer_professional_ids: string[];
};

export type Professional = {
  id: string;
  display_name: string;
  category: string | null;
  council_registration: string | null;
  credentials_verified_at: string | null;
  revision: number;
};

export type ServiceContent = {
  objectives: string[];
  audience: string | null;
  preparation: string[];
  aftercare: string[];
  human_guidance: string | null;
  price_kind: "fixed" | "from" | "on_evaluation";
};

export type ServiceDraft = {
  slug: string;
  name: string;
  category: string;
  description: string | null;
  content: ServiceContent;
  duration_minutes: number | null;
  buffer_minutes: number;
  booking_mode: "evaluation" | "direct" | null;
  price_brl: string | null;
  deposit_brl: string | null;
  professional_ids: string[];
};

export type Service = ServiceDraft & {
  id: string;
  status: "draft" | "approved" | "published";
  revision: number;
  approved_at: string | null;
  published_at: string | null;
  approvals: { professional_id: string; approved_at: string }[];
};

export type Catalog = { professionals: Professional[]; services: Service[] };
export type Mutation = (path: string, method: "POST" | "PATCH", body: unknown, success: string) => Promise<boolean>;
