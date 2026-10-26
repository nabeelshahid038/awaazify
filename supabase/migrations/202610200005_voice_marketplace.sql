-- Phase 17: presentation metadata for the public voice marketplace.
alter table public.voice_models
  add column if not exists category text not null default 'Featured',
  add column if not exists image_url text,
  add column if not exists demo_url_1 text,
  add column if not exists demo_url_2 text,
  add column if not exists sort_order integer not null default 100;

alter table public.voice_models
  drop constraint if exists voice_models_category_length,
  add constraint voice_models_category_length check (char_length(category) between 1 and 40),
  drop constraint if exists voice_models_image_url_length,
  add constraint voice_models_image_url_length check (image_url is null or char_length(image_url) <= 500),
  drop constraint if exists voice_models_demo_url_1_length,
  add constraint voice_models_demo_url_1_length check (demo_url_1 is null or char_length(demo_url_1) <= 500),
  drop constraint if exists voice_models_demo_url_2_length,
  add constraint voice_models_demo_url_2_length check (demo_url_2 is null or char_length(demo_url_2) <= 500);

create index if not exists voice_models_marketplace_idx
  on public.voice_models(is_active, visibility, sort_order, display_name);
