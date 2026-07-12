import { NextResponse } from "next/server";

const API_URL = process.env.INTERNAL_API_URL ?? "http://api:8000";

export async function POST(request: Request) {
  const credentials = await request.json();

  const response = await fetch(`${API_URL}/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(credentials),
    cache: "no-store",
  });

  const body = await response.json();

  if (!response.ok) {
    return NextResponse.json(body, {
      status: response.status,
    });
  }

  const result = NextResponse.json({
    user: body.user,
  });

  result.cookies.set("dentalflow_access_token", body.access_token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 30 * 60,
  });

  return result;
}
