import { NextRequest, NextResponse } from "next/server";

import { backendFetch } from "@/lib/server-api";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const query = request.nextUrl.searchParams.toString();
  const response = await backendFetch(
    `/conversations${query ? `?${query}` : ""}`,
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
