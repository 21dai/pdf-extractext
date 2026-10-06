# Vegeta en un contenedor, para correr la carga fija dentro de la red de Docker
# (en Windows, desde la PC el reenvio de puertos de Docker Desktop distorsiona
# la medicion). Binario oficial del release, con su checksum verificado.
FROM alpine:3.20

ARG VEGETA_VERSION=12.13.0

RUN apk add --no-cache bash \
    && cd /tmp \
    && wget -q "https://github.com/tsenart/vegeta/releases/download/v${VEGETA_VERSION}/vegeta_${VEGETA_VERSION}_linux_amd64.tar.gz" \
    && wget -q "https://github.com/tsenart/vegeta/releases/download/v${VEGETA_VERSION}/vegeta_${VEGETA_VERSION}_checksums.txt" \
    && grep "vegeta_${VEGETA_VERSION}_linux_amd64.tar.gz" "vegeta_${VEGETA_VERSION}_checksums.txt" | sha256sum -c - \
    && tar -xzf "vegeta_${VEGETA_VERSION}_linux_amd64.tar.gz" -C /usr/local/bin vegeta \
    && rm -f /tmp/vegeta_*

ENTRYPOINT ["vegeta"]
