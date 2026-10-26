-- Phase 17b: public contact inbox. Server/service role controls all access.
create table if not exists public.contact_messages (
  id uuid primary key default gen_random_uuid(),
  name text not null check(char_length(name) between 2 and 100),
  email text not null check(char_length(email) between 5 and 254),
  subject text not null check(char_length(subject) between 5 and 120),
  message text not null check(char_length(message) between 10 and 2000),
  status text not null default 'open' check(status in ('open','resolved','closed')),
  admin_note text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists contact_messages_status_created_idx on public.contact_messages(status,created_at);
alter table public.contact_messages enable row level security;
-- Intentionally no client policies. Public submissions and admin reads go through the API.
