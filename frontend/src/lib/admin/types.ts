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
  communication_restrictions: string[];
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
export type Mutation = (path: string, method: "POST" | "PATCH" | "PUT", body: unknown, success: string) => Promise<boolean>;
// Authenticated GET whose failure is already reported to the user; null means "nothing to show".
export type Query = <T>(path: string, decode: (value: unknown) => T) => Promise<T | null>;
// Authenticated POST whose answer the caller needs (failures already reported).
export type Command = <T>(path: string, body: unknown, decode: (value: unknown) => T) => Promise<T | null>;

export const BOOKING_STATUSES = ["pending_calendar", "held", "confirming", "confirmed", "expired", "cancelled", "conflict"] as const;
export type BookingStatus = (typeof BOOKING_STATUSES)[number];
export type BookingScope = "upcoming" | "history";

// Contact data is shown only inside the authenticated panel; never log or persist it.
export type Booking = {
  id: string;
  code: string;
  status: BookingStatus;
  version: number;
  starts_at: string;
  ends_at: string;
  expires_at: string | null;
  service: { id: string; name: string };
  professional: { id: string; name: string };
  contact: { name: string; phone: string };
  deposit_brl: string;
  deposit_confirmed_at: string | null;
  calendar_status: string;
  reschedule_count: number;
  rescheduled_from_id: string | null;
  closed_reason: string | null;
  attendance: "attended" | "no_show" | null;
  origin: "whatsapp" | "site" | "reschedule" | "other";
  calendar_overlap_at: string | null;
};

export type BookingEvent = { action: string; from_status: string | null; to_status: string; actor: "system" | "staff" | "client"; at: string };

export type Count = { key: string; count: number };
export type Metrics = {
  days: number;
  leads_total: number;
  leads_by_status: Count[];
  leads_marketing_consent: number;
  bookings_requested: number;
  bookings_by_origin: Count[];
  deposits_confirmed: number;
  appointments: number;
  attended: number;
  no_show: number;
  attendance_unmarked: number;
  cancellations: Count[];
  reschedules: number;
  expired: Count[];
  demand_by_service: Count[];
  handoffs_by_reason: Count[];
  upcoming_confirmed_7d: number;
};

export type ScheduleRule = { weekday: number; start: string; end: string };
export type Schedule = { professional_id: string; calendar_id: string | null; revision: number; rules: ScheduleRule[] };

export type Integrations = {
  whatsapp: {
    configured: boolean;
    state: string | null;
    needs_attention: boolean;
    changed_at: string | null;
    human_mode_conversations: number;
  };
  calendar_configured: boolean;
  self_service_configured: boolean;
};

export const LEAD_STATUSES = ["new", "contacted", "converted", "discarded"] as const;
export type LeadStatus = (typeof LEAD_STATUSES)[number];

// Contact data is shown only inside the authenticated panel; never copy it elsewhere.
export type Lead = {
  id: string;
  name: string;
  phone: string;
  city: string | null;
  service: string | null;
  preferred_period: "morning" | "afternoon" | "any";
  source: string;
  status: LeadStatus;
  marketing_consent: boolean;
  created_at: string;
  retain_until: string;
};

export type SiteSettings = {
  revision: number;
  status: "draft" | "approved" | "published";
  published_at: string | null;
  reviewer_professional_id: string | null;
  eligible_reviewers: { professional_id: string; display_name: string; approved: boolean }[];
  required_reviewers: { professional_id: string; display_name: string; approved: boolean }[];
  media_origins: string[];
  bot_text_options: { key: string; label: string; default: string; placeholders: string[] }[];
  content: {
    address: { street: string; city: string; maps_url: string | null } | null;
    hours: string[];
    whatsapp: string | null;
    instagram: string | null;
    differentiators: string[];
    faq: { question: string; answer: string }[];
    testimonials: { quote: string; author: string; authorized_on: string; authorization_confirmed: true }[];
    legal_contact: string | null;
    deposit_instructions: string | null;
    photos: { url: string; alt: string; width: number; height: number; authorized_on: string; authorization_confirmed: true }[];
    bot_texts: Record<string, string>;
  };
};
