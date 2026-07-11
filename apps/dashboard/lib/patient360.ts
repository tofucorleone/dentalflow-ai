import { backendFetch } from "@/lib/server-api";

export type Patient360 = {
  patient: {
    id: string;
    full_name: string | null;
    phone: string;
    email: string | null;
    administrative_notes: string | null;
  };
  appointments: Array<{
    id: string;
    status: string;
    channel: string;
    start_at: string;
    end_at: string;
    practitioner_name: string | null;
    treatment_name: string | null;
    treatment_price: number | null;
  }>;
  notes: Array<{
    id: string;
    author_name: string | null;
    note: string;
    created_at: string;
  }>;
  documents: Array<{
    id: string;
    document_type: string;
    filename: string;
    storage_url: string;
    created_at: string;
  }>;
  conversations: Array<{
    id: string;
    channel: string;
    direction: string;
    message: string;
    created_at: string;
  }>;
  memory: {
    summary: string | null;
    preferences: Record<string, unknown>;
    last_goal: string | null;
    updated_at: string;
  } | null;
  medical_history: Array<{
    id: string;
    category: string;
    value: string;
    is_active: boolean;
  }>;
};

export async function getPatient360(id: string): Promise<Patient360> {
  const response = await backendFetch(`/patients/${encodeURIComponent(id)}`);
  if (!response.ok) throw new Error(`API ${response.status}: ${await response.text()}`);
  return response.json() as Promise<Patient360>;
}
