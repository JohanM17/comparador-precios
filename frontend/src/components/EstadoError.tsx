import React from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

export interface EstadoErrorProps {
  readonly detalle: string;
  readonly codigo?: string;
  readonly requestId?: string;
  readonly onReintentar?: () => void;
}

/**
 * Componente estructurado para presentar errores conformes al estandar RFC 9457 (ProblemDetails).
 * Permite al usuario reportar el request_id al soporte y reintentar la operacion.
 */
export default function EstadoError({
  detalle,
  codigo,
  requestId,
  onReintentar,
}: EstadoErrorProps): React.JSX.Element {
  return (
    <div
      role="alert"
      aria-live="assertive"
      className="rounded-xl border border-rose-200 bg-rose-50/70 p-6 text-rose-950 sm:p-8"
    >
      <div className="flex items-start gap-4">
        <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-rose-100 text-rose-700">
          <AlertTriangle className="h-5 w-5" aria-hidden="true" />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="text-base font-semibold text-rose-900">
            {codigo ? `Ocurrio un error (${codigo})` : "Ocurrio un problema inesperado"}
          </h3>
          <p className="mt-1 text-sm text-rose-800 break-words">{detalle}</p>

          {requestId && (
            <div className="mt-3 flex items-center gap-2 font-mono text-xs text-rose-700">
              <span className="font-semibold">ID de seguimiento:</span>
              <code className="rounded bg-rose-100/80 px-2 py-0.5 select-all">
                {requestId}
              </code>
            </div>
          )}

          {onReintentar && (
            <div className="mt-5">
              <button
                type="button"
                onClick={onReintentar}
                className="inline-flex min-h-10 items-center gap-2 rounded-lg bg-rose-700 px-4 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-rose-800 focus:outline-none focus:ring-2 focus:ring-rose-600 focus:ring-offset-2"
              >
                <RefreshCw className="h-4 w-4" aria-hidden="true" />
                <span>Reintentar</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
