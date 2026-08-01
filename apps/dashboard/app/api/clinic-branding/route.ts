import { backendFetch } from "@/lib/server-api";

export async function PATCH(request: Request) {
  const payload = await request.json();

  const response = await backendFetch("/clinic-branding", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });

  const body = await response.text();

  return new Response(body, {
    status: response.status,
    headers: {
      "Content-Type":
        response.headers.get("Content-Type") ??
        "application/json",
    },
  });
}
