-- Unified memory cleanup script (Scheme A: data/sqlite/agentmesh.db as single source)
-- Usage examples:
--   sqlite3 "$HOME/agentmesh/memory/long-term/index.db" < scripts/drop_unused_tables.sql
--   sqlite3 "$HOME/agentmesh/memory/long-term/index.db" ".tables"
--
-- WARNING:
-- - This script is intended for index.db only.
-- - Do NOT run this against data/sqlite/agentmesh.db.

BEGIN TRANSACTION;

DROP TABLE IF EXISTS chunks_fts;
DROP TABLE IF EXISTS chunks;
DROP TABLE IF EXISTS files;
DROP TABLE IF EXISTS vector_map;
DROP TABLE IF EXISTS vector_meta;

COMMIT;
