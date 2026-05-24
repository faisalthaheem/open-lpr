import { NextResponse } from 'next/server';

export async function GET() {
  const apiBaseUrl =
    process.env.BACKEND_API_URL ||
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    '';

  if (apiBaseUrl) {
    return NextResponse.redirect(`${apiBaseUrl}/health/`);
  }
  return NextResponse.json({ status: 'spa-ok', backend: 'not configured' });
}
