import { NextRequest, NextResponse } from "next/server";

import { backendFetch } from "@/lib/server-api";

export async function PATCH(
  request: NextRequest,
  context: {
    params: Promise<{
      taskKey: string[];
    }>;
  },
) {
  const { taskKey } = await context.params;

  const body = await request.text();

  const response = await backendFetch(
    `/copilot/tasks/${taskKey.map(encodeURIComponent).join("/")}`,
    {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body,
    },
  );

  const payload = await response.text();

  return new NextResponse(payload, {
    status: response.status,
    headers: {
      "Content-Type":
        response.headers.get("content-type") ??
        "application/json",
    },
  });
}
