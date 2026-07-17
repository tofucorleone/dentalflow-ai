import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.INTERNAL_API_URL ?? "http://api:8000";
const CLINIC_ID = process.env.CLINIC_ID;

export async function POST(request: NextRequest) {
  if (!CLINIC_ID) {
    return NextResponse.json(
      { error: "CLINIC_ID manquant." },
      { status: 500 },
    );
  }

  const body = await request.text();

  const response = await fetch(
    `${API_URL}/appointments`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Clinic-Id": CLINIC_ID,
      },
      body,
    },
  );

  return NextResponse.json(
    await response.json(),
    {
      status: response.status,
    },
  );
}
