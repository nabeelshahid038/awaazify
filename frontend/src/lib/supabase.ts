import { createClient, type SupabaseClient } from '@supabase/supabase-js';
const url = import.meta.env.VITE_SUPABASE_URL;
const key = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY;
// No placeholder credentials: absence is surfaced in UI until Phase 2 setup.
export const supabase: SupabaseClient | null = url && key ? createClient(url, key) : null;
