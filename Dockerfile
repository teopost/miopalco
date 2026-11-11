# MioPalco — gestionale live per la band.
# L'app usa la libreria standard di Python piu' pywebpush (le notifiche push)
# e psycopg (PostgreSQL, il database del compose). Vedi requirements.txt.

FROM python:3.12-slim

WORKDIR /app

# Prima le dipendenze e poi il codice: requirements.txt cambia una volta
# ogni tanto, app.py dieci volte al giorno, e cosi' il livello con
# l'installazione resta in cache fra un deploy e l'altro.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# pg_dump, per la copia di sicurezza che l'app fa prima di una cancellazione
# che non si puo' disfare (copia_di_sicurezza) quando i dati stanno in
# PostgreSQL. Stessa versione maggiore del server (postgres:17 nel compose).
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client-17 \
    && rm -rf /var/lib/apt/lists/*

# Senza questa, Python tiene lo stdout in un buffer da blocchi e "docker logs"
# resta vuoto per ore: gli avvisi (compresi quelli delle notifiche Telegram
# che non partono) si vedrebbero solo al riavvio del container.
ENV PYTHONUNBUFFERED=1

COPY app.py pgcompat.py migra_sqlite_pg.py import_excel.py geocode_venues.py ./
COPY static/ ./static/
# La pagina di presentazione: l'app la mostra su "/" a chi non ha fatto
# l'accesso. E' la stessa che GitHub Pages pubblica dalla cartella docs/.
COPY docs/index.html docs/icon-192.png ./docs/
COPY docs/img/ ./docs/img/
RUN mkdir -p /app/data

# Niente utente dedicato: /app/data è un bind mount sulla cartella data/ del
# host (vedi compose.yaml), il cui proprietario è l'utente del host, non uno
# scelto qui in build. Con Docker rootless in particolare, un utente fisso
# nel container spesso non corrisponde a chi possiede quei file sul host e
# la scrittura sul database viene rifiutata — restare root nel container
# evita questa intera classe di problemi di permessi.
EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8765/', timeout=3)" || exit 1

CMD ["python3", "app.py", "8765"]
