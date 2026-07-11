import { NextResponse } from "next/server";
import { backendFetch } from "@/lib/server-api";

export async function POST(
  request: Request,
  context: { params: Promise<{ id: string }> },
) {
  const { id } = await context.params;
  const payload = await request.json();

  const response = await backendFetch(
    `/patients/${encodeURIComponent(id)}/notes`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );

  const text = await response.text();
  let body: unknown;
  try {
    body = JSON.parse(text);
  } catch {
    body = { detail: text };
  }

  return NextResponse.json(body, { status: response.status });
}
