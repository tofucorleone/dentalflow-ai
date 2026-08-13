import { NextResponse } from "next/server";

import { backendFetch } from "@/lib/server-api";

export async function GET() {
  const response = await backendFetch(
    "/copilot/dashboard-overview",
    {
      method: "GET",
    },
  );

  const text = await response.text();
  let body: unknown = null;

  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = { detail: text };
    }
  }

  return NextResponse.json(body, {
    status: response.status,
  });
}
