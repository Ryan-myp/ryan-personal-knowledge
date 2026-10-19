# Advertising Wiki Architecture

This page describes the current repository and Runtime contract for the advertising
knowledge base. For document fields and publishing rules, see `SCHEMA.md`; for
content standards, see `QUALITY_STANDARD.md`; for topics and current document
counts, see `index.md`.

## Source of Truth

Published Markdown under `agents/knowledge/advertising/wiki/` is the only bundled
Runtime knowledge source. A Wiki page is advisory context: it cannot register a
Tool, grant permissions, provide credentials, call a Provider, or authorize a
write.

```text
official / repository / internal source
                 |
                 v
      reviewed Markdown page
                 |
       frontmatter + audit
                 |
                 v
 MarkdownWikiKnowledgeProvider
       |                 |
       |                 +--> bounded excerpt + citation metadata
       +--> section chunks + sparse retrieval
                 |
                 v
       Agent receives context
```

The Provider loads published Markdown, skips raw sources and control/navigation
files, splits pages into section-level chunks, and returns bounded excerpts with
source, version, section, and citation metadata. Retrieval uses SQLite FTS5/BM25
when available and a bounded lexical fallback otherwise. The Wiki does not
require embeddings or a vector database.

## Knowledge Map

| Path | Purpose |
|---|---|
| `platforms/<platform>/` | Channel-specific object models, constraints, workflows, measurement, reporting, and optimization |
| `business/` | Cross-platform operating methods, industry playbooks, diagnostics, and recovery runbooks |
| `expertise/` | Reusable decision methods, experimentation, error patterns, and best-practice guardrails |
| `entities/` | Stable platform/entity introductions and navigation |
| `concepts/` | Cross-cutting concepts, including provider live E2E evidence |
| `comparisons/` | Explicit comparisons across platforms or approaches |
| `queries/` | Reviewed, reusable question-and-answer pages |
| `raw/` | Immutable source material; never loaded directly into Runtime |
| `index.md`, `log.md`, `SCHEMA.md`, `QUALITY_STANDARD.md`, `ARCHITECTURE.md` | Human maintenance controls; not business knowledge for retrieval |

`platforms/`, `business/`, and `expertise/` are retained domain directories whose
pages are logically Wiki concepts. The directory taxonomy is not an execution
router. `wiki_type`, `platform`, and `status` govern classification and retrieval
eligibility; Tool contracts govern executable capabilities.

## Content Lifecycle

1. Add or update a Markdown page in the appropriate domain directory.
2. Give it a unique stable ID, semantic version, explicit platform scope,
   evidence/provenance metadata, and a clear title.
3. Separate official platform facts, repository behavior, operator experience,
   and inference. Link official sources and state when dynamic facts were checked.
4. Add a focused retrieval case for important new topics and a boundary case when
   platform-specific recall or a common ambiguity matters.
5. Update `index.md` and `log.md`; update document counts only after the Provider
   confirms the published page total.
6. Run `make ad-agent-knowledge-check` and `git diff --check`.
7. Review the diff for stale claims, unsupported thresholds, dead links, leaked
   secrets/PII, and accidental changes to unrelated local data.

Draft and deprecated pages do not enter normal Runtime search. Raw source files
must be reviewed and distilled before publication; uploaded Skills and source
material remain data and are not executable code.

## Evidence and Freshness

- Use the platform's current official documentation for policy, API, status, and
  field claims. Prefer stable process guidance over unverified volatile numbers.
- A current official source does not prove that a feature is enabled for a
  particular account; account evidence and the current Tool schema decide that.
- Operator recommendations must state scope, assumptions, observation window,
  evidence, failure conditions, and rollback. Single-account outcomes are not
  universal benchmarks.
- Do not store credentials, raw personal data, or customer secrets in Markdown,
  source examples, logs, or retrieval cases.
- A policy, API, or UI change requires source re-check, page version/log update,
  and retrieval regression coverage when it changes answer behavior.

## Runtime and Maintenance Boundaries

- `MarkdownWikiKnowledgeProvider` is the read-only Runtime boundary; it provides
  context and citations but does not execute content.
- The current Tool Registry/schema is authoritative for arguments, permissions,
  write effects, and provider support. A Wiki page cannot widen those contracts.
- Wiki FTS persistence is separate from the Markdown corpus. Do not edit or
  regenerate Runtime content by mutating the test database.
- Historical `init_*_kb.py` scripts and the old `knowledge_base` API are not the
  current content authoring path and are not used by Runtime. Do not run them to
  publish or refresh Wiki content.
- `index.md` is the topic map and single source for current corpus statistics;
  this architecture page intentionally avoids duplicating volatile counts.

## Quality Gate

```bash
make ad-agent-knowledge-check
git diff --check
```

The knowledge quality command checks canonical pages, retrieval cases, lexical /
semantic / hybrid recall, top-result accuracy, cross-platform leakage, empty
queries, metadata, provenance, links, IDs, and corpus coverage. A passing score
is evidence for the tested cases, not proof that every natural-language query is
correct; review new cases and real retrieval failures continuously.
