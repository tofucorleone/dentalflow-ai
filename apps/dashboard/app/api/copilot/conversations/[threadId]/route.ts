import { backendFetch } from "@/lib/server-api";

type RouteContext = {
  params: Promise<{
    threadId: string;
  }>;
};

export async function GET(
  _request: Request,
  context: RouteContext,
): Promise<Response> {
  const { threadId } = await context.params;

  const response = await backendFetch(
    `/copilot/conversations/${threadId}/insight`,
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
