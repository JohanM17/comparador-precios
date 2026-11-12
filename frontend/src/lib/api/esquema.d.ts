/**
 * Tipos generados a partir de docs/api/openapi.json (FastAPI v1)
 */

export interface paths {
  "/v1/salud": {
    get: {
      responses: {
        200: {
          content: {
            "application/json": components["schemas"]["RespuestaSalud"];
          };
        };
      };
    };
  };
  "/v1/salud/listo": {
    get: {
      responses: {
        200: {
          content: {
            "application/json": components["schemas"]["RespuestaListo"];
          };
        };
        503: {
          content: {
            "application/problem+json": components["schemas"]["DetalleProblema"];
          };
        };
      };
    };
  };
  "/v1/auth/perfil-actual": {
    get: {
      responses: {
        200: {
          content: {
            "application/json": components["schemas"]["RespuestaUsuario"];
          };
        };
        401: {
          content: {
            "application/problem+json": components["schemas"]["DetalleProblema"];
          };
        };
      };
    };
  };
}

export interface components {
  schemas: {
    RespuestaSalud: {
      estado: string;
      version: string;
      entorno: string;
    };
    RespuestaListo: {
      estado: string;
      bd: string;
      cache: string;
    };
    RespuestaUsuario: {
      usuario_id: string;
      email: string | null;
      rol: string;
    };
    DetalleProblema: {
      type: string;
      title: string;
      status: number;
      detail: string;
      instance: string;
      codigo: string;
      request_id?: string | null;
    };
  };
}

