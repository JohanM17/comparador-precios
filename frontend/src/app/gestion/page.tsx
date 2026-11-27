"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ShieldCheck } from "lucide-react";
import { ApiError, clienteApi, type PerfilUsuario } from "@/lib/api/clienteApi";
import { obtenerTokenAcceso } from "@/lib/auth/supabase";
import { extraerInfoError, type InfoErrorVisible } from "@/lib/formato";
import Cargando from "@/components/Cargando";
import EstadoError from "@/components/EstadoError";
import PestanaAuditoria from "@/components/gestion/PestanaAuditoria";
import PestanaCatalogoTiendas from "@/components/gestion/PestanaCatalogoTiendas";
import PestanaColaCasos from "@/components/gestion/PestanaColaCasos";
import PestanaMiCuenta from "@/components/gestion/PestanaMiCuenta";
import PestanaMisReportes from "@/components/gestion/PestanaMisReportes";
import PestanaParametros from "@/components/gestion/PestanaParametros";

type IdPestana =
  | "mis_reportes"
  | "mi_cuenta"
  | "cola_casos"
  | "catalogo_tiendas"
  | "parametros"
  | "auditoria";

interface DefinicionPestana {
  readonly id: IdPestana;
  readonly titulo: string;
}

const PESTANAS_REPORTANTE: readonly DefinicionPestana[] = [
  { id: "mis_reportes", titulo: "Mis reportes" },
  { id: "mi_cuenta", titulo: "Mi cuenta" },
];

const PESTANAS_MODERADOR: readonly DefinicionPestana[] = [
  { id: "cola_casos", titulo: "Cola de casos" },
  { id: "catalogo_tiendas", titulo: "Catálogo y tiendas" },
  { id: "parametros", titulo: "Parámetros (43)" },
  { id: "auditoria", titulo: "Auditoría" },
];

/**
 * Pantalla S6 (/gestion): panel unificado por rol para Reportante y Moderador.
 */
export default function PaginaGestion(): React.JSX.Element {
  const [cargando, setCargando] = useState(true);
  const [token, setToken] = useState<string | null>(null);
  const [perfil, setPerfil] = useState<PerfilUsuario | null>(null);
  const [requiereIngreso, setRequiereIngreso] = useState(false);
  const [eliminada, setEliminada] = useState(false);
  const [error, setError] = useState<InfoErrorVisible | null>(null);
  const [pestanaActiva, setPestanaActiva] = useState<IdPestana>("mis_reportes");

  const cargarPerfil = useCallback(async () => {
    setCargando(true);
    setError(null);
    setRequiereIngreso(false);

    const jwt = await obtenerTokenAcceso();
    if (!jwt) {
      setToken(null);
      setPerfil(null);
      setRequiereIngreso(true);
      setCargando(false);
      return;
    }

    setToken(jwt);
    try {
      const miPerfil = await clienteApi.obtenerMiCuenta(jwt);
      setPerfil(miPerfil);
      if (miPerfil.rol === "moderador" || miPerfil.rol === "admin") {
        setPestanaActiva("cola_casos");
      } else {
        setPestanaActiva("mis_reportes");
      }
    } catch (err) {
      if (err instanceof ApiError && err.problem.codigo === "AUTORIZACION_REQUERIDA") {
        setRequiereIngreso(true);
        return;
      }
      setError(extraerInfoError(err, "No fue posible cargar tu panel de gestión."));
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    void cargarPerfil();
  }, [cargarPerfil]);

  const pestanasDisponibles = useMemo(() => {
    if (!perfil) {
      return [];
    }
    if (perfil.rol === "moderador" || perfil.rol === "admin") {
      return [...PESTANAS_MODERADOR, ...PESTANAS_REPORTANTE];
    }
    return [...PESTANAS_REPORTANTE];
  }, [perfil]);

  if (cargando) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
        <Cargando filas={5} etiqueta="Cargando panel de gestión..." />
      </div>
    );
  }

  if (eliminada) {
    return (
      <div className="mx-auto max-w-xl px-4 py-10 sm:px-6">
        <section className="rounded-2xl border border-emerald-300 bg-superficie p-6 text-center">
          <h1 className="text-xl font-bold text-slate-900">Cuenta suprimida y anonimizada</h1>
          <p className="mt-2 text-sm text-slate-600">
            Tus credenciales fueron eliminadas y tus reportes históricos quedaron anonimizados conforme a la Ley 1581.
          </p>
          <Link
            href="/"
            className="mt-5 inline-flex min-h-11 items-center justify-center rounded-xl bg-bosque-800 px-5 text-sm font-semibold text-white"
          >
            Volver al inicio
          </Link>
        </section>
      </div>
    );
  }

  if (requiereIngreso || !token || !perfil) {
    return (
      <div className="mx-auto max-w-xl px-4 py-10 sm:px-6">
        <section className="rounded-2xl border border-slate-300 bg-superficie p-6 text-center">
          <h1 className="text-2xl font-bold text-slate-900">Panel de gestión</h1>
          {error ? (
            <div className="mt-4 text-left">
              <EstadoError
                detalle={error.detalle}
                codigo={error.codigo}
                requestId={error.requestId}
                onReintentar={() => void cargarPerfil()}
              />
            </div>
          ) : (
            <>
              <p className="mt-2 text-sm text-slate-600">
                Inicia sesión y autoriza el tratamiento de datos (Ley 1581) para consultar tus reportes, gestionar tu cuenta o moderar casos.
              </p>
              <Link
                href="/ingresar"
                className="mt-5 inline-flex min-h-11 items-center justify-center rounded-xl bg-bosque-800 px-5 text-sm font-semibold text-white hover:bg-bosque-900"
              >
                Ir a ingresar
              </Link>
            </>
          )}
        </section>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">Panel de gestión</h1>
          <p className="mt-1 flex items-center gap-2 text-sm text-slate-600">
            <ShieldCheck className="h-4 w-4 text-emerald-700" aria-hidden="true" />
            <span>
              Sesión: <strong>{perfil.alias}</strong> · Rol: <strong>{perfil.rol}</strong>
            </span>
          </p>
        </div>
        <Link
          href="/reportar"
          className="inline-flex min-h-11 items-center justify-center rounded-full bg-bosque-800 px-5 text-sm font-semibold text-white hover:bg-bosque-900"
        >
          Nuevo reporte
        </Link>
      </header>

      <div
        role="tablist"
        aria-label="Secciones de gestión"
        className="flex flex-wrap gap-1 border-b border-slate-300"
      >
        {pestanasDisponibles.map((tab) => {
          const activa = tab.id === pestanaActiva;
          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={activa}
              onClick={() => setPestanaActiva(tab.id)}
              className={`-mb-px min-h-11 border-b-4 px-4 text-sm font-semibold transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-700 ${
                activa
                  ? "border-cereza-600 text-slate-900"
                  : "border-transparent text-slate-600 hover:border-slate-300 hover:text-slate-900"
              }`}
            >
              {tab.titulo}
            </button>
          );
        })}
      </div>

      <section role="tabpanel" aria-label={pestanaActiva}>
        {pestanaActiva === "mis_reportes" && <PestanaMisReportes token={token} />}
        {pestanaActiva === "mi_cuenta" && (
          <PestanaMiCuenta
            token={token}
            perfil={perfil}
            onPerfilActualizado={setPerfil}
            onCuentaEliminada={() => setEliminada(true)}
          />
        )}
        {pestanaActiva === "cola_casos" && <PestanaColaCasos token={token} />}
        {pestanaActiva === "catalogo_tiendas" && <PestanaCatalogoTiendas token={token} />}
        {pestanaActiva === "parametros" && <PestanaParametros token={token} />}
        {pestanaActiva === "auditoria" && <PestanaAuditoria token={token} />}
      </section>
    </div>
  );
}

