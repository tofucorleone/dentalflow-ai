import { NextRequest, NextResponse } from "next/server";

import { backendFetch } from "@/lib/server-api";

type RouteContext = {
  params: Promise<{
    threadId: string;
  }>;
};

export async function POST(
  request: NextRequest,
  context: RouteContext,
) {
  const { threadId } = await context.params;

  let payload: unknown;

  try {
    payload = await request.json();
  } catch {
    return NextResponse.json(
      {
        detail: "Le corps JSON est invalide.",
      },
      {
        status: 400,
      },
    );
  }

  const response = await backendFetch(
    `/conversations/${threadId}/send`,
    {
      method: "POST",
      body: JSON.stringify(payload),
      headers: {
        "Content-Type": "application/json",
      },
    },
  );

  const responseText = await response.text();

  let responseBody: unknown = null;

  if (responseText) {
    try {
      responseBody = JSON.parse(responseText);
    } catch {
      responseBody = {
        detail: responseText,
      };
    }
  }

  return NextResponse.json(
    responseBody,
    {
      status: response.status,
    },
  );
}
