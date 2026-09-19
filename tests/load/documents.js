// Prueba de carga de la API de documentos con k6 (https://k6.io).
//
// Uso (con la API levantada en Docker):
//   k6 run tests/load/documents.js
//   k6 run -e BASE_URL=http://localhost:8000 -e VUS=20 -e DURATION=1m tests/load/documents.js
//
// Cada iteracion sube un PDF distinto (el service rechaza checksums repetidos
// con 400), lo lee por id y consulta /health. Los umbrales hacen que k6
// termine con codigo de salida distinto de cero si no se cumplen.

import http from "k6/http";
import { check, group } from "k6";
import { Trend } from "k6/metrics";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
const DOCUMENTS_URL = `${BASE_URL}/api/v1/documents`;

// Latencia por endpoint, para ver cada uno por separado en el resumen.
const createLatency = new Trend("latencia_crear_documento", true);
const readLatency = new Trend("latencia_leer_documento", true);
const healthLatency = new Trend("latencia_health", true);

export const options = {
  vus: Number(__ENV.VUS || 10),
  duration: __ENV.DURATION || "30s",
  thresholds: {
    http_req_failed: ["rate<0.01"],
    latencia_crear_documento: ["p(95)<500"],
    latencia_leer_documento: ["p(95)<200"],
    latencia_health: ["p(95)<100"],
  },
};

// Mismo PDF minimo que tests/support/pdf.py, con un texto unico por
// iteracion para que el checksum no se repita.
function buildPdf(text) {
  const escaped = text
    .replace(/\\/g, "\\\\")
    .replace(/\(/g, "\\(")
    .replace(/\)/g, "\\)");
  const stream = `BT\n/F1 18 Tf\n50 100 Td\n(${escaped}) Tj\nET\n`;
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] " +
      "/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
    `<< /Length ${stream.length} >>\nstream\n${stream}endstream`,
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
  ];

  let pdf = "%PDF-1.4\n";
  const offsets = [];
  objects.forEach((obj, index) => {
    offsets.push(pdf.length);
    pdf += `${index + 1} 0 obj\n${obj}\nendobj\n`;
  });

  const startxref = pdf.length;
  pdf += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  offsets.forEach((offset) => {
    pdf += `${String(offset).padStart(10, "0")} 00000 n \n`;
  });
  pdf += `trailer\n<< /Root 1 0 R /Size ${objects.length + 1} >>\nstartxref\n${startxref}\n%%EOF\n`;
  return pdf;
}

export default function () {
  const label = `carga vu${__VU} iter${__ITER}`;
  let documentId = null;

  group("crear documento", () => {
    const res = http.post(DOCUMENTS_URL, {
      name: label,
      file: http.file(buildPdf(label), `${label}.pdf`, "application/pdf"),
    });
    createLatency.add(res.timings.duration);
    const ok = check(res, {
      "POST devuelve 201": (r) => r.status === 201,
      "POST devuelve el texto extraido": (r) => r.json("extracted_text") === label,
    });
    if (ok) {
      documentId = res.json("id");
    }
  });

  if (documentId !== null) {
    group("leer documento", () => {
      const res = http.get(`${DOCUMENTS_URL}/${documentId}`);
      readLatency.add(res.timings.duration);
      check(res, { "GET devuelve 200": (r) => r.status === 200 });
    });
  }

  group("health", () => {
    const res = http.get(`${BASE_URL}/health`);
    healthLatency.add(res.timings.duration);
    check(res, { "health devuelve 200": (r) => r.status === 200 });
  });
}
