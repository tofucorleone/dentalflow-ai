import { NextRequest, NextResponse } from "next/server";

import { backendFetch } from "@/lib/server-api";

export const dynamic = "force-dynamic";

type RouteContext = {
  params: Promise<{
    threadId: string;
  }>;
};

export async function GET(
  request: NextRequest,
  context: RouteContext,
) {
  const { threadId } = await context.params;
  const query = request.nextUrl.searchParams.toString();
  const response = await backendFetch(
    `/conversations/${encodeURIComponent(threadId)}/messages${
      query ? `?${query}` : ""
    }`,
  );

  const body = await response.text();

  return new NextResponse(body, {
    status: response.status,
    headers: {
      "Content-Type":
        response.headers.get("Content-Type") ?? "application/json",
    },
  });
}
