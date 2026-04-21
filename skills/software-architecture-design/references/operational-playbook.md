## Core Architecture Questions

Use these questions to frame any design discussion:

- **Domain:**
  - What problem is this system solving?
  - What are the core domain concepts and invariants?
- **Boundaries:**
  - How should responsibilities be split across services or modules?
  - What must stay together for strong consistency?
- **Data:**
  - What data is stored, where, and in what shape?
  - What are the consistency and durability requirements?
- **Workload:**
  - What are the expected read/write patterns?
  - How does traffic scale over time (burst vs steady)?
- **Failure:**
  - What happens when dependencies fail or degrade?
  - What are the recovery paths and fallbacks?

---

## Pattern: Layered Architecture

Use when the system is not yet highly distributed, or when clarity and separation of concerns are more important than aggressive scalability.

Typical layering:

- Presentation/API layer: HTTP or messaging interfaces, authentication, request validation.
- Application/service layer: orchestration, use cases, workflows.
- Domain layer: core business logic and invariants.
- Infrastructure layer: databases, queues, external services, file storage.

Checklist:

- Clear direction of dependencies (outer layers depend on inner, not vice versa).
- Domain code does not depend on transport or storage details.
- Cross-cutting concerns (logging, metrics, security) handled via composition, not duplication.

---

## Pattern: Service Decomposition

Use when deciding between monolith, modular monolith, and microservices.

- **Monolith:**
  - Use when the team is small and the problem space is still evolving
  - Focus on modular boundaries inside a single deployable
- **Modular monolith:**
  - Use when you need strong internal boundaries and clear ownership but still want a single deployment unit
- **Microservices:**
  - Use when you have clear bounded contexts, strong ownership boundaries, and operational maturity

**Decomposition heuristics:**

- Group code by domain boundary, not by technical layer only
- Avoid splitting entities that must be updated transactionally
- Prefer a small number of well-designed services over many tiny ones

---

## Pattern: Data and Consistency

Use when designing storage and consistency behavior.

- Choose the primary source of truth for each piece of data
- **Decide consistency model:**
  - **Strong:** transactions and immediate consistency; fewer consumers, higher coupling
  - **Eventual:** asynchronous updates; requires idempotency and reconciliation
- **Avoid writing to multiple sources in a single request without a clear strategy:**
  - Use a "single writer" or orchestrator service
  - Use outbox patterns for publishing events reliably

**Checklist:**

- Data ownership is clear for each service
- Failure modes for partial writes are understood and handled
- Migrations and schema evolution have a plan (backwards compatibility where needed)

---

## Pattern: Request-Driven vs Event-Driven

Use this pattern to decide between synchronous and asynchronous flows.

- **Request-driven (synchronous):**
  - Good for user-facing APIs needing immediate feedback
  - Latency and availability of dependencies directly affect the caller
- **Event-driven (asynchronous):**
  - Good for decoupling producers and consumers
  - Suited to background work, aggregations, notifications

**Guidelines:**

- Keep request paths shallow for user interactions; offload heavy work via events or queues
- In event-driven flows, design idempotent handlers and clear retry behaviors

---

## Pattern: Security Architecture

**Use when:** Designing secure system architectures with proper security layers and controls.

**IMPORTANT:** For comprehensive security patterns, see [../software-security-appsec/SKILL.md](../../software-security-appsec/SKILL.md) which covers:

- Defense in depth and security boundaries
- Zero trust architecture
- Threat modeling (STRIDE framework)
- Authentication & Authorization architecture
- Data protection at rest and in transit
- Secure design principles

**Architecture-Specific Security Patterns:**

- **Security Boundaries**: Define trust boundaries between layers (client → API → services → data)
- **Defense in Depth**: Layer security controls (authentication → authorization → validation → encryption)
- **Least Privilege**: Each service should have minimum necessary permissions
- **Fail Securely**: Systems should default to deny, not allow on errors
- **API Gateway Pattern**: Centralized authentication, rate limiting, logging
- **Service Mesh**: mTLS between services, zero trust networking
- **Secret Management**: Centralized secret storage (AWS Secrets Manager, Vault)

**Quick Example - Security Layers:**

```text
Client
  ↓ HTTPS + JWT
API Gateway (Auth, Rate Limit, Logging)
  ↓ Service-to-Service Auth
Backend Services (Authorization, Validation)
  ↓ Encrypted Connection
Database (Encrypted at Rest, Row-Level Security)
```

**Checklist:**

- Authentication at entry points
- Authorization on every service call
- Input validation at boundaries
- Encryption in transit (TLS)
- Encryption at rest for sensitive data
- Centralized logging for security events
- Rate limiting and DDoS protection
- Regular security audits and penetration testing

---

## External Resources

See [data/sources.json](../data/sources.json) for 42 curated references on:

- Architecture pattern catalogs (AWS, Azure, Google Cloud, Martin Fowler, microservices.io)
- Distributed systems and scalability guides (ByteByteGo, System Design)
- ADR templates and best practices (GitHub ADR org, AWS, Microsoft)
- Scalability and reliability (Google SRE Book, CAP theorem, resilience patterns)
- Event-driven architecture (AWS, Martin Fowler, CQRS, Saga patterns)
- Observability (OpenTelemetry, distributed tracing, SLI/SLO/SLA)
- API design (REST, GraphQL, gRPC, API Gateway patterns)
- Security architecture (OWASP, Zero Trust, Service Mesh security)
- Essential books (Designing Data-Intensive Applications, Building Microservices, Release It!)
