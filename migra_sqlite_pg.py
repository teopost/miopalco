"""Porta i dati di data/crm.db (SQLite) nel database PostgreSQL di DATABASE_URL.

    docker compose run --rm miopalco python3 migra_sqlite_pg.py [--sqlite data/crm.db] [--force]

Cosa fa, in una transazione sola (o tutto o niente):
  1. controlla il file SQLite (integrity_check, foreign_key_check) e lo apre
     in sola lettura: il crm.db resta com'e';
  2. crea lo schema su PostgreSQL con lo stesso init_db dell'app;
  3. svuota le tabelle (init_db mette i modelli di partenza) e copia tutte le
     righe, id compresi, nell'ordine delle foreign key;
  4. rimette i contatori degli id dopo l'id piu' alto;
  5. rilegge tutto da PostgreSQL e lo confronta riga per riga con SQLite.
     Alla prima differenza annulla e non scrive niente.

Se PostgreSQL contiene gia' dei dati si ferma, a meno di --force (che li
sostituisce con quelli di SQLite).
"""

import argparse
import math
import os
import sqlite3
import sys

import psycopg

import app
import pgcompat


def tabelle_sqlite(src):
    return [r[0] for r in src.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )]


def ordine_fk(src, tabelle):
    """Prima le tabelle a cui le altre puntano."""
    dipende = {t: {r[2] for r in src.execute(f"PRAGMA foreign_key_list({t})") if r[2] != t} for t in tabelle}
    ordine, fatte = [], set()
    while len(ordine) < len(tabelle):
        pronte = [t for t in tabelle if t not in fatte and dipende[t] <= fatte]
        if not pronte:
            raise SystemExit("Foreign key circolari: %s" % (set(tabelle) - fatte))
        for t in pronte:
            ordine.append(t)
            fatte.add(t)
    return ordine


def uguali(a, b):
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, float) or isinstance(b, float):
        return math.isclose(float(a), float(b), rel_tol=0, abs_tol=0)
    return a == b


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sqlite", default=app.DB_PATH)
    ap.add_argument("--force", action="store_true", help="sostituisce i dati gia' presenti in PostgreSQL")
    args = ap.parse_args()

    if not app.DATABASE_URL:
        raise SystemExit("DATABASE_URL non impostata: non so dove copiare i dati.")
    if not os.path.exists(args.sqlite):
        raise SystemExit("File SQLite non trovato: %s" % args.sqlite)

    src = sqlite3.connect("file:%s?mode=ro" % args.sqlite, uri=True)
    if src.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise SystemExit("integrity_check fallito su %s: non migro un file danneggiato." % args.sqlite)
    orfani = src.execute("PRAGMA foreign_key_check").fetchall()
    if orfani:
        raise SystemExit("Righe con foreign key rotte in SQLite (PostgreSQL le rifiuterebbe): %r" % orfani[:20])
    tabelle = tabelle_sqlite(src)

    # Lo schema: lo stesso init_db che l'app fa a ogni avvio.
    with psycopg.connect(app.DATABASE_URL) as pg:
        gia = {}
        for t in tabelle:
            esiste = pg.execute("SELECT to_regclass(%s)", (t,)).fetchone()[0]
            if esiste:
                gia[t] = pg.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
    dati = {t: n for t, n in gia.items() if n and t not in ("app_templates", "app_settings")}
    if dati and not args.force:
        raise SystemExit("PostgreSQL contiene gia' dei dati (%s): usa --force per sostituirli." % dati)
    app.init_db()

    ordine = ordine_fk(src, tabelle)
    totale = 0
    with psycopg.connect(app.DATABASE_URL) as pg:
        with pg.transaction():
            pg.execute("TRUNCATE %s RESTART IDENTITY CASCADE" % ", ".join('"%s"' % t for t in tabelle))
            colonne = {}
            for t in ordine:
                cols = [r[1] for r in src.execute(f"PRAGMA table_info({t})")]
                pg_cols = {r[0] for r in pg.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = current_schema() AND table_name = %s", (t,))}
                mancano = set(cols) - pg_cols
                if mancano:
                    raise SystemExit("In PostgreSQL mancano colonne di %s: %s" % (t, mancano))
                colonne[t] = cols
                righe = src.execute("SELECT %s FROM %s" % (", ".join(cols), t)).fetchall()
                if righe:
                    with pg.cursor() as cur:
                        cur.executemany(
                            'INSERT INTO "%s" (%s) VALUES (%s)'
                            % (t, ", ".join('"%s"' % c for c in cols), ", ".join(["%s"] * len(cols))),
                            righe,
                        )
                totale += len(righe)
                print("  %-22s %5d righe" % (t, len(righe)))

            # I contatori degli id: le righe sono entrate con il loro id.
            conn = pgcompat.Connection(None, pg)
            pgcompat.sync_sequences(conn)
            conn._raw = None  # la connessione e' nostra, non del pool
            # Con AUTOINCREMENT SQLite non riusa mai l'id di una riga
            # cancellata: il contatore sta in sqlite_sequence e puo' essere
            # piu' avanti del MAX(id). Si riparte da li', non da MAX(id).
            seq = dict(src.execute("SELECT name, seq FROM sqlite_sequence").fetchall()) \
                if src.execute("SELECT 1 FROM sqlite_master WHERE name = 'sqlite_sequence'").fetchone() else {}
            for t, valore in seq.items():
                if t in colonne and "id" in colonne[t] and valore:
                    pg.execute(
                        "SELECT setval(pg_get_serial_sequence(%s, 'id'), "
                        "GREATEST(%s, (SELECT COALESCE(MAX(id), 0) FROM " + '"' + t + '"' + ")) + 1, false)",
                        (t, valore),
                    )

            # La verifica: tutto quello che c'e' in SQLite, uguale in PostgreSQL.
            for t in ordine:
                cols = colonne[t]
                chiave = ", ".join(str(i + 1) for i in range(len(cols)))
                a = src.execute("SELECT %s FROM %s ORDER BY %s" % (", ".join(cols), t, chiave)).fetchall()
                b = pg.execute('SELECT %s FROM "%s" ORDER BY %s'
                               % (", ".join('"%s"' % c for c in cols), t, chiave)).fetchall()
                if len(a) != len(b):
                    raise SystemExit("%s: %d righe in SQLite, %d in PostgreSQL. Annullato." % (t, len(a), len(b)))
                # Gli ordinamenti dei testi possono differire: si confronta per id
                # quando c'e', altrimenti per tupla intera.
                if "id" in cols:
                    i = cols.index("id")
                    a = sorted(a, key=lambda r: r[i])
                    b = sorted(b, key=lambda r: r[i])
                else:
                    a = sorted(a, key=repr)
                    b = sorted(b, key=repr)
                for ra, rb in zip(a, b):
                    if len(ra) != len(rb) or not all(uguali(x, y) for x, y in zip(ra, rb)):
                        raise SystemExit("%s: riga diversa\n  SQLite:     %r\n  PostgreSQL: %r\nAnnullato."
                                         % (t, ra, rb))
        pg.execute("ANALYZE")
    src.close()
    print("Copiate e verificate %d righe in %d tabelle." % (totale, len(tabelle)))


if __name__ == "__main__":
    sys.exit(main())
