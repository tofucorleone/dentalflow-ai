import { NextResponse } from "next/server";

import { backendFetch } from "@/lib/server-api";

type RouteContext = {
  params: Promise<{
    threadId: string;
  }>;
};

export async function PATCH(
  request: Request,
  context: RouteContext,
) {
  const { threadId } = await context.params;
  const body = await request.text();

  const response = await backendFetch(
    `/copilot/conversations/${encodeURIComponent(threadId)}/control`,
    {
      method: "PATCH",
      body,
    },
  );

  const responseText = await response.text();
  let responseBody: unknown = null;

  if (responseText) {
    try {
      responseBody = JSON.parse(responseText);
    } catch {
      responseBody = { detail: responseText };
    }
  }

  return NextResponse.json(responseBody, {
    status: response.status,
  });
}
