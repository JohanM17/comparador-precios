"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { CheckCircle2, LogOut } from "lucide-react";
import { ApiError, clienteApi, type PerfilUsuario } from "@/lib/api/clienteApi";
import { crearClienteAuthNavegador, obtenerTokenAcceso } from "@/lib/auth/supabase";
import { extraerInfoError, type InfoErrorVisible } from "@/lib/formato";
import Cargando from "@/components/Cargando";
import FormularioAccesoSupabase from "@/components/FormularioAccesoSupabase";
import FormularioAutorizacionDatos from "@/components/FormularioAutorizacionDatos";

type EstadoVista = "verificando" | "sin_sesion" | "requiere_ley1581" | "listo";

/**
 * Pantalla S5 (/ingresar): acceso con Supabase Auth y autorizacion obligatoria Ley 1581.
 */
export default function PaginaIngresar(): React.JSX.Element {
  const [estado, setEstado] = useState<EstadoVista>("verificando");
  const [token, setToken] = useState<string | null>(null);
  const [perfil, setPerfil] = useState<PerfilUsuario | null>(null);
  const [aliasConfirmado, setAliasConfirmado] = useState<string | null>(null);
  const [error, setError] = useState<InfoErrorVisible | null>(null);

  const verificarEstadoCuenta = useCallback(async () => {
    setEstado("verificando");
    setError(null);
    const jwt = await obtenerTokenAcceso();
    if (!jwt) {
      setToken(null);
      setPerfil(null);
      setEstado("sin_sesion");
      return;
    }

    setToken(jwt);
    try {
      const miPerfil = await clienteApi.obtenerMiCuenta(jwt);
      setPerfil(miPerfil);
      setEstado("listo");
    } catch (err) {
      if (err instanceof ApiError && err.problem.codigo === "AUTORIZACION_REQUERIDA") {
        setEstado("requiere_ley1581");
        return;
      }
      setError(extraerInfoError(err, "No pudimos validar tu sesión con el servidor."));
      setEstado("sin_sesion");
    }
  }, []);

  useEffect(() => {
    void verificarEstadoCuenta();
  }, [verificarEstadoCuenta]);

  const cerrarSesion = async (): Promise<void> => {
    const supabase = crearClienteAuthNavegador();
    await supabase.auth.signOut();
    setAliasConfirmado(null);
    setPerfil(null);
    setToken(null);
    setEstado("sin_sesion");
  };

  return (
    <div className="mx-auto max-w-xl px-4 py-8 sm:px-6">
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <h1 className="text-2xl font-bold text-slate-900">Acceso y privacidad</h1>
        <p className="mt-1 text-sm text-slate-600">
          Para reportar precios necesitas una cuenta activa y autorizar el tratamiento de datos
          conforme a la Ley 1581 de 2012.
        </p>

        <div className="mt-6">
          {estado === "verificando" && <Cargando filas={3} etiqueta="Verificando sesión..." />}

          {estado === "sin_sesion" && (
            <FormularioAccesoSupabase
              errorInicial={error}
              onSesionActiva={verificarEstadoCuenta}
            />
          )}

          {estado === "requiere_ley1581" && token && (
            <FormularioAutorizacionDatos
              token={token}
              onAutorizado={(aliasNuevo) => {
                setAliasConfirmado(aliasNuevo);
                void verificarEstadoCuenta();
              }}
            />
          )}

          {estado === "listo" && (
            <div className="space-y-4">
              <div
                role="status"
                className="flex items-start gap-3 rounded-xl border border-emerald-300 bg-emerald-50 p-4 text-sm text-emerald-950"
              >
                <CheckCircle2
                  className="mt-0.5 h-5 w-5 flex-shrink-0 text-emerald-700"
                  aria-hidden="true"
                />
                <div>
                  <p className="font-bold">
                    Sesión activa como {perfil?.alias ?? aliasConfirmado}
                  </p>
                  <p className="mt-1 text-xs">
                    Tu autorización de datos (Ley 1581) está vigente. Ya puedes reportar precios y
                    consultar tu historial.
                  </p>
                </div>
              </div>

              <div className="flex flex-wrap gap-3">
                <Link
                  href="/reportar"
                  className="inline-flex min-h-11 flex-1 items-center justify-center rounded-xl bg-emerald-700 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-800"
                >
                  Reportar un precio
                </Link>
                <Link
                  href="/gestion"
                  className="inline-flex min-h-11 flex-1 items-center justify-center rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-50"
                >
                  Ir a mi gestión
                </Link>
              </div>

              <button
                type="button"
                onClick={() => void cerrarSesion()}
                className="inline-flex min-h-10 w-full items-center justify-center gap-2 rounded-xl border border-slate-200 px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100"
              >
                <LogOut className="h-4 w-4" aria-hidden="true" />
                Cerrar sesión
              </button>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
