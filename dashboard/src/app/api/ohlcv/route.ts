import { NextResponse } from "next/server";
import { getOhlcv, type Interval } from "@/lib/ohlcv";

const VALID_INTERVALS: Interval[] = ["1m", "5m", "15m", "1h", "4h", "1d"];

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const symbol = url.searchParams.get("symbol") ?? "BTC";
  const intervalParam = url.searchParams.get("interval") ?? "1h";
  const limitParam = parseInt(url.searchParams.get("limit") ?? "200", 10);

  if (!VALID_INTERVALS.includes(intervalParam as Interval)) {
    return NextResponse.json(
      { error: `Invalid interval. Allowed: ${VALID_INTERVALS.join(", ")}` },
      { status: 400 }
    );
  }
  const limit = Number.isFinite(limitParam) && limitParam > 0 && limitParam <= 1000 ? limitParam : 200;

  const candles = await getOhlcv(symbol, intervalParam as Interval, limit);
  return NextResponse.json({ symbol, interval: intervalParam, candles });
}
