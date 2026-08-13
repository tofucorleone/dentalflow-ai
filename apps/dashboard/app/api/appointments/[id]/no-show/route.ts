import { backendFetch } from "@/lib/server-api";

type RouteContext = {
  params: Promise<{
    id: string;
  }>;
};

export async function PATCH(
  _request: Request,
  context: RouteContext,
): Promise<Response> {
  const { id } = await context.params;

  const response = await backendFetch(
    `/appointments/${encodeURIComponent(
      id,
    )}/no-show`,
    {
      method: "PATCH",
    },
  );

  return new Response(
    response.body,
    {
      status: response.status,
      headers: {
        "Content-Type":
          response.headers.get(
            "Content-Type",
          ) ?? "application/json",
      },
    },
  );
}
