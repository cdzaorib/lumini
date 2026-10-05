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
