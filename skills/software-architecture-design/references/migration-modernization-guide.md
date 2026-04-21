# Migration & Modernization Guide

Step-by-step patterns for migrating from monoliths to microservices, decomposing databases, and incrementally modernizing legacy systems. Use when planning major refactors, strangler fig migrations, or database decomposition strategies.

## Contents

- [Strangler Fig Pattern](#strangler-fig-pattern)
- [Database Decomposition](#database-decomposition)
- [Feature Flags for Migration](#feature-flags-for-migration)
- [Risk Assessment Framework](#risk-assessment-framework)
- [Parallel Running and Shadow Traffic](#parallel-running-and-shadow-traffic)
- [Migration Path: Monolith to Microservices](#migration-path-monolith-to-microservices)
- [Anti-Patterns](#anti-patterns)
- [Decision Framework](#decision-framework)
- [Cross-References](#cross-references)

---

## Strangler Fig Pattern

### Core Concept

Incrementally replace pieces of a legacy system by routing traffic to new implementations while the old system remains operational. Named after strangler fig trees that grow around a host tree.

```text
Phase 1: Identify                Phase 2: Intercept              Phase 3: Replace
┌────────────────┐              ┌────────────────┐              ┌────────────────┐
│   Monolith     │              │   Facade/Proxy │              │   Facade/Proxy │
│  ┌──────────┐  │              │       │        │              │       │        │
│  │ Feature A │  │              │   ┌───┴───┐    │              │   ┌───┴───┐    │
│  │ Feature B │  │              │   │       │    │              │   │       │    │
│  │ Feature C │  │              │ Old A  New B   │              │ New A  New B   │
│  └──────────┘  │              │ Old C          │              │ New C          │
└────────────────┘              └────────────────┘              └────────────────┘
```

### Step-by-Step Implementation

**Step 1: Add a routing facade**

```typescript
// API Gateway or reverse proxy routes requests
// Start with 100% traffic to monolith

// nginx.conf or API gateway config
// location /api/orders {
//   proxy_pass http://monolith:3000;   # All traffic to monolith initially
// }
```

**Step 2: Identify extraction candidates**

Rank modules by these criteria:

| Criterion | Weight | Description |
|-----------|--------|-------------|
| Business value of independent deployment | High | Revenue impact, release frequency needs |
| Coupling to other modules | High | Fewer dependencies = easier extraction |
| Team ownership clarity | Medium | Clear owner = better extraction outcome |
| Data isolation feasibility | High | Shared tables make extraction hard |
| Change frequency | Medium | Frequently changed code benefits most |
| Performance isolation needs | Medium | One module's load affecting another |

**Step 3: Build the new service**

```typescript
// New service implements the SAME interface as the monolith feature
// This is critical — callers should not know about the migration

// New orders-service (standalone)
app.post('/api/orders', async (req, res) => {
  // New implementation with same API contract
  const order = await createOrder(req.body);
  res.json(order);
});
```

**Step 4: Gradual traffic shift**

```yaml
# Canary routing: shift traffic incrementally
# Week 1: 5% to new service
# Week 2: 25% to new service
# Week 3: 50% to new service
# Week 4: 100% to new service (if metrics are green)

# Example: Istio VirtualService
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: orders
spec:
  hosts:
    - orders.example.com
  http:
    - route:
        - destination:
            host: orders-new
          weight: 25
        - destination:
            host: monolith
          weight: 75
```

**Step 5: Decommission the old code**

After 100% traffic runs on the new service with stable metrics for at least 2 weeks:

- [ ] Remove old code path from monolith
- [ ] Remove old database tables (after data migration verification)
- [ ] Update documentation and runbooks
- [ ] Remove feature flags related to migration

---

## Database Decomposition

### Shared Database Problem

```text
[FAIL] Multiple services sharing one database:
  ┌─────────┐  ┌─────────┐  ┌─────────┐
  │Service A│  │Service B│  │Service C│
  └────┬────┘  └────┬────┘  └────┬────┘
       │            │            │
       └────────────┼────────────┘
                    │
            ┌───────▼───────┐
            │  Shared DB    │
            │  (everything) │
            └───────────────┘

Problems:
- Schema changes break multiple services
- No independent deployment
- Performance contention
- Unclear data ownership
```

### Decomposition Strategies

**Strategy 1: Database View Layer**

Intermediate step. Create views that simulate per-service schemas.

```sql
-- Service A sees only its data through a view
CREATE VIEW service_a_orders AS
SELECT id, customer_id, total, status, created_at
FROM orders
WHERE department = 'retail';

-- Service B sees different columns
CREATE VIEW service_b_orders AS
SELECT id, warehouse_id, shipping_status, tracking_number
FROM orders
WHERE shipping_status IS NOT NULL;
```

**Strategy 2: Schema-Per-Service (Same Instance)**

Each service gets its own schema within the same database instance.

```sql
-- Separate schemas, same PostgreSQL instance
CREATE SCHEMA orders_service;
CREATE SCHEMA inventory_service;
CREATE SCHEMA payments_service;

-- Each service's migrations target its own schema
-- Cross-schema access is explicitly forbidden (enforce via permissions)
REVOKE ALL ON SCHEMA orders_service FROM inventory_user;
```

**Strategy 3: Database-Per-Service (Full Separation)**

Each service has its own database instance.

```text
┌─────────┐       ┌─────────┐       ┌─────────┐
│Service A│       │Service B│       │Service C│
└────┬────┘       └────┬────┘       └────┬────┘
     │                 │                 │
┌────▼────┐       ┌────▼────┐       ┌────▼────┐
│  DB A   │       │  DB B   │       │  DB C   │
└─────────┘       └─────────┘       └─────────┘
```

### Data Synchronization During Decomposition

| Approach | Description | When |
|----------|-------------|------|
| Dual writes | Write to both old and new DB | Short transition periods only |
| CDC (Change Data Capture) | Stream changes from old to new | Gradual migration, minimal code changes |
| ETL batch sync | Periodic bulk sync | Non-real-time data, analytics |
| API calls | New service fetches data via API | Loosely coupled, eventually consistent |

**CDC Example with Debezium:**

```json
{
  "name": "orders-connector",
  "config": {
    "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
    "database.hostname": "monolith-db",
    "database.port": "5432",
    "database.dbname": "monolith",
    "table.include.list": "public.orders,public.order_items",
    "topic.prefix": "migration",
    "slot.name": "orders_migration"
  }
}
```

### Join Elimination Strategies

When decomposing a shared database, you lose cross-table joins. Solutions:

| Pattern | Use When | Trade-off |
|---------|----------|-----------|
| API composition | Low-frequency queries, few services | Latency from multiple API calls |
| Data denormalization | Read-heavy, stale data OK | Storage duplication, sync complexity |
| Event-driven sync | Real-time needs, owned data changes | Eventual consistency |
| Materialized views in read DB | Complex reporting queries | Additional infrastructure |

---

## Feature Flags for Migration

### Migration-Specific Flag Patterns

```typescript
// Flag: route traffic to new vs old implementation
const flags = {
  'orders-service-v2': {
    type: 'percentage',
    value: 25,  // 25% of traffic to new service
    metadata: {
      migration: 'orders-extraction',
      startDate: '2026-01-15',
      targetCompletion: '2026-03-01',
      rollbackPlan: 'Set to 0%, revert proxy config',
    },
  },
};

// Usage in routing layer
async function handleOrderRequest(req: Request): Promise<Response> {
  if (featureFlags.isEnabled('orders-service-v2', { userId: req.userId })) {
    return newOrdersService.handle(req);
  }
  return monolith.handle(req);
}
```

### Flag Lifecycle for Migrations

```text
Phase 1: Create flag (default: OFF)
Phase 2: Enable for internal users (testing)
Phase 3: Enable for 5% of traffic (canary)
Phase 4: Ramp to 25%, 50%, 75%, 100%
Phase 5: Remove flag + old code path (cleanup)

IMPORTANT: Set a cleanup deadline. Stale flags are tech debt.
```

### Comparison Read Pattern

```typescript
// During migration: read from BOTH, compare results, return old
async function getOrder(orderId: string): Promise<Order> {
  const oldResult = await monolith.getOrder(orderId);

  if (featureFlags.isEnabled('orders-comparison-reads')) {
    try {
      const newResult = await newService.getOrder(orderId);
      if (!deepEqual(oldResult, newResult)) {
        logger.warn('Migration mismatch', {
          orderId,
          diff: generateDiff(oldResult, newResult),
        });
        metrics.increment('migration.comparison.mismatch');
      } else {
        metrics.increment('migration.comparison.match');
      }
    } catch (error) {
      metrics.increment('migration.comparison.error');
    }
  }

  return oldResult; // Always return the trusted source during migration
}
```

---

## Risk Assessment Framework

### Migration Risk Matrix

| Risk Factor | Low Risk | Medium Risk | High Risk |
|-------------|----------|-------------|-----------|
| Data coupling | No shared tables | Shared lookup tables | Shared mutable tables with joins |
| Traffic volume | <100 req/s | 100–1000 req/s | >1000 req/s |
| Consistency requirements | Eventual OK | Read-your-writes needed | Strong ACID required |
| Team experience | Done migrations before | Some distributed systems experience | First microservice extraction |
| Rollback complexity | Stateless, easy revert | Some state to reconcile | Data divergence makes rollback hard |
| Business criticality | Internal tool | Customer-facing, non-revenue | Payment, checkout, auth |

### Risk Mitigation Checklist

- [ ] **Runbook** written for rollback (with specific steps, not "revert changes")
- [ ] **Monitoring** dashboards ready before migration starts
- [ ] **Alerts** configured for error rate increase, latency spikes
- [ ] **Data reconciliation** script ready to compare old vs new
- [ ] **Communication plan** for stakeholders (downtime windows, expected behavior changes)
- [ ] **Rollback tested** in staging environment
- [ ] **Feature flag** wired for instant traffic revert
- [ ] **Incremental rollout** plan with go/no-go criteria at each stage

### Go/No-Go Criteria Per Phase

| Metric | Green (Go) | Yellow (Pause) | Red (Rollback) |
|--------|------------|----------------|-----------------|
| Error rate | <0.1% increase | 0.1–1% increase | >1% increase |
| P95 latency | <10% increase | 10–50% increase | >50% increase |
| Data mismatches | <0.01% | 0.01–0.1% | >0.1% |
| Business metric (conversion, etc.) | No change | <2% drop | >2% drop |

---

## Parallel Running and Shadow Traffic

### Shadow Traffic Pattern

Route a copy of production traffic to the new service without affecting users.

```text
┌────────┐     ┌──────────────┐     ┌────────────┐
│ Client │────▶│  Proxy/LB    │────▶│  Monolith  │──▶ Response to client
└────────┘     └──────┬───────┘     └────────────┘
                      │ (async copy)
                      └──────────────▶┌─────────────┐
                                      │ New Service  │──▶ Response discarded
                                      └─────────────┘     (logged + compared)
```

### Implementation

```typescript
// Shadow traffic middleware
async function shadowTraffic(req: Request, res: Response, next: NextFunction) {
  // 1. Process the real request normally
  next();

  // 2. Asynchronously send a copy to the new service (fire-and-forget)
  if (featureFlags.isEnabled('shadow-traffic-orders')) {
    setImmediate(async () => {
      try {
        const shadowStart = Date.now();
        const shadowResponse = await newService.mirror(req);
        const shadowLatency = Date.now() - shadowStart;

        metrics.histogram('shadow.latency', shadowLatency);

        // Compare responses (logged, not returned to client)
        if (res.locals.responseBody) {
          const match = deepEqual(res.locals.responseBody, shadowResponse);
          metrics.increment(match ? 'shadow.match' : 'shadow.mismatch');
        }
      } catch (error) {
        metrics.increment('shadow.error');
        // Failures in shadow traffic NEVER affect the real response
      }
    });
  }
}
```

### Parallel Running Checklist

- [ ] Shadow traffic does NOT mutate production data
- [ ] Shadow requests are clearly marked (header: `X-Shadow: true`)
- [ ] New service has separate database/storage from production
- [ ] Comparison results are aggregated into dashboards
- [ ] Shadow traffic can be turned off instantly via feature flag
- [ ] Load from shadow traffic is accounted for in capacity planning

---

## Migration Path: Monolith to Microservices

### Recommended Progression

```text
Stage 1: Modular Monolith
  └─ Enforce module boundaries within the monolith
  └─ Define clear APIs between modules
  └─ Separate schemas per module (same DB)
  └─ Duration: 2-6 months

Stage 2: Extract First Service
  └─ Pick the module with least coupling
  └─ Use strangler fig + shadow traffic
  └─ Establish service infrastructure (CI/CD, monitoring, service mesh)
  └─ Duration: 1-3 months

Stage 3: Extract Core Services
  └─ Extract 2-4 more services in parallel (different teams)
  └─ Introduce async messaging for cross-service communication
  └─ Decompose database per service
  └─ Duration: 3-9 months

Stage 4: Steady State
  └─ New features built as services by default
  └─ Remaining monolith handles only legacy features
  └─ Monolith shrinks over time (or stays as a module)
```

### Case Study Pattern: E-Commerce Migration

| Phase | Extract | Why First | Risk Level |
|-------|---------|-----------|------------|
| 1 | Notifications | No writes to core data, read-only | Low |
| 2 | Search/Catalog | Heavy reads, independent index | Low-Medium |
| 3 | Inventory | Clear bounded context, event-driven | Medium |
| 4 | Orders | Core domain, complex state machine | High |
| 5 | Payments | Regulatory, compliance needs isolation | High |
| 6 | User/Auth | Shared dependency, extract last | Very High |

**Key principle:** Extract the easiest services first to build team confidence and infrastructure. Save the hardest (most coupled, most critical) for last.

---

## Migration Plan Binding

Migration plans are only executable when architecture, controls, and rollout mechanics are bound together in a single coherent plan:

- **Target-state decisions** must be connected to pilot-provider rollout sequencing, degraded modes, cutover controls, readiness checks, and decommission sequencing.
- Architecture proposals alone are not enough — the plan needs explicit stages, open-gap tracking, and clear acknowledgement of what is still unresolved.
- Roadmaps, trackers, and architecture docs must stay synchronized in the same delivery cycle. When they drift, they become contradictory instructions for the next implementation session.
- Distinguish verified current state, selected target state, and unresolved gaps in all migration documentation. Flattening them together makes docs unsafe to trust.

### Migration Plan Checklist

- [ ] Target architecture documented with explicit boundaries
- [ ] Pilot-provider or canary rollout sequence defined
- [ ] Degraded mode behavior specified (what happens when new path fails)
- [ ] Cutover controls identified (feature flags, traffic routing, kill switches)
- [ ] Readiness checks listed (what must be true before each phase advances)
- [ ] Decommission sequencing planned (what gets removed, when, and by whom)
- [ ] Open gaps explicitly tracked with owners
- [ ] Roadmap, architecture doc, and gap tracker synchronized

---

## Anti-Patterns

### 1. Big Bang Rewrite

```text
[FAIL] "Let's rewrite the entire monolith as microservices over 6 months"
       → Delayed value delivery, high risk, second-system effect, team burnout

[PASS] Incremental extraction with strangler fig. Ship value every 2-4 weeks.
       Each extraction is independently valuable and rollback-safe.
```

### 2. Premature Decomposition

```text
[FAIL] Splitting into 20 microservices before understanding domain boundaries
       → Distributed monolith, wrong service boundaries, expensive to fix

[PASS] Start with a modular monolith. Let boundaries emerge from real usage.
       Extract services only when you have clear, stable bounded contexts.
```

### 3. Shared Database Migration

```text
[FAIL] Extracting services but keeping the shared database
       → Services are coupled at the data layer, no independent deployment

[PASS] Database decomposition is part of the migration plan, not an afterthought.
       Use the view layer or schema-per-service as intermediate steps.
```

### 4. No Rollback Plan

```text
[FAIL] "We'll figure out rollback if something goes wrong"
       → Panic during incidents, data loss, extended outages

[PASS] Write the rollback runbook BEFORE starting migration.
       Test rollback in staging. Include data reconciliation steps.
```

### 5. Ignoring Data Migration

```text
[FAIL] Extracting the service but leaving historical data in the monolith
       → Split brain, queries return partial results, reporting breaks

[PASS] Plan data migration as a first-class concern. Include:
       - Historical data transfer
       - Data format transformation
       - Validation and reconciliation
       - Cutover strategy
```

### 6. Migrating Without Observability

```text
[FAIL] Extracting services without distributed tracing or unified logging
       → Impossible to debug issues across service boundaries

[PASS] Set up observability BEFORE the first extraction:
       - Distributed tracing (OpenTelemetry)
       - Centralized logging with correlation IDs
       - Service-level dashboards and alerts
```

---

## Decision Framework

### Should You Migrate at All?

```text
1. Are deployment bottlenecks hurting business velocity?    [Yes → +2, No → 0]
2. Do different parts of the system need different scaling? [Yes → +2, No → 0]
3. Are multiple teams blocked by monolith coupling?         [Yes → +2, No → 0]
4. Is the monolith technically healthy (tests, CI, docs)?   [Yes → +1, No → -1]
5. Does the team have distributed systems experience?       [Yes → +1, No → -2]
6. Is there executive buy-in for a multi-quarter effort?    [Yes → +1, No → -2]

Score: 0–3 → Improve the monolith (modularize, add tests, fix CI)
Score: 4–6 → Start with modular monolith, plan first extraction
Score: 7+  → Begin migration with strangler fig approach
```

### Extraction Order Prioritization

Score each module (1-5 per criterion), extract in descending total order:

| Module | Coupling (inverse) | Change Frequency | Business Value | Team Readiness | Total |
|--------|-------------------|-----------------|----------------|----------------|-------|
| Module A | ? | ? | ? | ? | ? |

---

## Cross-References

- [modern-patterns.md](modern-patterns.md) — Architecture patterns overview (microservices, modular monolith)
- [data-architecture-patterns.md](data-architecture-patterns.md) — CQRS, event sourcing, saga patterns for distributed data
- [scalability-reliability-guide.md](scalability-reliability-guide.md) — Scaling strategies post-migration
- [api-gateway-service-mesh.md](api-gateway-service-mesh.md) — Service mesh and gateway patterns for microservices
- [../software-backend/SKILL.md](../software-backend/SKILL.md) — Service-level implementation patterns
- [../../ops-devops-platform/SKILL.md](../../ops-devops-platform/SKILL.md) — CI/CD and deployment for microservices
