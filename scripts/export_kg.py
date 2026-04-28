"""Export GBD knowledge-graph SCHEMA (no bulk data) for sharing.

Produces only the metadata needed to understand and reconstruct the KG —
entity types, edge types, source-database contributions, and one example row
per type. The 5M-edge / 118k-entity payload is intentionally NOT exported.

Outputs (under repo root):
  schema/entity_types.tsv     entity_type, count, source_dbs, fields, example_id
  schema/edge_types.tsv       edge_type, count, sources, head_type, tail_type
  schema/resources.tsv        source_db, entity_total, edge_total, contributed
  schema/examples.tsv         one sample entity/edge row per type
  schema/table_schemas.sql    CREATE TABLE statements from the live DB

Run from the repo root:
    python scripts/export_kg.py
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from collections import defaultdict
from pathlib import Path

DEFAULT_DB = "/home/eqk3/scratch_pi_mg269/eqk3/coscientist_data/gbd_knowledge_graph.db"

KG_TABLES = ["entities", "backbone_edges", "claims", "claim_participants",
             "evidence", "support_sets", "contradictions", "context_nodes"]


def open_ro(db_path: str) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db_path}?mode=ro&immutable=1", uri=True)


def export_entity_types(conn, schema_dir: Path) -> dict[str, int]:
    cur = conn.cursor()
    cur.execute("SELECT entity_type, COUNT(*) FROM entities GROUP BY entity_type;")
    counts = {et: n for et, n in cur.fetchall()}

    cur.execute(
        "SELECT entity_type, json_extract(xrefs, '$.source_db') AS src, COUNT(*) "
        "FROM entities GROUP BY entity_type, src;"
    )
    by_type_src: dict[str, dict[str, int]] = defaultdict(dict)
    for et, src, n in cur.fetchall():
        by_type_src[et][src or "unspecified"] = n

    examples: dict[str, dict] = {}
    for et in counts:
        cur.execute(
            "SELECT entity_id, name, aliases, xrefs, properties "
            "FROM entities WHERE entity_type = ? LIMIT 1;",
            (et,),
        )
        row = cur.fetchone()
        if row:
            examples[et] = {
                "entity_id": row[0],
                "name": row[1],
                "aliases": row[2],
                "xrefs": row[3],
                "properties": row[4],
            }

    out = schema_dir / "entity_types.tsv"
    with out.open("w") as f:
        f.write("entity_type\tcount\tsources\texample_id\texample_name\texample_xrefs\n")
        for et in sorted(counts, key=lambda x: -counts[x]):
            srcs = "; ".join(f"{s}={c}" for s, c in
                             sorted(by_type_src[et].items(), key=lambda kv: -kv[1]))
            ex = examples.get(et, {})
            f.write("\t".join([
                et, str(counts[et]), srcs,
                _esc(ex.get("entity_id", "")),
                _esc(ex.get("name", "")),
                _esc(ex.get("xrefs", "")),
            ]) + "\n")
    print(f"  wrote {out} ({len(counts)} entity types)")
    return counts


def export_edge_types(conn, schema_dir: Path) -> dict[str, int]:
    cur = conn.cursor()
    cur.execute("SELECT edge_type, COUNT(*) FROM backbone_edges GROUP BY edge_type;")
    counts = {et: n for et, n in cur.fetchall()}

    cur.execute(
        "SELECT edge_type, source_db, COUNT(*) FROM backbone_edges "
        "GROUP BY edge_type, source_db;"
    )
    by_edge_src: dict[str, dict[str, int]] = defaultdict(dict)
    for et, src, n in cur.fetchall():
        by_edge_src[et][src or "unspecified"] = n

    # head/tail entity types per edge type — sample 200 rows per edge type
    cur.execute("SELECT DISTINCT edge_type FROM backbone_edges;")
    edge_types = [r[0] for r in cur.fetchall()]
    head_tail: dict[str, tuple[set, set]] = {}
    examples: dict[str, dict] = {}
    for et in edge_types:
        cur.execute(
            "SELECT b.source_id, e1.entity_type, b.target_id, e2.entity_type, "
            "       b.source_db, b.confidence, b.properties "
            "FROM backbone_edges b "
            "LEFT JOIN entities e1 ON e1.entity_id = b.source_id "
            "LEFT JOIN entities e2 ON e2.entity_id = b.target_id "
            "WHERE b.edge_type = ? LIMIT 200;",
            (et,),
        )
        heads, tails = set(), set()
        ex = None
        for sid, hty, tid, tty, sdb, conf, props in cur.fetchall():
            if hty:
                heads.add(hty)
            if tty:
                tails.add(tty)
            if ex is None:
                ex = {"source": sid, "head_type": hty or "?", "target": tid,
                      "tail_type": tty or "?", "source_db": sdb,
                      "confidence": conf, "properties": props}
        head_tail[et] = (heads, tails)
        if ex:
            examples[et] = ex

    out = schema_dir / "edge_types.tsv"
    with out.open("w") as f:
        f.write("edge_type\tcount\thead_types\ttail_types\tsources\t"
                "example_source\texample_target\texample_source_db\texample_confidence\n")
        for et in sorted(counts, key=lambda x: -counts[x]):
            heads, tails = head_tail.get(et, (set(), set()))
            srcs = "; ".join(f"{s}={c}" for s, c in
                             sorted(by_edge_src[et].items(), key=lambda kv: -kv[1]))
            ex = examples.get(et, {})
            f.write("\t".join([
                et, str(counts[et]),
                ",".join(sorted(heads)) or "?",
                ",".join(sorted(tails)) or "?",
                srcs,
                _esc(ex.get("source", "")),
                _esc(ex.get("target", "")),
                _esc(ex.get("source_db", "")),
                _esc(str(ex.get("confidence", ""))),
            ]) + "\n")
    print(f"  wrote {out} ({len(counts)} edge types)")
    return counts


def export_resources(conn, schema_dir: Path) -> None:
    cur = conn.cursor()

    cur.execute(
        "SELECT source_db, edge_type, COUNT(*) FROM backbone_edges "
        "GROUP BY source_db, edge_type;"
    )
    edge_by_src: dict[str, dict[str, int]] = defaultdict(dict)
    for src, et, n in cur.fetchall():
        edge_by_src[src or "unspecified"][et] = n

    cur.execute(
        "SELECT json_extract(xrefs, '$.source_db') AS src, entity_type, COUNT(*) "
        "FROM entities GROUP BY src, entity_type;"
    )
    ent_by_src: dict[str, dict[str, int]] = defaultdict(dict)
    for src, et, n in cur.fetchall():
        ent_by_src[src or "unspecified"][et] = n

    sources = sorted(set(edge_by_src) | set(ent_by_src))
    out = schema_dir / "resources.tsv"
    with out.open("w") as f:
        f.write("source_db\tentity_total\tedge_total\tentity_types_contributed\tedge_types_contributed\n")
        rows = []
        for src in sources:
            ent_map = ent_by_src.get(src, {})
            edge_map = edge_by_src.get(src, {})
            ent_total = sum(ent_map.values())
            edge_total = sum(edge_map.values())
            ents = "; ".join(f"{k}={v}" for k, v in
                             sorted(ent_map.items(), key=lambda kv: -kv[1]))
            edges = "; ".join(f"{k}={v}" for k, v in
                              sorted(edge_map.items(), key=lambda kv: -kv[1]))
            rows.append((src, ent_total, edge_total, ents, edges))
        rows.sort(key=lambda r: -(r[1] + r[2]))
        for src, et, ed, ets, eds in rows:
            f.write(f"{src}\t{et}\t{ed}\t{ets}\t{eds}\n")
    print(f"  wrote {out} ({len(sources)} resources)")


def export_table_schemas(conn, schema_dir: Path) -> None:
    cur = conn.cursor()
    out = schema_dir / "table_schemas.sql"
    with out.open("w") as f:
        f.write("-- Live CREATE TABLE / CREATE INDEX statements from the GBD KG SQLite DB.\n")
        f.write("-- Source: gbd_knowledge_graph.db\n\n")
        cur.execute(
            "SELECT type, name, sql FROM sqlite_master "
            "WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' "
            "ORDER BY CASE type WHEN 'table' THEN 0 WHEN 'index' THEN 1 ELSE 2 END, name;"
        )
        for typ, name, sql in cur.fetchall():
            f.write(f"-- {typ}: {name}\n{sql};\n\n")
    print(f"  wrote {out}")


def _esc(v) -> str:
    if v is None:
        return ""
    return str(v).replace("\t", " ").replace("\n", " ").replace("\r", " ")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.environ.get("GBD_KG_DB", DEFAULT_DB))
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent))
    args = ap.parse_args()

    out = Path(args.out)
    schema_dir = out / "schema"
    schema_dir.mkdir(parents=True, exist_ok=True)

    print(f"DB: {args.db}")
    print(f"OUT: {schema_dir}\n")

    conn = open_ro(args.db)

    print("[1/4] entity_types")
    ent_counts = export_entity_types(conn, schema_dir)
    print("\n[2/4] edge_types")
    edge_counts = export_edge_types(conn, schema_dir)
    print("\n[3/4] resources")
    export_resources(conn, schema_dir)
    print("\n[4/4] table_schemas")
    export_table_schemas(conn, schema_dir)

    print("\nTotals:")
    print(f"  entities: {sum(ent_counts.values()):,} across {len(ent_counts)} types")
    print(f"  edges:    {sum(edge_counts.values()):,} across {len(edge_counts)} types")


if __name__ == "__main__":
    main()
