#!/usr/bin/env python3
"""Merge all KG shard JSONs into the SQLite knowledge graph."""
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from gbd.knowledge_graph.graph import KnowledgeGraph
from gbd.knowledge_graph.schema import Entity, EntityType

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("merge")

SCRATCH = Path(os.environ["KG_DATA_ROOT"])
KG_PATH = SCRATCH / "gbd_knowledge_graph.db"
SHARD_DIR = SCRATCH / "kg_shards"

TYPE_MAP = {
    "Gene": EntityType.GENE,
    "BiologicalProcess": EntityType.BIOLOGICAL_PROCESS,
    "CellularComponent": EntityType.CELLULAR_COMPONENT,
    "Pathway": EntityType.PATHWAY,
    "MolecularFunction": EntityType.MOLECULAR_FUNCTION,
    "Disease": EntityType.DISEASE,
}

def main():
    kg = KnowledgeGraph(KG_PATH)

    # Merge gene annotation shards
    gene_shards = sorted(SHARD_DIR.glob("genes_shard_*.json"))
    log.info("Merging %d gene shards...", len(gene_shards))
    total_entities = 0
    total_edges = 0

    for shard_path in gene_shards:
        with open(shard_path) as f:
            data = json.load(f)

        for ent in data.get("entities", []):
            et = TYPE_MAP.get(ent["entity_type"], EntityType.GENE)
            kg.add_entity(Entity(
                entity_id=ent["entity_id"],
                entity_type=et,
                name=ent.get("name", ent["entity_id"]),
                xrefs=ent.get("xrefs", {}),
                properties={"summary": ent.get("summary", "")},
            ))
            total_entities += 1

        for edge in data.get("edges", []):
            # Ensure target entity exists
            target_type = TYPE_MAP.get(edge.get("target_type", ""), EntityType.BIOLOGICAL_PROCESS)
            kg.add_entity(Entity(
                entity_id=edge["target"],
                entity_type=target_type,
                name=edge.get("target_name", edge["target"]),
            ))
            edge_id = f"E-{edge['source']}-{edge['target'][:30]}"
            kg.conn.execute(
                "INSERT OR IGNORE INTO backbone_edges VALUES (?, ?, ?, ?, ?, ?, ?)",
                (edge_id, edge["type"], edge["source"], edge["target"],
                 json.dumps({}), edge.get("source_db", ""), 1.0),
            )
            total_edges += 1

        kg.conn.commit()
        log.info("  %s: +%d entities, +%d edges",
                 shard_path.name, len(data.get("entities", [])), len(data.get("edges", [])))

    # Merge PPI shards
    ppi_shards = sorted(SHARD_DIR.glob("ppi_shard_*.json"))
    log.info("Merging %d PPI shards...", len(ppi_shards))
    ppi_count = 0
    for shard_path in ppi_shards:
        with open(shard_path) as f:
            data = json.load(f)
        for edge in data.get("edges", []):
            a, b = edge["source"], edge["target"]
            edge_id = f"PPI-{min(a,b)}-{max(a,b)}"
            kg.conn.execute(
                "INSERT OR IGNORE INTO backbone_edges VALUES (?, ?, ?, ?, ?, ?, ?)",
                (edge_id, "Protein-interacts-Protein", a, b,
                 json.dumps({"score": edge.get("score", 0)}), "STRING", edge.get("score", 0)),
            )
            ppi_count += 1
        kg.conn.commit()
        log.info("  %s: +%d PPI edges", shard_path.name, len(data.get("edges", [])))

    summary = kg.summary()
    log.info("═══ MERGED KNOWLEDGE GRAPH ═══")
    for k, v in summary.items():
        log.info("  %-30s %s", k, v)
    log.info("Total: %d entities, %d backbone edges (incl %d PPI)",
             total_entities, total_edges + ppi_count, ppi_count)

    kg.close()


if __name__ == "__main__":
    main()
