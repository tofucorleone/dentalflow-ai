import { backendFetch } from "@/lib/server-api";

export async function POST(
  request: Request,
  context: { params: Promise<{ id: string }> },
): Promise<Response> {
  const { id } = await context.params;

  const formData = await request.formData();

  const response = await backendFetch(
    `/patients/${encodeURIComponent(id)}/documents`,
    {
      method: "POST",
      body: formData,
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
