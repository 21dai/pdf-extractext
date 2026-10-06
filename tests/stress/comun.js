// Partes compartidas por los scripts de k6 del TP: los PDFs oficiales, como se
// manda cada uno, las metricas por PDF y por codigo HTTP, y el resumen.

import http from "k6/http";
import { Trend, Rate, Counter } from "k6/metrics";

export const BASE_URL = __ENV.BASE_URL || "https://extract.universidad.localhost";
export const MODO = __ENV.MODO || "crudo"; // crudo | multipart

// Los nombres *.localhost siempre son la propia maquina (RFC 6761), pero el
// resolver de k6 en Windows no lo sabe: se los resuelve el script.
const HOST = (BASE_URL.match(/^https?:\/\/([^/:]+)/) || [])[1] || "";
export const HOSTS = HOST.endsWith(".localhost") ? { [HOST]: "127.0.0.1" } : {};

export const PDFS = [
  { clave: "scrum_guide", nombre: "2020-Scrum-Guide-Spanish-Latin-South-American.pdf", corto: "Scrum Guide (16 pag, 0,3 MB)" },
  { clave: "kanban", nombre: "Essential-Kanban-Condensed-Spanish.pdf", corto: "Essential Kanban (90 pag, 8,9 MB)" },
  { clave: "lean", nombre: "Filosofia Lean.pdf", corto: "Filosofia Lean (42 pag, 0,7 MB)" },
  { clave: "scrum_manager", nombre: "scrum_manager_historias_usuario.pdf", corto: "Scrum Manager (62 pag, 3,8 MB)" },
];

// Se cargan en el init context (una vez por VU), con la ruta relativa a este
// archivo.
for (const pdf of PDFS) {
  pdf.bytes = open(`./pdfs/${pdf.nombre}`, "b");
  pdf.tiempo = new Trend(`tiempo_${pdf.clave}`, true);
  pdf.exito = new Rate(`exito_${pdf.clave}`);
}
const tiempoTotal = new Trend("tiempo_por_documento", true);
const exitoTotal = new Rate("exito_por_documento");
// Contadores por codigo HTTP (k6 no muestra contadores con tags en el resumen).
const CODIGOS = ["200", "400", "413", "422", "429", "502", "503", "504", "0"];
const porCodigo = {};
for (const c of CODIGOS) porCodigo[c] = new Counter(`codigo_${c}`);
const otrosCodigos = new Counter("codigo_otros");

export function enviar(pdf, timeout) {
  const url = `${BASE_URL}/extract`;
  const params = { tags: { pdf: pdf.corto }, timeout };
  if (MODO === "multipart") {
    return http.post(url, { file: http.file(pdf.bytes, pdf.nombre, "application/pdf") }, params);
  }
  params.headers = { "Content-Type": "application/pdf" };
  return http.post(url, pdf.bytes, params);
}

// latenciaDeTodos: true mide todas las respuestas (como Vegeta, donde un
// timeout cuenta 30 s); false solo las 200 (como el benchmark de k6).
export function registrar(pdf, res, latenciaDeTodos) {
  const ok = res.status === 200;
  if (ok || latenciaDeTodos) {
    pdf.tiempo.add(res.timings.duration);
    tiempoTotal.add(res.timings.duration);
  }
  pdf.exito.add(ok);
  exitoTotal.add(ok);
  (porCodigo[String(res.status)] || otrosCodigos).add(1);
  return ok;
}

// ---------- Resumen en la terminal ----------

export const ANCHO = 102;

export function seg(ms) {
  return (ms / 1000).toFixed(2).padStart(6) + " s";
}

export function pct(rate) {
  return (rate * 100).toFixed(1).padStart(5) + " %";
}

function fila(nombre, exito, tiempo) {
  const enviados = exito.values.passes + exito.values.fails;
  const t = (clave) => (tiempo ? seg(tiempo.values[clave]) : "-").padStart(10);
  return (
    "  " + nombre.padEnd(36) + String(enviados).padStart(9) + String(exito.values.passes).padStart(8) +
    pct(exito.values.rate).padStart(8) + t("med") + t("p(90)") + t("p(95)") + t("max")
  );
}

// Tabla por PDF y total. Devuelve las lineas y las metricas totales.
export function tablaPorPdf(data) {
  const m = data.metrics;
  const l = [];
  l.push(
    "  " + "PDF".padEnd(36) + "enviados".padStart(9) + "OK".padStart(8) + "% OK".padStart(8) +
    "mediana".padStart(10) + "p90".padStart(10) + "p95".padStart(10) + "maximo".padStart(10)
  );
  l.push("  " + "-".repeat(ANCHO - 2));
  for (const pdf of PDFS) {
    const e = m[`exito_${pdf.clave}`];
    if (e) l.push(fila(pdf.corto, e, m[`tiempo_${pdf.clave}`]));
  }
  l.push("  " + "-".repeat(ANCHO - 2));
  const total = { tiempo: m.tiempo_por_documento, exito: m.exito_por_documento };
  if (total.exito) l.push(fila("TOTAL", total.exito, total.tiempo));
  return { lineas: l, total };
}

export function lineaCodigos(data) {
  const m = data.metrics;
  return CODIGOS.map((c) => [c === "0" ? "sin respuesta" : c, m[`codigo_${c}`]])
    .concat([["otros", m.codigo_otros]])
    .filter(([, v]) => v && v.values.count > 0)
    .map(([c, v]) => `${c} -> ${v.values.count}`)
    .join("     ");
}

// Una linea por umbral del SLO (thresholds de k6), con si se cumplio.
export function lineasSlo(data) {
  const l = ["  SLO (thresholds de k6)", "  " + "-".repeat(60)];
  let cumple = true;
  for (const [metrica, m] of Object.entries(data.metrics)) {
    for (const [umbral, r] of Object.entries(m.thresholds || {})) {
      cumple = cumple && r.ok;
      l.push("  " + `${metrica} ${umbral}`.padEnd(46) + (r.ok ? "cumple" : "NO CUMPLE"));
    }
  }
  l.push("  " + (cumple ? "SLO CUMPLIDO" : "SLO INCUMPLIDO (k6 termina con codigo 99)"));
  return l;
}

// "MEJOR" / "peor" / "igual"; menor es mejor salvo que se indique lo contrario.
function comparar(nuestro, profesor, mayorEsMejor) {
  if (Math.abs(nuestro - profesor) < 1e-9) return "igual";
  const mejor = mayorEsMejor ? nuestro > profesor : nuestro < profesor;
  return mejor ? "MEJOR" : "peor";
}

export function encabezadoComparacion() {
  return [
    "  " + "COMPARACION CON EL PROFESOR".padEnd(24) + "nosotros".padStart(14) + "profesor".padStart(14),
    "  " + "-".repeat(60),
  ];
}

export function filaComparacion(nombre, nuestro, profesor, formato, mayorEsMejor) {
  return (
    "  " + nombre.padEnd(24) + formato(nuestro).padStart(14) + formato(profesor).padStart(14) +
    "   " + comparar(nuestro, profesor, mayorEsMejor)
  );
}

export const formato = {
  num: (v) => String(Math.round(v)),
  rps: (v) => v.toFixed(2) + " req/s",
  porc: (v) => v.toFixed(2) + " %",
  s: (v) => v.toFixed(2) + " s",
};
