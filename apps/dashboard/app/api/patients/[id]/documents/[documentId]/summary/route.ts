import { backendFetch } from "@/lib/server-api";

export async function POST(
  _request: Request,
  context: {
    params: Promise<{
      id: string;
      documentId: string;
    }>;
  },
): Promise<Response> {
  const { id, documentId } = await context.params;

  const response = await backendFetch(
    `/patients/${encodeURIComponent(id)}/documents/${encodeURIComponent(documentId)}/summary`,
    {
      method: "POST",
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
