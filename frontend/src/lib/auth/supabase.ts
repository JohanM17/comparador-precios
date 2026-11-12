import { createBrowserClient } from "@supabase/ssr";

/**
 * Cliente Supabase exclusivo para gestion de sesion de autenticacion (Auth).
 * Regla de Arquitectura: JAMAS utilizar supabase.from() en el cliente frontend.
 * Toda la logica de negocio y datos se resuelve a traves de FastAPI (/v1).
 */
const SUPABASE_URL =
  process.env.NEXT_PUBLIC_SUPABASE_URL || "https://pjwqpftvlglhorujhnii.supabase.co";
const SUPABASE_ANON_KEY =
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "anon-key-placeholder";

export function crearClienteAuthNavegador() {
  return createBrowserClient(SUPABASE_URL, SUPABASE_ANON_KEY);
}

export async function obtenerTokenAcceso(): Promise<string | null> {
  try {
    const supabase = crearClienteAuthNavegador();
    const {
      data: { session },
    } = await supabase.auth.getSession();
    return session?.access_token ?? null;
  } catch {
    return null;
  }
}

