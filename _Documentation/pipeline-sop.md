# Analytics Pipeline Build — Standard Operating Procedure

**Document ID:** SOP-DATA-001
**Version:** 1.1
**Effective date:** 2026-04-21
**Owner:** Data Platform Team
**Review cadence:** quarterly

---

## 1. Purpose

This SOP defines the standard process the Data Platform Team follows to deliver a new analytics pipeline — from raw source data to a validated, tested, consumer-ready data model. It applies to all new pipeline requests and to incremental additions to existing solutions, regardless of specific source format, transformation tooling, or consumption layer.

## 2. Scope

**In scope:** any structured or semi-structured source, any team-approved transformation tool, any dimensional target model, automated testing and validation, handoff to downstream consumption.

**Out of scope:** real-time streaming pipelines, consumption-layer authoring (measures, reports, dashboards), production release and promotion (covered by separate release SOP).

## 3. Roles and responsibilities

| Role | Responsibility |
|---|---|
| **Product Owner** | Submits request; approves the solution design; accepts or rejects deviations during build |
| **Pipeline Coordinator** | Owns end-to-end delivery; maintains the single source of truth document; enforces quality gates |
| **Business Analyst** | Gathers requirements; documents business rules, KPIs, and consumer intent |
| **Data Profiler** | Inventories sources; produces structural and quality profiles |
| **Platform Engineer** | Provisions environment, workspace, connections, version control |
| **Staging Modeller** | Builds source-to-prepared transformations |
| **Dimension Modeller** | Builds conformed reference/entity tables according to the approved model |
| **Fact Modeller** | Builds transactional/event tables at declared grain, aligned to dimensions |
| **QA Engineer** | Authors and executes test coverage; gates build quality |
| **Validator** | Performs end-to-end build validation; produces the validation report |

## 4. Process overview

The build is organised into **14 sequential steps**, grouped into four phases:

| Phase | Steps | Purpose |
|---|---|---|
| A. Preparation | 1–3 | Confirm environment, sources, and current state |
| B. Design & Approval | 4–6 | Document requirements, propose design, obtain sign-off |
| C. Build | 7–12 | Provision workspace, load data, build model layers, author tests |
| D. Validation & Handoff | 13–14 | Validate end-to-end and hand over artefacts |

Each step has an owner, an input, a deliverable, and (where applicable) a quality gate.

## 5. Process steps

### Phase A — Preparation

#### Step 1 — Verify Environment and Tool Access

Pipeline Coordinator confirms the build environment is ready: required tools are installed and functional, target platform (database, lakehouse, or other) is reachable, credentials are valid, version control is available. **Gate:** no build work begins until environment is verified.

#### Step 2 — Verify Access to Sources and Current State of the Project

Coordinator confirms that source data is accessible in the designated intake location and determines whether this is a **fresh build** (new project) or an **incremental addition** (existing project with prior deliverables). The mode determines whether Step 7 (workspace provisioning) is executed or skipped. If sources are missing or unreachable, the request is returned to the Product Owner.

#### Step 3 — Profile and Inventory Sources

Data Profilers produce a structural profile for every source, documenting entities, attributes, data types, null rates, cardinality, candidate keys, and any data quality concerns. Sources with missing or ambiguous metadata (e.g., headerless files, undocumented codes) are flagged for explicit resolution in Step 4.

**Deliverable:** a source profile artefact for each source, stored in the project documentation folder.

### Phase B — Design and Approval

#### Step 4 — Requirements Discovery *(Product Owner touchpoint 1 of 2)*

Business Analyst reviews all source profiles. For any source flagged in Step 3 (missing metadata, unresolved codes, etc.), the Analyst resolves the gap via authoritative references and/or direct confirmation with the Product Owner — building on unverified assumptions is prohibited.

The Analyst then conducts a structured discovery session with the Product Owner covering:
- Business goals and decisions the data must support
- Consumer audience and tools
- Key performance indicators
- Required time grain
- Known business rules and constraints

**Deliverable:** Requirements section of the Master Design Document.

#### Step 5 — Draft Proposed Solution Design

Coordinator drafts the complete solution design as a coherent single plan. The design is organised into two halves:

1. **Semantic Model (what consumers will analyse)** — the user-facing contract: measures, reference entities, hierarchies, schema topology, conformed identifiers, cross-subject-area relationships, and a visual model diagram. This is drafted first because it represents what the Product Owner evaluates.
2. **Physical Implementation (how it will be delivered)** — the implementation plan: preparation layer, reference/entity tables, transactional/event tables, load strategies, test plan.

The semantic model is the target; the physical plan is its derivation.

**Deliverable:** Complete draft of the Master Design Document covering both halves.

#### Step 6 — Design Approval *(Product Owner touchpoint 2 of 2)*

Coordinator presents a concise approval summary to the Product Owner that **leads with the Semantic Model** so the Product Owner first evaluates whether the solution answers the right business questions, then reviews the implementation plan.

**Gate:** Product Owner approves or requests revisions. Build does not start without recorded approval (timestamp and approver logged in the Master Design Document).

### Phase C — Build

#### Step 7 — Prepare Project Workspace *(fresh builds only)*

Platform Engineer provisions the build workspace according to team standards: folder structure, runtime environment, tool configuration, shared macro/utility libraries, standard ignore patterns, version control initialisation, and connection settings. Incremental builds skip this step.

#### Step 8 — Load Source Data into Intake Layer

Platform Engineer stages source data into the intake/raw layer. Source files remain in their original location (copy, not move) to preserve reproducibility. Row counts are reconciled against Step 3 profiles; discrepancies are escalated to the Coordinator.

#### Step 9 — Build Data Preparation Layer *(sequential)*

Staging Modellers build one preparation model per source entity, **sequentially, not in parallel**. The first model serves as the **canary**: source-specific quirks (reserved identifiers, format surprises, encoding issues, adapter limitations) are caught and resolved on model one before the pattern is applied to the rest.

**Gate:** each preparation model must compile and execute successfully before the next is started.

#### Step 10 — Build Core Entities *(parallel, with deviation control)*

Dimension Modellers work in parallel, each in an isolated workspace. Before building, each Modeller performs a **conformance check**: the assigned build brief is compared against the approved Core Entity Plan, and every specified attribute is confirmed to exist in the prepared source data.

**Gate — Deviation control:** if any Modeller cannot deliver the entity as approved (missing attribute, type conflict, identifier mismatch), the build is completed with documented deviations and the pipeline halts. The Coordinator escalates to the Product Owner with two options:

- **Accept** — update the approved design to reflect the deviation, log the decision, resume.
- **Abort** — revise sources or the semantic target, restart from Step 5.

The pipeline does not advance to Step 11 until every deviation has been explicitly accepted by the Product Owner.

#### Step 11 — Build Transactional/Event Tables *(parallel, with deviation control)*

Fact Modellers work in parallel after all core entities are merged. Each Modeller performs the same conformance check (declared grain is enforceable, foreign keys resolve with the conformed identifiers, measures are of the expected type at the correct grain) and follows the same deviation-escalation rule as Step 10.

#### Step 12 — Author and Execute Quality Tests

QA Engineer authors tests sufficient to meet the team's coverage standard: uniqueness on identifiers, not-null on critical attributes, referential integrity, and business-rule assertions derived from the Requirements section. Tests are executed and any failures are resolved before the step is marked complete.

**Gate:** test coverage meets the approved threshold **and** all tests pass.

### Phase D — Validation and Handoff

#### Step 13 — Validate End-to-End Pipeline

Validator performs a clean end-to-end build and records the outcome. Possible statuses:

- **Validated** — full build clean, tests pass, coverage threshold met
- **Built with gaps** — build complete and tests pass, but below the coverage threshold
- **Build failed** — build or test execution failed

**Deliverable:** Validation Report section of the Master Design Document.

#### Step 14 — Handoff and Closure

Coordinator updates the Master Design Document status and, where validation succeeded, produces a handoff package including:

- Master Design Document (complete audit trail)
- Validation Report
- Any downstream-consumption scaffolding produced by the standard toolchain
- Record of any deviations accepted during Steps 10–11

Handoff is formalised by acknowledgement from the Product Owner and the downstream consumption team.

## 6. Quality gates summary

| Gate | Step | Owner | Consequence of failure |
|---|---|---|---|
| Environment verified | 1 | Coordinator | Build work cannot begin |
| Source access confirmed | 2 | Coordinator | Request returned |
| Source metadata resolved | 3–4 | Business Analyst / Product Owner | No building on unverified assumptions |
| Design approval | 6 | Product Owner | Build does not start |
| Canary preparation model | 9 | Coordinator | Resolve before scaling |
| Core entity deviation | 10 | Product Owner | Accept or abort |
| Transactional-table deviation | 11 | Product Owner | Accept or abort |
| Test coverage threshold | 12 | QA Engineer | Fix gaps or re-scope |
| Validation passed | 13 | Validator | Block handoff if failed |

## 7. Escalation

| Situation | First-line | Second-line |
|---|---|---|
| Environment or tool issue | Platform Engineer | Data Platform Team lead |
| Source access issue | Platform Engineer | Product Owner |
| Requirements unclear | Business Analyst | Product Owner |
| Build-level deviation | Pipeline Coordinator | Product Owner |
| Data quality concern | QA Engineer | Business Analyst + Product Owner |
| Schedule slippage | Pipeline Coordinator | Data Platform Team lead |

## 8. Artefacts and retention

The **Master Design Document** is the single source of truth for the pipeline and contains the complete audit trail: requirements, source inventory, design decisions, approval history, build outputs, test coverage, validation results, and any accepted deviations.

Profile artefacts, test results, and validation reports are retained alongside the Master Design Document in the project repository.

**Retention:** indefinite for as long as the pipeline is in use; archival policy follows team standard.

## 9. Related documents

- Technical process reference (tool-specific): `_Documentation/pipeline-workflow.md`
- Known issues and resolutions: `_Plan/Issues.md`
- Team lessons learned: project root `CLAUDE.md`

## 10. Document control

| Version | Date | Author | Change |
|---|---|---|---|
| 1.0 | 2026-04-21 | Data Platform Team | Initial issue |
| 1.1 | 2026-04-21 | Data Platform Team | Made tool-agnostic; reorganised into 4 phases with 14 steps |
