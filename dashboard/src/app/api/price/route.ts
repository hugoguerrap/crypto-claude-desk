import { NextResponse } from "next/server";
import { getCurrentPrice } from "@/lib/ohlcv";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const symbol = url.searchParams.get("symbol") ?? "BTC";
  const price = await getCurrentPrice(symbol);
  return NextResponse.json({ symbol, price });
}
