"""MioPalco su PostgreSQL, con lo stesso codice scritto per SQLite.

L'app e' nata su SQLite e ha piu' di quattrocento query scritte nel suo
dialetto: i segnaposto "?", INSERT OR IGNORE, PRAGMA table_info per le
migrazioni, cursor.lastrowid, le righe che si leggono sia per nome sia per
posizione. Riscriverle tutte voleva dire due app da tenere allineate. Questo
modulo invece da' a PostgreSQL la faccia di una connessione sqlite3, e
traduce al volo solo quello che serve:

  - "?"                          -> "%s" (e "%" -> "%%" quando ci sono parametri)
  - INSERT OR IGNORE INTO ...    -> INSERT INTO ... ON CONFLICT DO NOTHING
  - INSERT in una tabella con id -> ... RETURNING id, per cursor.lastrowid
  - PRAGMA table_info(t)         -> le colonne lette da information_schema
  - PRAGMA foreign_keys, BEGIN, COMMIT dentro executescript -> ignorati
  - CREATE/ALTER TABLE: INTEGER -> BIGINT, REAL -> DOUBLE PRECISION,
    INTEGER PRIMARY KEY [AUTOINCREMENT] -> BIGINT IDENTITY
  - le eccezioni tornano sqlite3.IntegrityError / sqlite3.OperationalError

Due cose non si traducono, si preparano nel database (prepare()):
  - la collation "nocase", cosi' "ORDER BY name COLLATE NOCASE" resta com'e';
  - round(double precision, integer), che SQLite ha e PostgreSQL no.

E i valori tornano come li darebbe sqlite3: i booleani come 0/1, i numeric
come int o float, mai Decimal (che json.dumps non sa scrivere).

Si attiva con DATABASE_URL (vedi app.get_conn): senza, l'app resta su SQLite.
"""

import re
import sqlite3
import threading
from datetime import date, datetime

import psycopg
from psycopg.adapt import Dumper, Loader
from psycopg_pool import ConnectionPool


# --- i valori, nei due versi -------------------------------------------

class _BoolDumper(Dumper):
    # SQLite non ha booleani: True e' 1. Le colonne "booleane" sono INTEGER.
    oid = psycopg.postgres.types["int8"].oid

    def dump(self, obj):
        return b"1" if obj else b"0"


class _DateDumper(Dumper):
    # Come l'adattatore di default di sqlite3: la data in testo ISO. Le
    # colonne delle date sono TEXT, quindi si manda "unknown" e decide lei.
    oid = 0

    def dump(self, obj):
        return obj.isoformat().encode()


class _DateTimeDumper(Dumper):
    oid = 0

    def dump(self, obj):
        return obj.isoformat(" ").encode()


class _BoolLoader(Loader):
    def load(self, data):
        return 1 if bytes(data) == b"t" else 0


class _NumericLoader(Loader):
    # COUNT e simili tornano bigint; numeric arriva da SUM/AVG su interi e
    # da round(): SQLite li darebbe int o float.
    def load(self, data):
        testo = bytes(data).decode()
        if testo.lstrip("-").isdigit():
            return int(testo)
        return float(testo)


def _registra_adattatori(adapters):
    adapters.register_dumper(bool, _BoolDumper)
    adapters.register_dumper(date, _DateDumper)
    adapters.register_dumper(datetime, _DateTimeDumper)
    adapters.register_loader("bool", _BoolLoader)
    adapters.register_loader("numeric", _NumericLoader)


# --- le righe: come sqlite3.Row ------------------------------------------

class Row:
    """Si legge per posizione (row[0]) e per nome (row["name"], senza badare
    alle maiuscole, come sqlite3.Row), e dict(row) funziona."""

    __slots__ = ("_keys", "_index", "_values")

    def __init__(self, keys, index, values):
        self._keys = keys
        self._index = index
        self._values = values

    def keys(self):
        return list(self._keys)

    def __getitem__(self, key):
        if isinstance(key, str):
            try:
                return self._values[self._index[key.lower()]]
            except KeyError:
                raise IndexError("No item with that key") from None
        return self._values[key]

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def __eq__(self, other):
        return isinstance(other, Row) and self._keys == other._keys and self._values == other._values

    def __hash__(self):
        return hash((tuple(self._keys), tuple(self._values)))

    def __repr__(self):
        return "<Row %r>" % (dict(zip(self._keys, self._values)),)


def _row_factory(cursor):
    desc = cursor.description
    if desc is None:
        return tuple
    keys = tuple(d.name for d in desc)
    index = {}
    for i, k in enumerate(keys):
        index.setdefault(k.lower(), i)

    def make(values):
        return Row(keys, index, values)

    return make


# --- la traduzione delle query -------------------------------------------

_TOKEN = re.compile(r"'(?:[^']|'')*'|\"(?:[^\"]|\"\")*\"|--[^\n]*|/\*.*?\*/|\?|%|[^'\"?%/;-]+|.", re.S)
_INSERT_OR_IGNORE = re.compile(r"^\s*INSERT\s+OR\s+IGNORE\s+INTO\b", re.I)
_INSERT_OR_OTHER = re.compile(r"^\s*(INSERT\s+OR\s+\w+|REPLACE\s+INTO)\b", re.I)
_INSERT_TABLE = re.compile(r"^\s*INSERT\s+INTO\s+(\w+)", re.I)
_PRAGMA_TABLE_INFO = re.compile(r"^\s*PRAGMA\s+table_info\s*\(\s*['\"]?(\w+)['\"]?\s*\)\s*;?\s*$", re.I)
_PRAGMA = re.compile(r"^\s*PRAGMA\b", re.I)
_TXN = re.compile(r"^\s*(BEGIN|COMMIT|END)(\s+TRANSACTION)?\s*;?\s*$", re.I)
_DDL = re.compile(r"^\s*(CREATE\s+TABLE|ALTER\s+TABLE)\b", re.I)
_RETURNING = re.compile(r"\bRETURNING\b", re.I)

_TABLE_INFO_SQL = """
    SELECT c.ordinal_position - 1 AS cid,
           c.column_name AS name,
           upper(c.data_type) AS type,
           CASE WHEN c.is_nullable = 'NO' THEN 1 ELSE 0 END AS "notnull",
           c.column_default AS dflt_value,
           CASE WHEN EXISTS (
               SELECT 1 FROM information_schema.table_constraints tc
               JOIN information_schema.key_column_usage k
                 ON k.constraint_name = tc.constraint_name AND k.table_schema = tc.table_schema
               WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_schema = c.table_schema
                 AND tc.table_name = c.table_name AND k.column_name = c.column_name
           ) THEN 1 ELSE 0 END AS pk
    FROM information_schema.columns c
    WHERE c.table_schema = current_schema() AND c.table_name = %s
    ORDER BY c.ordinal_position
"""


def _placeholders(sql, con_parametri):
    """? -> %s fuori dalle stringhe; % -> %% ovunque se ci sono parametri
    (psycopg legge i % anche dentro gli apici). Via i commenti."""
    out = []
    for tok in _TOKEN.findall(sql):
        if tok.startswith("--") or (tok.startswith("/*") and tok.endswith("*/")):
            out.append(" ")
        elif tok == "?":
            out.append("%s")
        elif con_parametri and "%" in tok:
            out.append(tok.replace("%", "%%"))
        else:
            out.append(tok)
    return "".join(out)


_ORDER_END = {"LIMIT", "OFFSET", "UNION", "EXCEPT", "INTERSECT", "RETURNING", "FOR", "ON"}
_WORD = re.compile(r"[A-Za-z_][A-Za-z_0-9]*|\S")


def _order_nulls(sql):
    """I NULL nell'ordinamento come li mette SQLite: in cima in ASC, in fondo
    in DESC. PostgreSQL fa il contrario, e un elenco "per data" metterebbe
    in testa le righe senza data.

    Ogni voce di ogni ORDER BY (fuori dalle stringhe) riceve il suo NULLS
    FIRST/LAST, se non ce l'ha gia'."""
    toks = _TOKEN.findall(sql)
    out, i, n = [], 0, len(toks)

    def parole(t):
        return [w.upper() for w in _WORD.findall(t)] if t[:1] not in ("'", '"') else []

    while i < n:
        t = toks[i]
        out.append(t)
        w = parole(t)
        # "ORDER BY" puo' stare in un token solo ("ORDER BY name ...") o in due.
        if "ORDER" in w:
            testo = "".join(toks[i:])
            m = re.match(r"(?is)(.*?\bORDER\s+BY\b)", testo)
            if m and not re.search(r"['\"]", m.group(1)):
                out.pop()
                resto = testo[m.end():]
                clausola, coda = _split_order(resto)
                out.append(m.group(1) + " ")
                out.append(", ".join(_con_nulls(v) for v in _split_top(clausola)))
                out.append(" " + _order_nulls(coda) if coda else "")
                return "".join(out)
        i += 1
    return "".join(out)


def _split_order(testo):
    """Divide 'voci ORDER BY ... | resto' alla fine della clausola."""
    depth = 0
    for m in _TOKEN.finditer(testo):
        t = m.group(0)
        if t[:1] in ("'", '"'):
            continue
        for w in re.finditer(r"[()]|[A-Za-z_][A-Za-z_0-9]*", t):
            x = w.group(0)
            pos = m.start() + w.start()
            if x == "(":
                depth += 1
            elif x == ")":
                depth -= 1
                if depth < 0:
                    return testo[:pos], testo[pos:]
            elif depth == 0 and x.upper() in _ORDER_END:
                return testo[:pos], testo[pos:]
    return testo, ""


def _split_top(clausola):
    voci, depth, cur = [], 0, []
    for t in _TOKEN.findall(clausola):
        if t[:1] in ("'", '"'):
            cur.append(t)
            continue
        for ch in re.split(r"([(),])", t):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            elif ch == "," and depth == 0:
                voci.append("".join(cur))
                cur = []
                continue
            cur.append(ch)
    voci.append("".join(cur))
    return voci


_NOCASE = re.compile(r"(?is)^(.*?)\s+COLLATE\s+NOCASE\b(.*)$")


def _con_nulls(voce):
    v = voce.strip()
    # NOCASE di SQLite: confronto per byte dopo aver abbassato solo A-Z.
    # "Café" va dopo "Caffe" (é > f), e cosi' deve restare.
    m = _NOCASE.match(v)
    if m:
        v = "translate(%s, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz') COLLATE \"C\"%s" % (
            m.group(1), m.group(2))
    if not v or re.search(r"(?i)\bNULLS\s+(FIRST|LAST)\s*$", v):
        return v
    if re.search(r"(?i)\bDESC\s*$", v):
        return v + " NULLS LAST"
    return v + " NULLS FIRST"


def _ddl(sql):
    sql = re.sub(r"\bINTEGER\s+PRIMARY\s+KEY(\s+AUTOINCREMENT)?\b",
                 "BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY", sql, flags=re.I)
    sql = re.sub(r"\bINTEGER\b", "BIGINT", sql, flags=re.I)
    sql = re.sub(r"\bREAL\b", "DOUBLE PRECISION", sql, flags=re.I)
    sql = re.sub(r"\bBLOB\b", "BYTEA", sql, flags=re.I)
    return sql


def split_script(script):
    """Divide uno script SQL sui ; che stanno fuori da stringhe e commenti."""
    parti, cur = [], []
    for tok in _TOKEN.findall(script):
        if tok == ";":
            parti.append("".join(cur))
            cur = []
        else:
            cur.append(tok)
    parti.append("".join(cur))
    return [p for p in (_placeholders(p, False).strip() for p in parti) if p]


# --- cursore e connessione ----------------------------------------------

class Cursor:
    def __init__(self, cur, lastrowid=None, rows=None):
        self._cur = cur
        self.lastrowid = lastrowid
        self._rows = rows  # gia' letti (INSERT ... RETURNING): a chi chiede, niente
        self.rowcount = cur.rowcount if cur is not None else -1

    @property
    def description(self):
        return self._cur.description if self._cur is not None else None

    def fetchone(self):
        if self._rows is not None:
            return self._rows.pop(0) if self._rows else None
        if self._cur is None or self._cur.description is None:
            return None
        return self._cur.fetchone()

    def fetchall(self):
        if self._rows is not None:
            rows, self._rows = self._rows, []
            return rows
        if self._cur is None or self._cur.description is None:
            return []
        return self._cur.fetchall()

    def fetchmany(self, size=1):
        return [r for r in (self.fetchone() for _ in range(size)) if r is not None]

    def __iter__(self):
        return iter(self.fetchall())

    def close(self):
        if self._cur is not None:
            self._cur.close()


def _errore(e):
    if isinstance(e, psycopg.errors.IntegrityError):
        return sqlite3.IntegrityError(str(e))
    return sqlite3.OperationalError(str(e))


class Connection:
    """Una connessione PostgreSQL presa dal pool che si usa come sqlite3."""

    def __init__(self, db, raw):
        self._db = db
        self._raw = raw
        self.row_factory = None  # ignorato: le righe sono sempre Row

    # -- comandi
    def _run(self, sql, params=None, many=False):
        cur = self._raw.cursor()
        try:
            if many:
                cur.executemany(sql, params)
            else:
                cur.execute(sql, params)
        except psycopg.Error as e:
            cur.close()
            raise _errore(e) from e
        return cur

    def execute(self, sql, params=()):
        params = tuple(params) if params is not None else ()
        if _PRAGMA_TABLE_INFO.match(sql):
            tabella = _PRAGMA_TABLE_INFO.match(sql).group(1).lower()
            return Cursor(self._run(_TABLE_INFO_SQL, (tabella,)))
        if _PRAGMA.match(sql) or _TXN.match(sql):
            return Cursor(None)
        if _INSERT_OR_OTHER.match(sql) and not _INSERT_OR_IGNORE.match(sql):
            raise sqlite3.OperationalError("pgcompat: non tradotto: " + sql[:60])
        ignora = bool(_INSERT_OR_IGNORE.match(sql))
        if ignora:
            sql = _INSERT_OR_IGNORE.sub("INSERT INTO", sql, count=1)
        q = _placeholders(sql, bool(params)).strip().rstrip(";")
        if "ORDER" in q.upper():
            q = _order_nulls(q)
        if _DDL.match(q):
            q = _ddl(q)
            self._db.tabelle_con_id = None
        if ignora:
            q += " ON CONFLICT DO NOTHING"
        m = _INSERT_TABLE.match(q)
        if m and not _RETURNING.search(q) and m.group(1).lower() in self._db.id_tables(self):
            cur = self._run(q + " RETURNING id", params or None)
            rows = cur.fetchall()
            return Cursor(cur, lastrowid=rows[0][0] if rows else None, rows=[])
        return Cursor(self._run(q, params or None))

    def executemany(self, sql, seq):
        seq = [tuple(p) for p in seq]
        ignora = bool(_INSERT_OR_IGNORE.match(sql))
        if ignora:
            sql = _INSERT_OR_IGNORE.sub("INSERT INTO", sql, count=1)
        q = _placeholders(sql, True).strip().rstrip(";")
        if ignora:
            q += " ON CONFLICT DO NOTHING"
        if not seq:
            return Cursor(None)
        return Cursor(self._run(q, seq, many=True))

    def executescript(self, script):
        ddl = False
        for stmt in split_script(script):
            if _PRAGMA.match(stmt) or _TXN.match(stmt):
                continue
            if _DDL.match(stmt):
                stmt = _ddl(stmt)
                ddl = True
            self._run(stmt).close()
        if ddl:
            self._db.tabelle_con_id = None
            # Le ricostruzioni di SQLite ("crea la nuova, copia, scambia")
            # copiano anche gli id: il contatore va rimesso dopo l'ultimo.
            sync_sequences(self)
        return Cursor(None)

    # -- transazioni
    def commit(self):
        try:
            self._raw.commit()
        except psycopg.Error as e:
            raise _errore(e) from e

    def rollback(self):
        self._raw.rollback()

    def close(self):
        raw, self._raw = self._raw, None
        if raw is not None:
            # Come sqlite3: chiudere senza commit butta via la transazione.
            # Fatto qui, il pool non se ne lamenta nel log a ogni GET.
            if raw.info.transaction_status != psycopg.pq.TransactionStatus.IDLE:
                try:
                    raw.rollback()
                except psycopg.Error:
                    pass
            self._db.restituisci(raw)

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        # Come sqlite3: il blocco with chiude la transazione, non la connessione.
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        return False


class Database:
    def __init__(self, url, max_size=20):
        _registra_adattatori(psycopg.adapters)
        self.url = url
        self.pool = ConnectionPool(
            url, min_size=1, max_size=max_size, open=True, timeout=30,
            kwargs={"row_factory": _row_factory, "autocommit": False},
            name="miopalco",
        )
        self.tabelle_con_id = None
        self._lock = threading.Lock()

    def connect(self):
        return Connection(self, self.pool.getconn())

    def restituisci(self, raw):
        self.pool.putconn(raw)

    def id_tables(self, conn):
        tabelle = self.tabelle_con_id
        if tabelle is None:
            rows = conn._run(
                "SELECT table_name FROM information_schema.columns "
                "WHERE table_schema = current_schema() AND column_name = 'id' "
                "AND is_identity = 'YES'"
            ).fetchall()
            tabelle = self.tabelle_con_id = {r[0] for r in rows}
        return tabelle


def prepare(conn):
    """Quello che il dialetto di SQLite da' per scontato e PostgreSQL no.
    Idempotente: gira a ogni avvio, dentro init_db."""
    conn._run(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_collation WHERE collname = 'nocase') THEN "
        "CREATE COLLATION nocase (provider = icu, locale = 'und-u-ks-level2', deterministic = false); "
        "END IF; END $$"
    ).close()
    conn._run(
        "CREATE OR REPLACE FUNCTION round(double precision, integer) RETURNS double precision "
        "LANGUAGE sql IMMUTABLE STRICT AS $$ SELECT round($1::numeric, $2)::double precision $$"
    ).close()
    conn.commit()


def sync_sequences(conn):
    """Porta i contatori degli id almeno dopo l'id piu' alto di ogni tabella.
    Solo in avanti: un contatore piu' avanti del MAX(id) (righe cancellate,
    o il sqlite_sequence portato dalla migrazione) resta dov'e', cosi' un id
    gia' usato non torna mai."""
    for (tabella,) in conn._run(
        "SELECT table_name FROM information_schema.columns "
        "WHERE table_schema = current_schema() AND column_name = 'id' AND is_identity = 'YES'"
    ).fetchall():
        seq = conn._run("SELECT pg_get_serial_sequence(%s, 'id')", ('"%s"' % tabella,)).fetchone()[0]
        prossimo, = conn._run(
            "SELECT CASE WHEN is_called THEN last_value + 1 ELSE last_value END FROM " + seq
        ).fetchone()
        massimo, = conn._run('SELECT COALESCE(MAX(id), 0) + 1 FROM "' + tabella + '"').fetchone()
        if massimo > prossimo:
            conn._run("SELECT setval(%s, %s, false)", (seq, massimo)).close()


def table_exists(conn, nome):
    return conn._run(
        "SELECT 1 FROM information_schema.tables WHERE table_schema = current_schema() "
        "AND table_name = %s", (nome,),
    ).fetchone() is not None
