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

import { check } from "k6";
import {
  ANCHO, BASE_URL, HOSTS, MODO, PDFS, encabezadoComparacion, enviar, filaComparacion,
  formato, lineaCodigos, pct, registrar, tablaPorPdf,
} from "./comun.js";

const VUS = Number(__ENV.VUS || 100);
const LOG = (__ENV.LOG || "0") === "1";

const ETAPAS = {
  subida: __ENV.SUBIDA || "10s",
  meseta: __ENV.MESETA || "20s",
  bajada: __ENV.BAJADA || "10s",
};

export const options = {
  hosts: HOSTS,
  insecureSkipTLSVerify: true, // certificado autofirmado de Traefik o de mkcert
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

export default function () {
  const pdf = PDFS[Math.floor(Math.random() * PDFS.length)];
  const res = enviar(pdf, "60s");
  // Las latencias se miden sobre las respuestas 200, como las del profesor:
  // un error inmediato no puede mejorar la mediana.
  const ok = registrar(pdf, res, false);
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

export function handleSummary(data) {
  const duracion = data.state.testRunDurationMs / 1000;
  const l = [];
  l.push("");
  l.push("=".repeat(ANCHO));
  l.push(`  RESULTADO DEL SPIKE   POST /extract   ${VUS} VUs (${ETAPAS.subida} / ${ETAPAS.meseta} / ${ETAPAS.bajada}), ${duracion.toFixed(1)} s, body ${MODO}`);
  l.push(`  ${BASE_URL}`);
  l.push("=".repeat(ANCHO));

  const { lineas, total } = tablaPorPdf(data);
  l.push(...lineas);
  const e = total.exito;
  const t = total.tiempo;
  if (!e) {
    l.push("  No se completo ningun request.");
    l.push("=".repeat(ANCHO));
    return { stdout: l.join("\n") + "\n" };
  }

  const enviados = e.values.passes + e.values.fails;
  // Throughput de respuestas 200: lo que el servicio efectivamente proceso.
  const throughput = e.values.passes / duracion;
  l.push("");
  l.push(`  Respuestas por codigo HTTP:   ${lineaCodigos(data)}`);
  l.push(`  Throughput (200 OK):          ${throughput.toFixed(2)} req/s`);
  l.push(`  EXITO GLOBAL:                 ${pct(e.values.rate).trim()}   (${e.values.passes} de ${enviados} con 200 OK)`);
  l.push("  Latencias calculadas sobre las respuestas 200.");

  const perfilDelProfesor =
    VUS === 100 && ETAPAS.subida === "10s" && ETAPAS.meseta === "20s" && ETAPAS.bajada === "10s";
  l.push("");
  l.push(...encabezadoComparacion());
  l.push(filaComparacion("Peticiones 200 OK", e.values.passes, PROFESOR.peticiones, formato.num, true));
  l.push(filaComparacion("Throughput", throughput, PROFESOR.throughput, formato.rps, true));
  l.push(filaComparacion("Tasa de error", (1 - e.values.rate) * 100, PROFESOR.error, formato.porc, false));
  if (t) {
    l.push(filaComparacion("Latencia p50", t.values.med / 1000, PROFESOR.p50, formato.s, false));
    l.push(filaComparacion("Latencia p90", t.values["p(90)"] / 1000, PROFESOR.p90, formato.s, false));
    l.push(filaComparacion("Latencia p95", t.values["p(95)"] / 1000, PROFESOR.p95, formato.s, false));
    l.push(filaComparacion("Latencia maxima", t.values.max / 1000, PROFESOR.max, formato.s, false));
  }
  if (!perfilDelProfesor) {
    l.push("");
    l.push("  Aviso: el perfil de carga no es el del profesor (100 VUs, 10s/20s/10s); la comparacion no es valida.");
  }
  l.push("=".repeat(ANCHO));
  l.push("");

  return { stdout: l.join("\n") };
}
