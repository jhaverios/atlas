// src/lib/db.ts
import 'server-only'
import postgres from 'postgres'

if (!process.env.ATLAS_DB_URL) {
  throw new Error('ATLAS_DB_URL is not defined. Set it in .env.local.')
}

const isPooler = process.env.ATLAS_DB_URL.includes('pooler.supabase.com')

// M13: sql.begin() + SET LOCAL requires session-mode pooler (port 5432).
// Transaction-mode pooler (port 6543) releases the connection between
// statements — SET LOCAL has no effect and audit rows get NULL change_reason,
// which is a SEBI compliance gap. Fail fast at module load.
if (process.env.ATLAS_DB_URL.includes(':6543/')) {
  throw new Error(
    'ATLAS_DB_URL must use session-mode pooler (port 5432), not transaction-mode (port 6543). ' +
    'M13 audit trail relies on sql.begin() + SET LOCAL which requires a pinned connection.',
  )
}

// The session-mode pooler allows 15 clients IN ALL, shared by this server, every `next build`
// (each build worker opens its own pool) and the Python pipelines on the same role. The server
// used to take 14, so a build could only succeed while the board sat idle: the midday deploy of
// #293 on 2026-09-28 died prerendering /stocks with EMAXCONNSESSION ("max clients reached in
// session mode"). The budget is now split — server 10, build 2 — leaving room for the pipelines.
// Next sets NEXT_PHASE before it spawns its build workers (next/dist/build, 15.3). The stock
// page's 11-query fan-out queues for a moment on 10; idle_timeout recycles connections fast.
const isBuild = process.env.NEXT_PHASE === 'phase-production-build'
const sql = postgres(process.env.ATLAS_DB_URL, {
  max: isBuild ? 2 : 10,
  idle_timeout: 10,
  max_lifetime: 60 * 5,
  connect_timeout: 10,
  // Transaction-mode pooler (Supabase) doesn't support prepared statements
  prepare: !isPooler,
  ssl: process.env.ATLAS_DB_URL.includes('sslmode=require')
    ? { rejectUnauthorized: false }
    : false,
})

export default sql
