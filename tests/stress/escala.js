// Carga cerrada constante para medir cuanto rinde el servicio segun la
// cantidad de replicas: VUS usuarios mandan los 4 PDFs en ronda durante DUR.
// Con pocos usuarios por replica no hay rechazos ni colas largas: mide la
// capacidad, no el comportamiento bajo sobrecarga (para eso, spike y Vegeta).
//
//   docker compose up -d --scale extract=2
//   docker run --rm --network pdf-extractext-tp_default -v "${PWD}/tests/stress:/scripts:ro" grafana/k6 run -e BASE_URL=http://traefik -e VUS=6 /scripts/escala.js

import { PDFS, HOSTS, enviar, registrar } from "./comun.js";

export const options = {
  hosts: HOSTS,
  scenarios: {
    escala: {
      executor: "constant-vus",
      vus: Number(__ENV.VUS || 3),
      duration: __ENV.DUR || "60s",
      gracefulStop: "0s",
    },
  },
};

export default function () {
  const pdf = PDFS[(__VU + __ITER) % PDFS.length];
  registrar(pdf, enviar(pdf, "60s"), false);
}

export function handleSummary(data) {
  const ok = data.metrics.codigo_200 ? data.metrics.codigo_200.values.count : 0;
  const segundos = data.state.testRunDurationMs / 1000;
  const t = data.metrics.tiempo_por_documento ? data.metrics.tiempo_por_documento.values : {};
  const s = (ms) => ((ms || 0) / 1000).toFixed(2) + " s";
  return {
    stdout:
      `RESULTADO ok=${ok} rps=${(ok / segundos).toFixed(2)} ` +
      `p50=${s(t.med)} p95=${s(t["p(95)"])}\n`,
  };
}
