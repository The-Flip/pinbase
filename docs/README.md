# Documentation

This directory contains the stable product, architecture, development, and operations documentation for Flipcommons.

For setup and common commands, start with the repository [README](../README.md). For historical design notes and implementation plans, use [plans/README.md](plans/README.md).

## Start Here

- [Overview.md](Overview.md) explains what Flipcommons is, who it serves, and why the product is shaped the way it is.
- [Development.md](Development.md) is the contributor-facing hub for working in this codebase.
- [Architecture.md](Architecture.md) gives the top-level system map.
- [DomainModel.md](DomainModel.md) explains the catalog's pinball domain model.

## Product And Domain

- [Definitions.md](Definitions.md) defines pinball terminology used by the product and data model.
- [Personas.md](Personas.md) describes the main user groups the product serves.
- [DomainModel.md](DomainModel.md) documents titles, models, variants, series, and related catalog concepts.
- [SingleModelTitles.md](SingleModelTitles.md) explains how the product handles titles with exactly one model.
- [RecordLifecycle.md](RecordLifecycle.md) covers creation, deletion, restore, and duplicate-prevention semantics.
- [Privacy.md](Privacy.md) captures privacy principles and analytics expectations.
- [SmallTeam.md](SmallTeam.md) records operating principles for a small team.

## System Architecture

- [Architecture.md](Architecture.md) describes the overall Django + SvelteKit system.
- [WebArchitecture.md](WebArchitecture.md) covers the web split, same-origin model, API layer, and development proxy.
- [AppBoundaries.md](AppBoundaries.md) defines Django app responsibilities and dependency rules.
- [ApiDesign.md](ApiDesign.md) documents endpoint design and schema design heuristics.
- [Authz.md](Authz.md) explains authorization activities, policy gates, and capability surfaces.
- [Provenance.md](Provenance.md) documents claims, resolution, audit history, and provenance invariants.
- [Media.md](Media.md) explains media storage, uploads, claims, and attachment resolution.
- [Ingest.md](Ingest.md) describes external data sources and the ingest pipeline.
- [Hosting.md](Hosting.md) documents the Railway deployment topology.

## Frontend

- [Svelte.md](Svelte.md) covers Svelte 5 authoring conventions and rendering strategy.
- [SSRConversion.md](SSRConversion.md) gives the workflow for converting routes from CSR to SSR.
- [DetailLayoutPatterns.md](DetailLayoutPatterns.md) documents detail-page layout patterns.
- [TestingFrontend.md](TestingFrontend.md) covers frontend test tiers and DOM test patterns.

## Backend

- [Python.md](Python.md) documents backend typing and Python style decisions.
- [DataModeling.md](DataModeling.md) covers database modeling principles and constraint patterns.
- [EntityNaming.md](EntityNaming.md) defines entity naming rules and where canonical names live.
- [TestingBackend.md](TestingBackend.md) covers backend test strategy and constraint testing.

## Testing And Review

- [Testing.md](Testing.md) covers the overall testing strategy.
- [Reviewing.md](Reviewing.md) gives repo-specific review priorities and checks.

## Agent Docs

- [AGENTS.src.md](AGENTS.src.md) is the source for generated AI-agent guidance. Do not edit generated `AGENTS.md` or `CLAUDE.md` directly.

## Historical Plans

- [plans/README.md](plans/README.md) explains how to use historical planning documents. Plan docs are useful for context and rationale, but they are not canonical current documentation.
