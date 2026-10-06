// Carga fija del TP con k6 (modelo abierto): el mismo perfil que la prueba de
// Vegeta del profesor, 50 req/s durante 30 s rotando los 4 PDFs en orden, con
// timeout de cliente de 30 s. A diferencia del spike, cada request sale a su
// hora aunque las anteriores no hayan respondido.
//
//   k6 run tests/stress/carga_fija.js
//   k6 run -e RATE=25 tests/stress/carga_fija.js
//
// Limitacion: cada VU de k6 carga los 4 PDFs (13,7 MB). Con requests que
// esperan ~30 s hacen falta ~1.500 VUs a la vez y k6 no llega a crearlos:
// descarta iteraciones (dropped_iterations). Aca se cuentan como fallas y
// se avisa. Para la medicion de la carga fija usar Vegeta (vegeta.sh, o su
// imagen de tests/stress/docker para correrlo dentro de la red de Docker).
// Variables: BASE_URL, RATE, DURACION, TIMEOUT, MODO (crudo | multipart).

import exec from "k6/execution";
import {
  ANCHO, BASE_URL, HOSTS, MODO, PDFS, encabezadoComparacion, enviar, filaComparacion,
  formato, lineaCodigos, pct, registrar, tablaPorPdf,
} from "./comun.js";

const RATE = Number(__ENV.RATE || 50);
const DURACION = __ENV.DURACION || "30s";
const TIMEOUT = __ENV.TIMEOUT || "30s";

export const options = {
  hosts: HOSTS,
  insecureSkipTLSVerify: true,
  scenarios: {
    carga_fija: {
      executor: "constant-arrival-rate",
      rate: RATE,
      timeUnit: "1s",
      duration: DURACION,
      // Como Vegeta: tantos clientes como hagan falta para no frenar la tasa,
      // aunque se acumulen requests esperando respuesta (hasta 30 s x 50/s).
      preAllocatedVUs: 200,
      maxVUs: 2000,
    },
  },
  summaryTrendStats: ["avg", "med", "p(90)", "p(95)", "max"],
};

// Benchmark de la catedra con Vegeta (consigna del TP, seccion B).
const PROFESOR = {
  throughput: 16.65,
  exitosas: 998,
  exito: 66.53,
  timeouts: 501,
  p50: 14.89,
};

export default function () {
  // Rotacion en orden, como los targets de Vegeta.
  const pdf = PDFS[exec.scenario.iterationInTest % PDFS.length];
  const res = enviar(pdf, TIMEOUT);
  // Latencias de todos los requests, como Vegeta: un timeout cuenta 30 s.
  registrar(pdf, res, true);
}

export function handleSummary(data) {
  const duracion = data.state.testRunDurationMs / 1000;
  const l = [];
  l.push("");
  l.push("=".repeat(ANCHO));
  l.push(`  RESULTADO DE LA CARGA FIJA   POST /extract   ${RATE} req/s durante ${DURACION}, timeout ${TIMEOUT}, ${duracion.toFixed(1)} s, body ${MODO}`);
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

  // Iteraciones que k6 no llego a lanzar: para Vegeta serian requests
  // enviados sin respuesta, asi que cuentan como fallas.
  const descartadas = data.metrics.dropped_iterations
    ? data.metrics.dropped_iterations.values.count
    : 0;
  const enviados = e.values.passes + e.values.fails;
  const programadas = enviados + descartadas;
  const tasaExito = programadas ? e.values.passes / programadas : 0;
  const timeouts = data.metrics.codigo_0 ? data.metrics.codigo_0.values.count : 0;
  // Como el "throughput" de Vegeta: respuestas exitosas por segundo de prueba.
  const throughput = e.values.passes / duracion;
  l.push("");
  l.push(`  Respuestas por codigo HTTP:   ${lineaCodigos(data)}`);
  l.push(`  Throughput efectivo (200):    ${throughput.toFixed(2)} req/s`);
  l.push(`  EXITO GLOBAL:                 ${pct(tasaExito).trim()}   (${e.values.passes} de ${programadas} programadas con 200 OK)`);
  if (descartadas > 0) {
    l.push(`  AVISO: k6 descarto ${descartadas} iteraciones por falta de VUs; se cuentan como fallas.`);
    l.push("         Para comparar con el profesor usar Vegeta (ver tests/stress/README.md).");
  }
  l.push("  Latencias de todos los requests, como Vegeta (un timeout cuenta su duracion).");

  const perfilDelProfesor = RATE === 50 && DURACION === "30s" && TIMEOUT === "30s";
  l.push("");
  l.push(...encabezadoComparacion());
  l.push(filaComparacion("Throughput efectivo", throughput, PROFESOR.throughput, formato.rps, true));
  l.push(filaComparacion("Peticiones exitosas", e.values.passes, PROFESOR.exitosas, formato.num, true));
  l.push(filaComparacion("Tasa de exito", tasaExito * 100, PROFESOR.exito, formato.porc, true));
  l.push(filaComparacion("Timeouts (codigo 0)", timeouts, PROFESOR.timeouts, formato.num, false));
  if (t) l.push(filaComparacion("Latencia p50", t.values.med / 1000, PROFESOR.p50, formato.s, false));
  if (!perfilDelProfesor) {
    l.push("");
    l.push("  Aviso: el perfil no es el del profesor (50 req/s, 30 s, timeout 30 s); la comparacion no es valida.");
  }
  l.push("=".repeat(ANCHO));
  l.push("");

  return { stdout: l.join("\n") };
}
