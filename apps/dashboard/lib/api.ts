const API_URL = process.env.INTERNAL_API_URL ?? "http://api:8000";
const CLINIC_ID = process.env.CLINIC_ID;

async function apiFetch<T>(path: string): Promise<T> {
  if (!CLINIC_ID) throw new Error("CLINIC_ID n'est pas configuré.");
  const response = await fetch(`${API_URL}${path}`, {
    headers: { "X-Clinic-Id": CLINIC_ID },
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`API ${response.status}: ${await response.text()}`);
  return response.json() as Promise<T>;
}

export type Appointment = {
  id: string; status: string; channel: string; start_at: string; end_at: string;
  patient_name: string | null; patient_phone: string;
  practitioner_name: string | null; treatment_name: string | null;
};
export type Patient = { id: string; phone: string; full_name: string | null; email: string | null; };
export type Treatment = { id: string; name: string; description: string | null; duration_minutes: number; price: number; active: boolean; };
export type Practitioner = { id: string; full_name: string; speciality: string | null; google_calendar_id: string | null; active: boolean; };

export const getAppointments = () => apiFetch<Appointment[]>("/appointments?limit=200");
export const getPatients = () => apiFetch<Patient[]>("/patients?limit=100");
export const getTreatments = () => apiFetch<Treatment[]>("/treatments");
export const getPractitioners = () => apiFetch<Practitioner[]>("/practitioners");
