import { backendFetch } from "@/lib/server-api";

export async function DELETE(
  _request: Request,
  context: {
    params: Promise<{
      id: string;
      noteId: string;
    }>;
  },
): Promise<Response> {
  const { id, noteId } = await context.params;

  const response = await backendFetch(
    `/patients/${encodeURIComponent(id)}/notes/${encodeURIComponent(noteId)}`,
    {
      method: "DELETE",
    },
  );

  return new Response(null, {
    status: response.status,
  });
}
