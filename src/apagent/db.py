"""Small data layer: the rest of the code only calls query() and execute().

Swap SQLite -> DuckDB -> Databricks by changing APAGENT_BACKEND in .env.
Nothing else in the project knows which database it is talking to.
"""
from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path
from typing import Any, Protocol

from apagent.config import Settings, get_settings

TABLES = ["suppliers", "po_headers", "po_lines", "receipts", "invoices", "invoice_lines", "holds"]


def ddl(money: str) -> list[str]:
    """Table definitions. `money` is the column type for amounts (TEXT in SQLite, DECIMAL elsewhere)."""
    return [
        """CREATE TABLE suppliers (supplier_id TEXT PRIMARY KEY, supplier_name TEXT, site TEXT,
               bank_account TEXT, tax_id TEXT)""",
        "CREATE TABLE po_headers (po_id TEXT PRIMARY KEY, supplier_id TEXT, currency TEXT, buyer TEXT)",
        f"""CREATE TABLE po_lines (po_id TEXT, line_num INTEGER, item TEXT, unit_price {money},
               qty_ordered {money}, match_type TEXT)""",
        f"""CREATE TABLE receipts (receipt_id TEXT, po_id TEXT, line_num INTEGER, qty_received {money},
               receipt_date TEXT)""",
        f"""CREATE TABLE invoices (invoice_id TEXT PRIMARY KEY, invoice_num TEXT, supplier_id TEXT,
               invoice_date TEXT, amount {money}, currency TEXT, status TEXT, description TEXT)""",
        f"""CREATE TABLE invoice_lines (invoice_id TEXT, line_num INTEGER, po_id TEXT, po_line_num INTEGER,
               qty_billed {money}, unit_price {money})""",
        "CREATE TABLE holds (invoice_id TEXT, hold_code TEXT, hold_date TEXT)",
    ]


class DataLayer(Protocol):
    def query(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]: ...
    def execute(self, sql: str, params: tuple = ()) -> None: ...
    def executemany(self, sql: str, rows: list[tuple]) -> None: ...
    def reset_schema(self) -> None: ...


class SQLiteBackend:
    money = "TEXT"  # store money as text, convert to Decimal in Python -> no float rounding

    def __init__(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)  # MCP server calls tools from worker threads
        self.conn.row_factory = sqlite3.Row

    def query(self, sql, params=()):
        return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    def execute(self, sql, params=()):
        self.conn.execute(sql, params)
        self.conn.commit()

    def executemany(self, sql, rows):
        self.conn.executemany(sql, rows)
        self.conn.commit()

    def reset_schema(self):
        for t in TABLES:
            self.conn.execute(f"DROP TABLE IF EXISTS {t}")
        for stmt in ddl(self.money):
            self.conn.execute(stmt)
        self.conn.commit()


class DuckDBBackend:
    money = "DECIMAL(18,4)"

    def __init__(self, path: str):
        import duckdb  # imported only if this backend is chosen
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = duckdb.connect(path.replace(".db", ".duckdb"))

    def query(self, sql, params=()):
        cur = self.conn.execute(sql, list(params))
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def execute(self, sql, params=()):
        self.conn.execute(sql, list(params))

    def executemany(self, sql, rows):
        self.conn.executemany(sql, [list(r) for r in rows])

    def reset_schema(self):
        for t in TABLES:
            self.conn.execute(f"DROP TABLE IF EXISTS {t}")
        for stmt in ddl(self.money):
            self.conn.execute(stmt)


class DatabricksBackend:
    """Milestone H. Uses Delta tables in a Unity Catalog schema.

    Not exercised by the local test suite; verify against your own workspace.
    """
    money = "DECIMAL(18,4)"

    def __init__(self):
        from databricks import sql as dbsql  # pip install databricks-sql-connector
        self.conn = dbsql.connect(
            server_hostname=os.environ["DATABRICKS_SERVER_HOSTNAME"],
            http_path=os.environ["DATABRICKS_HTTP_PATH"],
            access_token=os.environ["DATABRICKS_TOKEN"],
        )
        catalog = os.getenv("DATABRICKS_CATALOG", "workspace")
        schema = os.getenv("DATABRICKS_SCHEMA", "ap_agent")
        with self.conn.cursor() as cur:
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")
            cur.execute(f"USE {catalog}.{schema}")

    @staticmethod
    def _named(sql: str, params: tuple) -> tuple[str, dict]:
        """Convert '?' placeholders to ':p0, :p1' named parameters (Databricks native style)."""
        counter = iter(range(len(params)))
        new_sql = re.sub(r"\?", lambda _: f":p{next(counter)}", sql)
        return new_sql, {f"p{i}": v for i, v in enumerate(params)}

    def query(self, sql, params=()):
        s, p = self._named(sql, params)
        with self.conn.cursor() as cur:
            cur.execute(s, p)
            cols = [c[0] for c in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]

    def execute(self, sql, params=()):
        s, p = self._named(sql, params)
        with self.conn.cursor() as cur:
            cur.execute(s, p)

    def executemany(self, sql, rows):
        for r in rows:  # fine for ~hundreds of rows; use COPY INTO / Spark for real volumes
            self.execute(sql, r)

    def reset_schema(self):
        for t in TABLES:
            self.execute(f"DROP TABLE IF EXISTS {t}")
        for stmt in ddl(self.money):
            self.execute(stmt + " USING DELTA")


def get_data_layer(settings: Settings | None = None) -> DataLayer:
    s = settings or get_settings()
    if s.backend == "sqlite":
        return SQLiteBackend(s.db_path)
    if s.backend == "duckdb":
        return DuckDBBackend(s.db_path)
    if s.backend == "databricks":
        return DatabricksBackend()
    raise ValueError(f"Unknown backend: {s.backend!r} (use sqlite, duckdb or databricks)")
