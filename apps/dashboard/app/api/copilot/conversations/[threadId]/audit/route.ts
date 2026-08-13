import { NextResponse } from "next/server";
import { backendFetch } from "@/lib/server-api";
type RouteContext = { params: Promise<{ threadId: string }> };
export async function GET(_request: Request, context: RouteContext) {
  const { threadId } = await context.params;
  const response = await backendFetch(`/copilot/conversations/${encodeURIComponent(threadId)}/audit`, { method: "GET" });
  const text = await response.text();
  let body: unknown = null;
  if (text) { try { body = JSON.parse(text); } catch { body = { detail: text }; } }
  return NextResponse.json(body, { status: response.status });
}
