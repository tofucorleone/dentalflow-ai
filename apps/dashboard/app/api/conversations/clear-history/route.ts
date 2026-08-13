import { NextResponse } from "next/server";

import { backendFetch } from "@/lib/server-api";

export async function POST() {
  const response = await backendFetch(
    "/conversations/clear-history",
    {
      method: "POST",
    },
  );

  const body = await response.text();

  return new NextResponse(body, {
    status: response.status,
    headers: {
      "Content-Type":
        response.headers.get("Content-Type") ??
        "application/json",
    },
  });
}
