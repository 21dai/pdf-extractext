# Decisiones de arquitectura (ADRs)

Cada archivo registra una decision: el contexto, que se decidio, que
alternativas se midieron y que consecuencias tiene. Las mediciones completas
estan en [INFORME-TP.md](../INFORME-TP.md).

| ADR | Decision |
|---|---|
| [0001](0001-contrato-de-extract.md) | `POST /extract` sin estado, body crudo o multipart, modo solo extractor |
| [0002](0002-motor-de-extraccion-y-markdown.md) | PDFium con su API cruda y Markdown por altura de letra, detras de `PdfExtractor` |
| [0003](0003-contrapresion.md) | Cola de 60 por replica (el PDF mas liviano primero), tiempo util de 25 s con margen pesimista y 503 con `Retry-After` |
| [0004](0004-workers-y-replicas.md) | 5 replicas de 1 CPU y 1 GB, 1 proceso cada una, round robin en Traefik |
| [0005](0005-tolerancia-a-fallos.md) | Reinicio automatico, reintentos de Traefik y apagado ordenado |
| [0006](0006-metodologia-de-medicion.md) | Medir dentro de la red de Docker, con Vegeta real e intercalando |
| [0007](0007-metricas-propias.md) | Metricas propias de cada replica en `/metrics`, con un observador de la compuerta |
