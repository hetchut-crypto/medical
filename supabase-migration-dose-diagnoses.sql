-- Run this in Supabase Dashboard → SQL Editor for project mslqsmfwdmwgrahmpeqa
-- Creates Dose/Outcome Tracking + Diagnoses tables with RLS matching existing patterns.

-- ── Dose / Outcome logs ──────────────────────────────────────
create table if not exists public.dose_logs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  logged_at timestamptz not null default now(),
  -- [{ "name": "Naltrexone", "am": "4.5mg", "pm": "3.0mg" }, ...]
  doses jsonb not null default '[]'::jsonb,
  titrating_med text,
  outcome text not null check (outcome in ('pain', 'no_pain')),
  context_notes text,
  notes text,
  created_at timestamptz not null default now()
);

create index if not exists dose_logs_user_logged_at_idx
  on public.dose_logs (user_id, logged_at desc);

alter table public.dose_logs enable row level security;

create policy "Users manage own dose_logs"
  on public.dose_logs
  for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- ── Diagnoses ────────────────────────────────────────────────
create table if not exists public.diagnoses (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  condition_name text not null,
  doctor text,
  provider_id uuid references public.providers(id) on delete set null,
  date_diagnosed date,
  status text not null default 'Active'
    check (status in ('Active', 'Monitoring', 'Resolved')),
  notes text,
  created_at timestamptz not null default now()
);

create index if not exists diagnoses_user_created_idx
  on public.diagnoses (user_id, created_at);

alter table public.diagnoses enable row level security;

create policy "Users manage own diagnoses"
  on public.diagnoses
  for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- Refresh PostgREST schema cache
notify pgrst, 'reload schema';
