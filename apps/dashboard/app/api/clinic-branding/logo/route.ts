import { backendFetch } from "@/lib/server-api";

export async function GET() {
  const response = await backendFetch("/clinic-branding/logo");

  if (!response.ok) {
    return new Response(null, {
      status: response.status,
    });
  }

  const body = await response.arrayBuffer();

  return new Response(body, {
    status: response.status,
    headers: {
      "Content-Type":
        response.headers.get("Content-Type") ??
        "application/octet-stream",
      "Cache-Control": "no-store",
    },
  });
}

export async function POST(request: Request) {
  const formData = await request.formData();

  const response = await backendFetch("/clinic-branding/logo", {
    method: "POST",
    body: formData,
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
