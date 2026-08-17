import { backendFetch } from "@/lib/server-api";

export async function POST(
  request: Request,
): Promise<Response> {
  const body = await request.text();

  const response = await backendFetch(
    "/copilot/appointment-message-drafts",
    {
      method: "POST",
      body,
      headers: {
        "Content-Type": "application/json",
      },
    },
  );

  return new Response(response.body, {
    status: response.status,
    headers: {
      "Content-Type":
        response.headers.get("Content-Type") ??
        "application/json",
    },
  });
}
