/**
 * Identificadores para idempotencia en clientes web.
 *
 * `crypto.randomUUID()` solo existe en contextos seguros (HTTPS o localhost).
 * En la LAN por HTTP (por ejemplo, abrir la app desde el telefono en
 * `http://192.168.x.x:3000`) no esta disponible. `crypto.getRandomValues()`
 * si funciona en contextos no seguros, asi que se usa como respaldo.
 */
export function generarUuidV4(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }

  const bytes = new Uint8Array(16);
  if (typeof crypto !== "undefined" && typeof crypto.getRandomValues === "function") {
    crypto.getRandomValues(bytes);
  } else {
    for (let i = 0; i < bytes.length; i += 1) {
      bytes[i] = Math.floor(Math.random() * 256);
    }
  }

  // Version 4 y variante RFC 4122.
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;

  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}
