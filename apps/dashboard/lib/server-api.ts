import { cookies } from "next/headers";
import type { Appointment } from "@/lib/api";

const API_URL = process.env.INTERNAL_API_URL ?? "http://api:8000";
const CLINIC_ID = process.env.CLINIC_ID;
const COOKIE_NAME = "dentalflow_access_token";

export function getClinicId(): string {
  if (!CLINIC_ID) {
    throw new Error("CLINIC_ID n'est pas configuré.");
  }

  return CLINIC_ID;
}

export async function backendFetch(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const cookieStore = await cookies();
  const accessToken = cookieStore.get(COOKIE_NAME)?.value;

  const headers = new Headers(init.headers);
  headers.set("X-Clinic-Id", getClinicId());

  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  const isFormData = init.body instanceof FormData;

  if (init.body && !isFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  return fetch(`${API_URL}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });
}

export type ClinicBranding = {
  id: string;
  name: string;
  display_name: string;
  software_name: string;
  logo_url: string | null;
  background_image_url: string | null;
  primary_color: string;
  currency_label: string;
};

export async function getClinicBranding(): Promise<ClinicBranding> {
  const response = await backendFetch("/clinic-branding");

  if (!response.ok) {
    throw new Error(
      `API ${response.status}: ${await response.text()}`,
    );
  }

  return response.json() as Promise<ClinicBranding>;
}


export async function getAppointments(): Promise<Appointment[]> {
  const response = await backendFetch("/appointments?limit=200");

  if (!response.ok) {
    throw new Error(
      `API ${response.status}: ${await response.text()}`,
    );
  }

  return response.json() as Promise<Appointment[]>;
}


export type CopilotRecallCandidate = {
  patient_id: string;
  patient_name: string | null;
  score: number;
  match_level: "primary" | "secondary";
  reasons: string[];
  requires_validation: boolean;
  draft_message: string;
};

export type CopilotReleasedSlot = {
  appointment_id: string;
  cancelled_patient_id: string;
  practitioner_id: string | null;
  practitioner_name: string | null;
  treatment_id: string | null;
  start_at: string;
  end_at: string;
  recall_candidates: CopilotRecallCandidate[];
};

export type CopilotOverdueRecallPatient = {
  patient_id: string;
  patient_name: string | null;
  phone: string;
  email: string | null;
  last_completed_at: string;
  score: number;
  priority: "high" | "medium" | "low";
  reasons: string[];
  draft_message: string;
};

export type CopilotAction = {
  id: string;
  priority: "high" | "medium" | "low";
  score: number;
  title: string;
  description: string;
  recommended_action: string;
  requires_validation: boolean;
};

export type CopilotTask = {
  id: string;
  type:
    | "recall"
    | "released_slot"
    | "late_active"
    | "pending_confirmation"
    | "no_show"
    | "conversation_reply";
  priority: "high" | "medium" | "low";
  score: number;
  title: string;
  description: string;
  recommended_action: string;
  patient_id: string | null;
  appointment_id: string | null;
  draft_id: string | null;
  draft_message: string | null;
  reasons: string[];
  status:
    | "open"
    | "prepared"
    | "completed"
    | "dismissed"
    | "snoozed";
  assigned_user_id: string | null;
  snoozed_until: string | null;
  completed_at: string | null;
  requires_validation: boolean;
  actions: {
    type: "navigate";
    label: string;
    href: string;
  }[];
};


export type CopilotDailyBrief = {
  date: string;
  timezone: string;
  clinic_id: string;
  user: {
    id: string;
    full_name: string | null;
    role: "owner" | "admin" | "staff";
  };
  summary: {
    total: number;
    pending: number;
    confirmed: number;
    cancelled: number;
    completed: number;
    no_show: number;
    active: number;
    upcoming: number;
  };
  priorities: {
    pending_confirmation: number;
    cancelled_today: number;
    no_show: number;
    late_active: number;
  };
  actions: CopilotAction[];
  released_slots: CopilotReleasedSlot[];
  overdue_recall_patients: CopilotOverdueRecallPatient[];
};

export async function getCopilotDailyBrief(): Promise<CopilotDailyBrief> {
  const response = await backendFetch("/copilot/daily-brief");

  if (!response.ok) {
    throw new Error(
      `API ${response.status}: ${await response.text()}`,
    );
  }

  return response.json() as Promise<CopilotDailyBrief>;
}

export async function getCopilotTasks(): Promise<CopilotTask[]> {
  const response = await backendFetch("/copilot/tasks");

  if (!response.ok) {
    throw new Error(
      `API ${response.status}: ${await response.text()}`,
    );
  }

  return response.json() as Promise<CopilotTask[]>;
}

