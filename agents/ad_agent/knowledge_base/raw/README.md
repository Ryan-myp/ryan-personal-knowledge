# Raw Sources

This directory is the immutable source layer of the Karpathy-style Wiki.

Raw material is kept for ingest, provenance and re-processing. It is not
loaded into the Agent Runtime directly. Runtime context comes from published
entity, concept, comparison and query pages with source citations.

The larger personal corpus remains under the repository-level `knowledge/`
directory. New material should record its original path or URL in
`source_ref`, then be distilled into a published Wiki page.

For tenant uploads, the HTTP/API source of truth is the persistence-backed
`raw_knowledge_sources` table. The checked-in directory documents this same
boundary for repository-managed material; it is not a writable Runtime cache.
