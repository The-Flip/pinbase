# Model-Driven Metadata — Planning

Sibling doc to [ModelDrivenMetadata.md](ModelDrivenMetadata.md) (the principle + patterns reference). This doc holds the order-sensitive state: what work comes next, what's waiting on what, what can go in parallel. The umbrella stays time-invariant; this doc is where sequencing lives and evolves.

## Next steps

Ordered by "how sure this is the right next thing," not by dependency.

### Resolve open questions in `CatalogRelationshipSpec`

Primarily the `M2M_FIELDS` / bespoke-resolver asymmetry (why is a resolver generic vs. bespoke?). Detail doc: [ModelDrivenCatalogRelationshipMetadata.md](ModelDrivenCatalogRelationshipMetadata.md). Includes a code-survey subtask across the Cluster 1 bespoke resolvers; natural candidate to delegate to a fresh session.

### Rewrite `ProvenanceValidationTightening.md`

Against the finalized `CatalogRelationshipSpec`. Reopens [CatalogResolveTyping.md](../types/CatalogResolveTyping.md) (TypedDicts still make sense, but "consistency test against a registry" becomes "consistency test against model introspection results").

Do NOT do this before `CatalogRelationshipSpec`'s open questions are resolved — the asymmetry decision changes the spec's actual fields, and rewriting against an imagined spec wastes the rewrite.

### Revisit cluster 4

Ingest adapter wiring, once both specs exist.
