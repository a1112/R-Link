import { createClient } from "@supabase/supabase-js";
import type { Database } from "./types";

const url = import.meta.env.VITE_SUPABASE_URL?.trim();
const key = import.meta.env.VITE_SUPABASE_ANON_KEY?.trim();
export const supabaseConfigured = Boolean(url && key);

// An unconfigured build never restores or refreshes historical sessions.
// AuthGate displays setup instructions and no management views are mounted.
export const supabase = createClient<Database>(url || "http://127.0.0.1:1", key || "unconfigured", {
  auth: {
    autoRefreshToken: supabaseConfigured,
    detectSessionInUrl: supabaseConfigured,
    persistSession: supabaseConfigured,
    storageKey: "rlink-auth-token",
  },
});
export default supabase;
