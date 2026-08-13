import { NextResponse } from "next/server";

import { backendFetch } from "@/lib/server-api";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  const backendResponse = await backendFetch(
    "/conversations/events",
    {
      method: "GET",
      headers: {
        Accept: "text/event-stream",
      },
    },
  );

  if (!backendResponse.ok) {
    const body = await backendResponse.text();

    return NextResponse.json(
      {
        detail:
          body ||
          `Flux temps réel indisponible (${backendResponse.status}).`,
      },
      {
        status: backendResponse.status,
      },
    );
  }

  if (!backendResponse.body) {
    return NextResponse.json(
      {
        detail: "Le backend n’a retourné aucun flux SSE.",
      },
      {
        status: 502,
      },
    );
  }

  return new Response(
    backendResponse.body,
    {
      status: 200,
      headers: {
        "Content-Type": "text/event-stream; charset=utf-8",
        "Cache-Control": "no-cache, no-transform",
        Connection: "keep-alive",
        "X-Accel-Buffering": "no",
      },
    },
  );
}
