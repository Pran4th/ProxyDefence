// src/lib/supabase.ts
import { createClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

const mockSupabase = {
  auth: {
    getSession: async () => ({ data: { session: null } }),
    onAuthStateChange: () => ({
      data: {
        subscription: {
          unsubscribe: () => undefined,
        },
      },
    }),
    signOut: async () => ({ error: null }),
    signInWithOAuth: async () => ({
      data: { provider: null, url: null },
      error: new Error("Supabase is not configured."),
    }),
  },
};

if (!supabaseUrl || !supabaseAnonKey) {
  console.warn("Supabase credentials are missing. Running in mock auth mode.");
}

export const supabase =
  supabaseUrl && supabaseAnonKey
    ? createClient(supabaseUrl, supabaseAnonKey)
    : mockSupabase;
