import { cookies } from "next/headers";

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
