export const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
export const supabaseConfigured = Boolean(import.meta.env.VITE_SUPABASE_URL && import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY);
