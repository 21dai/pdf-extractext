"""Simulacion del spike del profesor (modelo cerrado, 100 VUs, 10s/20s/10s).

5 replicas, reparto round robin (Traefik wrr), cada replica con 1 CPU.
Politicas por replica:
  fifo          una extraccion por vez, por orden de llegada
  sjf           una por vez, primero el PDF mas barato (sin limite)
  sjf_edad:N    como sjf, pero el que ya espero N segundos pasa primero
  hrrn          Highest Response Ratio Next
  ps:k          k extracciones a la vez repartiendo la CPU
Costos de CPU por PDF medidos (contenedor de 1 CPU, informe Fase 0), en s.
`escala` los multiplica: 1 = un nucleo por replica; 2,2 = la notebook con
5 replicas (informe, experimento 14).

    python tests/stress/simulacion_spike.py 1.0 fifo,sjf_edad:7.5
    python tests/stress/simulacion_spike.py 2.2 fifo,sjf_edad:7.5
"""

import heapq
import random
import statistics
import sys

COSTOS = {"scrum_guide": 0.053, "kanban": 0.214, "lean": 0.178, "scrum_manager": 0.352}
PDFS = list(COSTOS)


def vus_objetivo(t):
    if t < 10:
        return 100 * t / 10
    if t < 30:
        return 100
    if t < 40:
        return 100 * (40 - t) / 10
    return 0


def simular(politica, escala=1.0, replicas=5, semilla=1):
    rnd = random.Random(semilla)
    k = int(politica.split(":")[1]) if politica.startswith("ps") else 1
    # Estado por replica
    cola = [[] for _ in range(replicas)]  # esperando (llegada, costo, id)
    activos = [[] for _ in range(replicas)]  # para ps: [restante, id]
    ocupado = [None] * replicas  # para fifo/sjf: (fin, id)
    ultimo_t = [0.0] * replicas
    eventos = []  # (t, tipo, datos)
    req = {}  # id -> (vu, inicio, pdf)
    latencias, completados = [], 0
    rr = 0
    seq = 0
    vus_activos = set()

    def enviar(t, vu):
        nonlocal rr, seq
        pdf = rnd.choice(PDFS)
        costo = COSTOS[pdf] * escala
        seq += 1
        req[seq] = (vu, t, pdf)
        r = rr % replicas
        rr += 1
        llegar(t, r, seq, costo)

    def avanzar_ps(r, t):
        # reparte el tiempo transcurrido entre los activos
        if activos[r] and t > ultimo_t[r]:
            dt = (t - ultimo_t[r]) / len(activos[r])
            for a in activos[r]:
                a[0] -= dt
        ultimo_t[r] = t

    def programar_ps(r, t):
        if activos[r]:
            m = min(a[0] for a in activos[r])
            heapq.heappush(
                eventos, (t + m * len(activos[r]), "fin_ps", (r, ultimo_version[r]))
            )

    ultimo_version = [0] * replicas

    def llegar(t, r, rid, costo):
        if k > 1:
            avanzar_ps(r, t)
            if len(activos[r]) < k:
                activos[r].append([costo, rid])
            else:
                cola[r].append((t, costo, rid))
            ultimo_version[r] += 1
            programar_ps(r, t)
        else:
            cola[r].append((t, costo, rid))
            if ocupado[r] is None:
                arrancar(t, r)

    def arrancar(t, r):
        if not cola[r]:
            ocupado[r] = None
            return
        if politica == "sjf":
            item = min(cola[r], key=lambda x: (x[1], x[0]))
        elif politica.startswith("hrrn"):
            # Highest Response Ratio Next: (espera + costo) / costo, con peso w
            w = float(politica.split(":")[1]) if ":" in politica else 1.0
            item = max(cola[r], key=lambda x: (w * (t - x[0]) + x[1]) / x[1])
        elif politica.startswith("sjf_edad:"):
            limite = float(politica.split(":")[1])
            viejo = min(cola[r], key=lambda x: x[0])
            if t - viejo[0] >= limite:
                item = viejo
            else:
                item = min(cola[r], key=lambda x: (x[1], x[0]))
        else:
            item = cola[r][0]
        cola[r].remove(item)
        ocupado[r] = item[2]
        heapq.heappush(eventos, (t + item[1], "fin", (r, item[2])))

    def terminar(t, rid):
        nonlocal completados
        vu, inicio, _ = req.pop(rid)
        latencias.append(t - inicio)
        completados += 1
        # el VU sigue si todavia corresponde segun la rampa
        if vu in vus_activos and vu < vus_objetivo(t) + 0.5 and t < 40:
            enviar(t, vu)
        else:
            vus_activos.discard(vu)

    # VUs que arrancan durante la subida, uno cada 0,1 s
    for i in range(100):
        heapq.heappush(eventos, (i * 0.1, "vu", i))

    while eventos:
        t, tipo, dato = heapq.heappop(eventos)
        if tipo == "vu":
            vus_activos.add(dato)
            enviar(t, dato)
        elif tipo == "fin":
            r, rid = dato
            terminar(t, rid)
            arrancar(t, r)
        elif tipo == "fin_ps":
            r, version = dato
            if version != ultimo_version[r]:
                continue
            avanzar_ps(r, t)
            listos = [a for a in activos[r] if a[0] <= 1e-9]
            activos[r] = [a for a in activos[r] if a[0] > 1e-9]
            for a in listos:
                terminar(t, a[1])
            while cola[r] and len(activos[r]) < k:
                _, costo, rid = cola[r].pop(0)
                activos[r].append([costo, rid])
            ultimo_version[r] += 1
            programar_ps(r, t)

    lat = sorted(latencias)

    def q(p):
        return lat[min(len(lat) - 1, int(p * len(lat)))]

    dur = 40.0
    return completados, completados / dur, q(0.5), q(0.9), q(0.95), lat[-1]


if __name__ == "__main__":
    escala = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
    print(f"escala de costos x{escala}")
    print("profesor: 1037 req, 25.35 req/s, p50 1.88, p90 7.83, p95 8.80, max 13.94")
    for pol in sys.argv[2].split(",") if len(sys.argv) > 2 else ["fifo", "sjf"]:
        res = [simular(pol, escala, semilla=s) for s in range(5)]
        m = [statistics.median(x) for x in zip(*res)]
        print(
            f"{pol:12s} req={m[0]:5.0f}  rps={m[1]:5.2f}  p50={m[2]:5.2f}"
            f"  p90={m[3]:5.2f}  p95={m[4]:5.2f}  max={m[5]:5.2f}"
        )
