# Crypto Trading Desk — Dashboard

Modern dashboard for the multi-agent trading system. Reads directly from the local SQLite database (`../data/db/learning.db`) and the markdown reports in `../data/reports/`.

## Stack

- Next.js 16 (App Router, Server Components, Turbopack)
- React 19 + TypeScript
- Tailwind CSS v4 + shadcn/ui (Card, Table, Tabs, Badge, ScrollArea, Dialog)
- Recharts for the equity curve
- Framer Motion for entry animations + animated KPI numbers
- lucide-react for icons
- react-markdown + remark-gfm for rendering decision reports
- better-sqlite3 for direct read-only access to the learning DB

## Run

```bash
cd dashboard
npm install        # only first time
npm run dev        # http://localhost:3000
```

The dashboard is read-only and never blocks the trading system — both can run simultaneously.

## What's on the page

| Section | Source |
|---|---|
| KPI cards (Equity, PnL, Win Rate, Open) | `portfolio_state` + `trades` |
| Equity curve | running sum of closed `trades.pnl_usd` |
| Recent trades (with expandable reasoning) | `trades` table, last 25 |
| Patterns | `patterns` table |
| Predictions panel | `predictions` table + accuracy split |
| Latest Decision | most recent `decision.md` under `data/reports/` |

## Migration path to public hosting (when ready)

The frontend code is reusable. To publish:

1. Move data to Supabase (Postgres) and add a sync job from local SQLite.
2. Swap `src/lib/db.ts` to call Supabase REST instead of `better-sqlite3`.
3. Deploy on Vercel (free tier) — the rest of the code is unchanged.
