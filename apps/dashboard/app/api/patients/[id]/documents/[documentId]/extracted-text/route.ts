import { backendFetch } from "@/lib/server-api";

export async function PATCH(
  request: Request,
  context: {
    params: Promise<{
      id: string;
      documentId: string;
    }>;
  },
): Promise<Response> {
  const { id, documentId } = await context.params;
  const body = await request.text();

  const response = await backendFetch(
    `/patients/${encodeURIComponent(id)}/documents/${encodeURIComponent(documentId)}/extracted-text`,
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
