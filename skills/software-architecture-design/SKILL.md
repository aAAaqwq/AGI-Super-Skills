---
name: software-architecture-design
description: Designs system structure across monolith/microservices/serverless. Use when structuring systems, scaling, decomposing monoliths, or choosing patterns.
---

# Software Architecture Design — Quick Reference

Use this skill for **system-level design decisions** rather than implementation details within a single service or component.

## Quick Reference

| Task | Pattern/Tool | Key Resources | When to Use |
|------|-------------|---------------|-------------|
| Choose architecture style | Layered, Microservices, Event-driven, Serverless | [modern-patterns.md](references/modern-patterns.md) | Greenfield projects, major refactors |
| Design for scale | Load balancing, Caching, Sharding, Read replicas | [scalability-reliability-guide.md](references/scalability-reliability-guide.md) | High-traffic systems, performance goals |
| Ensure resilience | Circuit breakers, Retries, Bulkheads, Graceful degradation | [scalability-reliability-guide.md](references/scalability-reliability-guide.md) | Distributed systems, external dependencies |
| Document decisions | Architecture Decision Record (ADR) | [adr-template.md](assets/planning/adr-template.md) | Major technical decisions, tradeoff analysis |
| Define service boundaries | Domain-Driven Design (DDD), Bounded contexts | [microservices-template.md](assets/patterns/microservices-template.md) | Microservices decomposition |
| Model data consistency | ACID vs BASE, Event sourcing, CQRS, Saga patterns | [data-architecture-patterns.md](references/data-architecture-patterns.md) | Multi-service transactions |
| Plan observability | SLIs/SLOs/SLAs, Distributed tracing, Metrics, Logs | [architecture-blueprint.md](assets/planning/architecture-blueprint.md) | Production readiness |
| Migrate from monolith | Strangler fig, Database decomposition, Shadow traffic | [migration-modernization-guide.md](references/migration-modernization-guide.md) | Legacy modernization |
| Design inter-service comms | API Gateway, Service mesh, BFF pattern | [api-gateway-service-mesh.md](references/api-gateway-service-mesh.md) | Microservices networking |

## When to Use This Skill

Invoke when working on:

- **System decomposition**: Deciding between monolith, modular monolith, microservices
- **Architecture patterns**: Event-driven, CQRS, layered, hexagonal, serverless
- **Data architecture**: Consistency models, sharding, replication, CQRS patterns
- **Scalability design**: Load balancing, caching strategies, database scaling
- **Resilience patterns**: Circuit breakers, retries, bulkheads, graceful degradation
- **API contracts**: Service boundaries, versioning, integration patterns
- **Architecture decisions**: ADRs, tradeoff analysis, technology selection
- **Migration planning**: Monolith decomposition, strangler fig, database separation

## When NOT to Use This Skill

Use other skills instead for:

- **Single-service implementation** (routes, controllers, business logic) → [software-backend](../software-backend/SKILL.md)
- **API endpoint design** (REST conventions, GraphQL schemas) → [dev-api-design](../dev-api-design/SKILL.md)
- **Security implementation** (auth, encryption, OWASP) → [software-security-appsec](../software-security-appsec/SKILL.md)
- **Frontend component architecture** → [software-frontend](../software-frontend/SKILL.md)
- **Database query optimization** → [data-sql-optimization](../data-sql-optimization/SKILL.md)

## Decision Tree: Choosing Architecture Pattern

```text
Project needs: [New System or Major Refactor]
    ├─ Single team, evolving domain?
    │   ├─ Start simple → Modular Monolith (clear module boundaries)
    │   └─ Need rapid iteration → Layered Architecture
    │
    ├─ Multiple teams, clear bounded contexts?
    │   ├─ Independent deployment critical → Microservices
    │   └─ Shared data model → Modular Monolith with service modules
    │
    ├─ Event-driven workflows?
    │   ├─ Asynchronous processing → Event-Driven Architecture (Kafka, queues)
    │   └─ Complex state machines → Saga pattern + Event Sourcing
    │
    ├─ Variable/unpredictable load?
    │   ├─ Pay-per-use model → Serverless (AWS Lambda, Cloudflare Workers)
    │   └─ Batch processing → Serverless + queues
    │
    └─ High consistency requirements?
        ├─ Strong ACID guarantees → Monolith or Modular Monolith
        └─ Distributed data → CQRS + Event Sourcing
```

**Decision Factors:**

- **Team size threshold**: <10 developers → modular monolith typically outperforms microservices (operational overhead)
- Team structure (Conway's Law) — architecture mirrors org structure
- Deployment independence needs
- Consistency vs availability tradeoffs (CAP theorem)
- Operational maturity (monitoring, orchestration)

See [references/modern-patterns.md](references/modern-patterns.md) for detailed pattern descriptions.

## Output Guidelines

The references in this skill are background knowledge for you — absorb the patterns and present them as your own expertise. Do not cite internal reference file names (e.g., "from data-architecture-patterns.md") in user-facing output. Users don't know these files exist.

Every architecture recommendation should include:

- **Concrete technology picks**: Name specific technologies (e.g., "Temporal.io for workflow orchestration", "Socket.io with Redis adapter") rather than staying abstract. The user needs to make build decisions, not just understand patterns.
- **What NOT to build**: Explicitly call out what to defer or avoid. Premature scope is the #1 architecture mistake — help the user avoid it.
- **Team and process alignment**: How does this architecture map to team structure? What ownership model does it imply? Include CODEOWNERS, deployment ownership, and on-call boundaries where relevant.
- **Success metrics**: How will the team know the architecture is working? Include measurable indicators (deploy frequency, lead time, error rates, MTTR).
- **Focused length**: Aim for depth on the 3–5 decisions that matter most rather than exhaustive coverage of every concern. A recommendation that's too long to read is a recommendation that won't be followed.

## Workflow (System-Level)

Use this workflow when a user asks for architecture recommendations, decomposition, or major platform decisions.

1. Clarify: problem statement, non-goals, constraints, and success metrics
2. Capture quality attributes: availability, latency, throughput, durability, consistency, security, compliance, cost
3. Propose 2–3 candidate architectures and compare tradeoffs
4. Define boundaries: bounded contexts, ownership, APIs/events, integration contracts
5. Decide data strategy: storage, consistency model, schema evolution, migrations
6. Design for operations: SLOs, failure modes, observability, deployment, DR, incident playbooks
7. Call out scope limits: what NOT to build yet, what to defer, what to buy vs build
8. Document decisions: write ADRs for key tradeoffs and irreversible choices

Preferred deliverables (pick what fits the request):

- Architecture blueprint: `assets/planning/architecture-blueprint.md`
- Decision record: `assets/planning/adr-template.md`
- Pattern deep dives: `references/modern-patterns.md`, `references/scalability-reliability-guide.md`

## 2026 Considerations

Load only when the question explicitly involves current trends, vendor-specific constraints, or "what's the latest thinking on X?"

- [references/architecture-trends-2026.md](references/architecture-trends-2026.md) — Platform engineering, data mesh, composable architecture, AI-native systems
- [data/sources.json](data/sources.json) — 60 curated resources organized by category:
  - `platform_engineering_2026` — IDP trends, AI-platform convergence, Backstage
  - `optional_ai_architecture` — RAG patterns, multi-agent design, MCP/A2A protocols
  - `modern_architecture_2025` — Data mesh, composable architecture, continuous architecture

If live web access is available, consult 2–3 authoritative sources from `data/sources.json` and fold findings into the recommendation. If not, answer with durable patterns and explicitly state assumptions that could change (vendor limits, pricing, managed-service capabilities).

## Navigation

### Core References

Read **at most 2–3 references** per question — pick the ones most relevant to the specific ask. Do not read all of them.

| Reference | Contents | When to Read |
|-----------|----------|--------------|
| [modern-patterns.md](references/modern-patterns.md) | 10 architecture patterns with decision trees | Choosing or comparing patterns |
| [scalability-reliability-guide.md](references/scalability-reliability-guide.md) | CAP theorem, DB scaling, caching, circuit breakers, SRE | Scaling or reliability questions |
| [data-architecture-patterns.md](references/data-architecture-patterns.md) | CQRS variants, event sourcing, data mesh, sagas, consistency | Data flow across services |
| [migration-modernization-guide.md](references/migration-modernization-guide.md) | Strangler fig, DB decomposition, feature flags, risk assessment | Refactoring a monolith |
| [api-gateway-service-mesh.md](references/api-gateway-service-mesh.md) | Gateway patterns, service mesh, mTLS, observability | Inter-service communication |
| [architecture-trends-2026.md](references/architecture-trends-2026.md) | Platform engineering, data mesh, AI-native systems | Current trends only |
| [operational-playbook.md](references/operational-playbook.md) | Architecture questions framework, decomposition heuristics | Design discussion framing |

### Templates

**Planning & Documentation** ([assets/planning/](assets/planning/)):

- [architecture-blueprint.md](assets/planning/architecture-blueprint.md) — Service blueprint (dependencies, SLAs, data flows, resilience, security, observability)
- [adr-template.md](assets/planning/adr-template.md) — Architecture Decision Record for tradeoff analysis

**Architecture Patterns** ([assets/patterns/](assets/patterns/)):

- [microservices-template.md](assets/patterns/microservices-template.md) — Microservices design (API contracts, resilience, deployment, testing)
- [event-driven-template.md](assets/patterns/event-driven-template.md) — Event-driven architecture (event schemas, saga patterns, event sourcing)

**Operations** ([assets/operations/](assets/operations/)):

- [scalability-checklist.md](assets/operations/scalability-checklist.md) — Scalability checklist (DB scaling, caching, load testing, auto-scaling, DR)

### Related Skills

- [software-backend](../software-backend/SKILL.md) — Backend engineering, API implementation, data layer
- [software-frontend](../software-frontend/SKILL.md) — Frontend architecture, micro-frontends, state management
- [dev-api-design](../dev-api-design/SKILL.md) — REST, GraphQL, gRPC design patterns
- [ops-devops-platform](../ops-devops-platform/SKILL.md) — CI/CD, deployment strategies, IaC
- [qa-observability](../qa-observability/SKILL.md) — Monitoring, tracing, alerting, SLOs
- [software-security-appsec](../software-security-appsec/SKILL.md) — Threat modeling, auth, secure design
- [data-sql-optimization](../data-sql-optimization/SKILL.md) — Database design, optimization, indexing
- [docs-codebase](../docs-codebase/SKILL.md) — Architecture documentation, C4 diagrams, ADRs
