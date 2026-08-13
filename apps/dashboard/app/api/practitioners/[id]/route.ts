import { backendFetch } from "@/lib/server-api";

type RouteContext = {
  params: Promise<{
    id: string;
  }>;
};

export async function PATCH(
  request: Request,
  context: RouteContext,
): Promise<Response> {
  const { id } = await context.params;
  const body = await request.text();

  const response = await backendFetch(
    `/practitioners/${encodeURIComponent(id)}`,
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
        response.headers.get("Content-Type") ??
        "application/json",
    },
  });
}

export async function DELETE(
  _request: Request,
  context: RouteContext,
): Promise<Response> {
  const { id } = await context.params;

  const response = await backendFetch(
    `/practitioners/${encodeURIComponent(id)}`,
    {
      method: "DELETE",
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
