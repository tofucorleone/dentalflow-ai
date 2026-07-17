import { backendFetch } from "@/lib/server-api";

export async function PATCH(
  request: Request,
  context: {
    params: Promise<{
      id: string;
    }>;
  },
): Promise<Response> {
  const { id } = await context.params;
  const body = await request.text();

  const response = await backendFetch(
    `/patients/${encodeURIComponent(id)}`,
    {
      method: "PATCH",
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
        response.headers.get("Content-Type") ?? "application/json",
    },
  });
}
