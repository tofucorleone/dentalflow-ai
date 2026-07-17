import { backendFetch } from "@/lib/server-api";

export async function GET(
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
    `/patients/${encodeURIComponent(id)}/documents/${encodeURIComponent(documentId)}/download`,
    {
      method: "GET",
    },
  );

  return new Response(response.body, {
    status: response.status,
    headers: response.headers,
  });
}

export async function DELETE(
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
    `/patients/${encodeURIComponent(id)}/documents/${encodeURIComponent(documentId)}`,
    {
      method: "DELETE",
    },
  );

  return new Response(null, {
    status: response.status,
  });
}
