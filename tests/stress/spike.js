// Prueba spike del TP con Grafana k6 (modelo cerrado): reproduce el perfil del
// profesor y compara el resultado contra su benchmark al final.
//
//   k6 run tests/stress/spike.js                        (100 VUs, 10s/20s/10s)
//   k6 run -e LOG=1 tests/stress/spike.js               (+ una linea por request)
//   k6 run -e MODO=multipart tests/stress/spike.js      (multipart en vez de body crudo)
//   k6 run --out "web-dashboard=export=reporte.html" tests/stress/spike.js
//
// Variables: BASE_URL, VUS, SUBIDA, MESETA, BAJADA, MODO (crudo | multipart), LOG.
// Contrato que se mide: POST /extract -> 200 {"content": "...", "page_count": N}.

import http from "k6/http";
import { Trend, Rate, Counter } from "k6/metrics";
import { check } from "k6";

const BASE_URL = __ENV.BASE_URL || "https://extract.universidad.localhost";
const VUS = Number(__ENV.VUS || 100);
const MODO = __ENV.MODO || "crudo";
const LOG = (__ENV.LOG || "0") === "1";

const ETAPAS = {
  subida: __ENV.SUBIDA || "10s",
  meseta: __ENV.MESETA || "20s",
  bajada: __ENV.BAJADA || "10s",
};

export const options = {
  insecureSkipTLSVerify: true, // certificado local de mkcert
  stages: [
    { duration: ETAPAS.subida, target: VUS },
    { duration: ETAPAS.meseta, target: VUS },
    { duration: ETAPAS.bajada, target: 0 },
  ],
  summaryTrendStats: ["avg", "med", "p(90)", "p(95)", "max"],
};

// Benchmark de la catedra con este mismo perfil (consigna del TP, seccion A).
const PROFESOR = {
  peticiones: 1037,
  throughput: 25.35,
  error: 0,
  p50: 1.88,
  p90: 7.83,
  p95: 8.8,
  max: 13.94,
};

const PDFS = [
  { clave: "scrum_guide", nombre: "2020-Scrum-Guide-Spanish-Latin-South-American.pdf", corto: "Scrum Guide (16 pag, 0,3 MB)" },
  { clave: "kanban", nombre: "Essential-Kanban-Condensed-Spanish.pdf", corto: "Essential Kanban (90 pag, 8,9 MB)" },
  { clave: "lean", nombre: "Filosofia Lean.pdf", corto: "Filosofia Lean (42 pag, 0,7 MB)" },
  { clave: "scrum_manager", nombre: "scrum_manager_historias_usuario.pdf", corto: "Scrum Manager (62 pag, 3,8 MB)" },
];

// Se cargan en el init context (una vez por VU), como en el script original.
for (const pdf of PDFS) {
  pdf.bytes = open(`./pdfs/${pdf.nombre}`, "b");
  pdf.tiempo = new Trend(`tiempo_${pdf.clave}`, true);
  pdf.exito = new Rate(`exito_${pdf.clave}`);
}
const tiempoTotal = new Trend("tiempo_por_documento", true);
const exitoTotal = new Rate("exito_por_documento");
// Contadores por codigo HTTP (k6 no muestra contadores con tags en el resumen).
const CODIGOS = ["200", "400", "413", "422", "429", "503", "504", "0"];
const porCodigo = {};
for (const c of CODIGOS) porCodigo[c] = new Counter(`codigo_${c}`);
const otrosCodigos = new Counter("codigo_otros");

function enviar(pdf) {
  const url = `${BASE_URL}/extract`;
  const params = { tags: { pdf: pdf.corto }, timeout: "60s" };
  if (MODO === "multipart") {
    return http.post(url, { file: http.file(pdf.bytes, pdf.nombre, "application/pdf") }, params);
  }
  params.headers = { "Content-Type": "application/pdf" };
  return http.post(url, pdf.bytes, params);
}

export default function () {
  const pdf = PDFS[Math.floor(Math.random() * PDFS.length)];
  const res = enviar(pdf);

  const ok = res.status === 200;
  pdf.tiempo.add(res.timings.duration);
  pdf.exito.add(ok);
  tiempoTotal.add(res.timings.duration);
  exitoTotal.add(ok);
  (porCodigo[String(res.status)] || otrosCodigos).add(1);
  check(res, {
    "status 200": () => ok,
    "respuesta con content y page_count": (r) =>
      ok && typeof r.body === "string" && r.body.includes('"content"') && r.body.includes('"page_count"'),
  });

  if (LOG) {
    const estado = ok ? "OK       " : `FALLO ${String(res.status).padEnd(3)}`;
    const segundos = (res.timings.duration / 1000).toFixed(2).padStart(6);
    console.log(`${estado} ${segundos} s   ${pdf.corto}   [usuario ${__VU}]`);
  }
}

// ---------- Resumen en la terminal ----------

function seg(ms) {
  return (ms / 1000).toFixed(2).padStart(6) + " s";
}

function pct(rate) {
  return (rate * 100).toFixed(1).padStart(5) + " %";
}

function fila(nombre, exito, tiempo) {
  const enviados = exito.values.passes + exito.values.fails;
  return (
    "  " + nombre.padEnd(36) + String(enviados).padStart(9) + String(exito.values.passes).padStart(8) +
    pct(exito.values.rate).padStart(8) + seg(tiempo.values.med).padStart(10) + seg(tiempo.values["p(90)"]).padStart(10) +
    seg(tiempo.values["p(95)"]).padStart(10) + seg(tiempo.values.max).padStart(10)
  );
}

// Devuelve "mejor" / "peor" / "igual"; menor es mejor salvo que se indique lo contrario.
function comparar(nuestro, profesor, mayorEsMejor) {
  if (Math.abs(nuestro - profesor) < 1e-9) return "igual";
  const mejor = mayorEsMejor ? nuestro > profesor : nuestro < profesor;
  return mejor ? "MEJOR" : "peor";
}

function filaComparacion(nombre, nuestro, profesor, formato, mayorEsMejor) {
  return (
    "  " + nombre.padEnd(24) + formato(nuestro).padStart(14) + formato(profesor).padStart(14) +
    "   " + comparar(nuestro, profesor, mayorEsMejor)
  );
}

export function handleSummary(data) {
  const m = data.metrics;
  const duracion = data.state.testRunDurationMs / 1000;
  const l = [];
  const ancho = 102;
  l.push("");
  l.push("=".repeat(ancho));
  l.push(`  RESULTADO DEL SPIKE   POST /extract   ${VUS} VUs (${ETAPAS.subida} / ${ETAPAS.meseta} / ${ETAPAS.bajada}), ${duracion.toFixed(1)} s, body ${MODO}`);
  l.push(`  ${BASE_URL}`);
  l.push("=".repeat(ancho));
  l.push(
    "  " + "PDF".padEnd(36) + "enviados".padStart(9) + "OK".padStart(8) + "% OK".padStart(8) +
    "mediana".padStart(10) + "p90".padStart(10) + "p95".padStart(10) + "maximo".padStart(10)
  );
  l.push("  " + "-".repeat(ancho - 2));

  for (const pdf of PDFS) {
    const t = m[`tiempo_${pdf.clave}`];
    const e = m[`exito_${pdf.clave}`];
    if (t && e) l.push(fila(pdf.corto, e, t));
  }

  const t = m.tiempo_por_documento;
  const e = m.exito_por_documento;
  l.push("  " + "-".repeat(ancho - 2));
  if (!t || !e) {
    l.push("  No se completo ningun request.");
    l.push("=".repeat(ancho));
    return { stdout: l.join("\n") + "\n" };
  }

  const enviados = e.values.passes + e.values.fails;
  const throughput = enviados / duracion;
  l.push(fila("TOTAL", e, t));
  l.push("");
  const codigos = CODIGOS.map((c) => [c === "0" ? "sin respuesta" : c, m[`codigo_${c}`]])
    .concat([["otros", m.codigo_otros]])
    .filter(([, v]) => v && v.values.count > 0)
    .map(([c, v]) => `${c} -> ${v.values.count}`)
    .join("     ");
  l.push(`  Respuestas por codigo HTTP:   ${codigos}`);
  l.push(`  Throughput:                   ${throughput.toFixed(2)} req/s`);
  l.push(`  EXITO GLOBAL:                 ${pct(e.values.rate).trim()}   (${e.values.passes} de ${enviados} con 200 OK)`);

  const perfilDelProfesor =
    VUS === 100 && ETAPAS.subida === "10s" && ETAPAS.meseta === "20s" && ETAPAS.bajada === "10s";
  l.push("");
  l.push("  " + "COMPARACION CON EL PROFESOR".padEnd(24) + "nosotros".padStart(14) + "profesor".padStart(14));
  l.push("  " + "-".repeat(60));
  const num = (v) => String(Math.round(v));
  const rps = (v) => v.toFixed(2) + " req/s";
  const porc = (v) => v.toFixed(2) + " %";
  const s = (v) => v.toFixed(2) + " s";
  l.push(filaComparacion("Peticiones", enviados, PROFESOR.peticiones, num, true));
  l.push(filaComparacion("Throughput", throughput, PROFESOR.throughput, rps, true));
  l.push(filaComparacion("Tasa de error", (1 - e.values.rate) * 100, PROFESOR.error, porc, false));
  l.push(filaComparacion("Latencia p50", t.values.med / 1000, PROFESOR.p50, s, false));
  l.push(filaComparacion("Latencia p90", t.values["p(90)"] / 1000, PROFESOR.p90, s, false));
  l.push(filaComparacion("Latencia p95", t.values["p(95)"] / 1000, PROFESOR.p95, s, false));
  l.push(filaComparacion("Latencia maxima", t.values.max / 1000, PROFESOR.max, s, false));
  if (!perfilDelProfesor) {
    l.push("");
    l.push("  Aviso: el perfil de carga no es el del profesor (100 VUs, 10s/20s/10s); la comparacion no es valida.");
  }
  l.push("=".repeat(ancho));
  l.push("");

  return { stdout: l.join("\n") };
}
