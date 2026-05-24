import { NextResponse } from 'next/server';

export async function GET() {
  const apiBaseUrl =
    process.env.BACKEND_API_URL ||
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    '';

  return NextResponse.json({ apiBaseUrl });
}
