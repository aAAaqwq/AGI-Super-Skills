# Data Architecture Patterns

Comprehensive guide to data architecture patterns for distributed systems: CQRS, event sourcing, data mesh, polyglot persistence, saga patterns, and consistency models. Use when designing data flows across service boundaries, choosing storage strategies, or managing distributed state.

## Contents

- [CQRS Implementation Patterns](#cqrs-implementation-patterns)
- [Event Sourcing](#event-sourcing)
- [Data Mesh](#data-mesh)
- [Polyglot Persistence](#polyglot-persistence)
- [Saga Patterns](#saga-patterns)
- [Consistency Models](#consistency-models)
- [Anti-Patterns](#anti-patterns)
- [Decision Framework](#decision-framework)
- [Cross-References](#cross-references)

---

## CQRS Implementation Patterns

### When to Use CQRS

| Indicator | Strength |
|-----------|----------|
| Read/write ratio > 10:1 | Strong signal |
| Read and write models differ structurally | Strong signal |
| Independent scaling of reads vs writes needed | Strong signal |
| Simple CRUD with uniform access | Do NOT use CQRS |
| Small team, single database | Do NOT use CQRS |
| Prototype or MVP stage | Do NOT use CQRS |

### CQRS Variants

**Variant 1: Same Database, Separate Models**

Simplest form. Single database with distinct read/write code paths.

```typescript
// Write side — normalized, validated
class OrderCommandHandler {
  async createOrder(cmd: CreateOrderCommand): Promise<void> {
    const order = Order.create(cmd.customerId, cmd.items);
    await this.writeRepo.save(order);          // normalized tables
    await this.eventBus.publish(order.events);  // domain events
  }
}

// Read side — denormalized, optimized for queries
class OrderQueryHandler {
  async getCustomerDashboard(customerId: string): Promise<Dashboard> {
    // Single query against a denormalized view or materialized table
    return this.readRepo.getDashboard(customerId);
  }
}
```

**Variant 2: Separate Databases**

Write DB (normalized, ACID) + Read DB (denormalized, optimized). Sync via events.

```text
┌──────────────┐     events     ┌──────────────────┐
│  Write DB    │ ──────────────▶│  Read DB          │
│  (Postgres)  │                │  (Elasticsearch / │
│  normalized  │                │   Redis / Mongo)  │
└──────────────┘                └──────────────────┘
```

**Variant 3: CQRS + Event Sourcing**

Write side stores events as source of truth. Read side projects events into queryable models.

### Synchronization Strategies

| Strategy | Latency | Complexity | Use When |
|----------|---------|------------|----------|
| Synchronous (same transaction) | Zero | Low | Same-DB variant, simple reads |
| Async via domain events | Seconds | Medium | Separate DBs, eventual consistency OK |
| Change Data Capture (CDC) | Sub-second | Medium | Existing DB, no event bus yet |
| Polling projectors | Seconds–minutes | Low | Batch reporting, analytics |

### Projection Patterns

```typescript
// Event handler that maintains a read model
class OrderProjection {
  async handleOrderCreated(event: OrderCreatedEvent): Promise<void> {
    await this.readDb.customerOrders.upsert({
      customerId: event.customerId,
      orderId: event.orderId,
      status: 'created',
      total: event.total,
      itemCount: event.items.length,
      createdAt: event.timestamp,
    });
  }

  async handleOrderShipped(event: OrderShippedEvent): Promise<void> {
    await this.readDb.customerOrders.update(
      { orderId: event.orderId },
      { status: 'shipped', shippedAt: event.timestamp }
    );
  }

  // Rebuild: replay all events from the event store
  async rebuild(): Promise<void> {
    await this.readDb.customerOrders.truncate();
    const events = await this.eventStore.readAll('Order');
    for (const event of events) {
      await this.handle(event);
    }
  }
}
```

---

## Event Sourcing

### Core Concepts

Event sourcing stores every state change as an immutable event. Current state is derived by replaying events.

```text
Event Store (append-only log):
  [OrderCreated] → [ItemAdded] → [ItemAdded] → [OrderPaid] → [OrderShipped]

Current State = fold(initialState, events)
```

### When to Use Event Sourcing

| Good Fit | Poor Fit |
|----------|----------|
| Audit trail is a business requirement | Simple CRUD with no audit needs |
| Need to answer "how did we get here?" | High-throughput writes with no read-back |
| Complex domain with temporal queries | Team unfamiliar with event-driven design |
| Event-driven architecture already in place | Tight latency requirements on reads (without CQRS) |
| Regulatory compliance (financial, healthcare) | Schema changes are frequent and unpredictable |

### Event Store Design

```typescript
interface DomainEvent {
  eventId: string;          // UUID, globally unique
  aggregateId: string;      // Entity this event belongs to
  aggregateType: string;    // e.g., 'Order', 'Account'
  eventType: string;        // e.g., 'OrderCreated', 'ItemAdded'
  version: number;          // Monotonic per aggregate
  timestamp: string;        // ISO 8601
  data: Record<string, unknown>;  // Event payload
  metadata: {
    correlationId: string;  // Trace through the system
    causationId: string;    // Which command caused this
    userId?: string;        // Who triggered it
  };
}
```

**Storage options:**

| Store | Strengths | Trade-offs |
|-------|-----------|------------|
| EventStoreDB | Purpose-built, projections, subscriptions | Operational overhead of specialized DB |
| PostgreSQL (append-only table) | Familiar, ACID, good tooling | Must build projection infrastructure |
| DynamoDB / Cosmos DB | Managed, scalable | Ordering guarantees require careful key design |
| Kafka (as event store) | High throughput, retention | Not a true event store (no per-aggregate reads) |

### Snapshots

Snapshots prevent replaying thousands of events for every state reconstruction.

```typescript
class OrderAggregate {
  private version = 0;
  private state: OrderState;
  private static SNAPSHOT_INTERVAL = 100;

  async load(aggregateId: string): Promise<void> {
    // 1. Load latest snapshot (if any)
    const snapshot = await this.snapshotStore.getLatest(aggregateId);
    if (snapshot) {
      this.state = snapshot.state;
      this.version = snapshot.version;
    }

    // 2. Replay events AFTER the snapshot
    const events = await this.eventStore.readFrom(
      aggregateId,
      this.version + 1
    );
    for (const event of events) {
      this.apply(event);
    }
  }

  async save(newEvents: DomainEvent[]): Promise<void> {
    await this.eventStore.append(this.aggregateId, newEvents, this.version);
    this.version += newEvents.length;

    // 3. Create snapshot periodically
    if (this.version % OrderAggregate.SNAPSHOT_INTERVAL === 0) {
      await this.snapshotStore.save({
        aggregateId: this.aggregateId,
        version: this.version,
        state: this.state,
      });
    }
  }
}
```

### Schema Evolution for Events

Events are immutable once stored. Handle schema changes with:

1. **Upcasting** — Transform old events to new shape at read time
2. **Versioned event types** — `OrderCreated_v2` with migration logic
3. **Weak schema** — Keep events loosely typed, validate at projection

```typescript
// Upcaster example
function upcast(event: DomainEvent): DomainEvent {
  if (event.eventType === 'OrderCreated' && !event.data.currency) {
    return { ...event, data: { ...event.data, currency: 'USD' } };
  }
  return event;
}
```

---

## Data Mesh

### Principles

Data mesh treats data as a product, owned by domain teams rather than a centralized data team.

| Principle | Description |
|-----------|-------------|
| Domain ownership | Each domain team owns, produces, and serves its data |
| Data as a product | Data has SLOs, documentation, discoverability, quality guarantees |
| Self-serve platform | Central platform provides tooling, not data pipelines |
| Federated governance | Standards are global, enforcement is local |

### Data Product Structure

```text
orders-domain/
├── data-products/
│   ├── order-events/           # Real-time event stream
│   │   ├── schema.avro
│   │   ├── slo.yaml            # Freshness, completeness, accuracy
│   │   └── README.md           # Discovery documentation
│   ├── order-metrics/          # Aggregated metrics
│   │   ├── schema.sql
│   │   └── slo.yaml
│   └── order-snapshots/        # Periodic full snapshots
│       ├── schema.parquet
│       └── slo.yaml
├── pipelines/                  # Domain-owned transformations
└── contracts/                  # Input/output contracts
```

### Data Product Quality Checklist

- [ ] Schema is versioned and published to a registry
- [ ] SLOs defined: freshness (<N minutes), completeness (>99%), accuracy
- [ ] Documentation: purpose, owner, schema, access patterns, known limitations
- [ ] Discoverability: registered in data catalog
- [ ] Access control: RBAC or attribute-based access
- [ ] Monitoring: alerting on SLO violations

### Federated Governance Model

| Global Standards (Central) | Local Standards (Domain) |
|---------------------------|-------------------------|
| Naming conventions | Schema design choices |
| Security and access policies | Transformation logic |
| Data classification (PII, etc.) | Refresh cadence |
| Interoperability formats | Internal storage format |
| Quality SLO minimums | Quality SLO targets above minimum |

---

## Polyglot Persistence

### Choosing the Right Database Per Service

| Use Case | Recommended Store | Why |
|----------|-------------------|-----|
| Transactional business data | PostgreSQL / MySQL | ACID, relational integrity, mature tooling |
| Document-oriented, flexible schema | MongoDB / DynamoDB | Schema flexibility, horizontal scaling |
| Full-text search | Elasticsearch / Typesense | Inverted index, relevance scoring |
| Caching, sessions, real-time | Redis / Valkey / Dragonfly | Sub-ms latency, pub/sub, TTL |
| Time-series metrics | TimescaleDB / InfluxDB | Time-partitioned storage, rollups |
| Graph relationships | Neo4j / Amazon Neptune | Traversal queries, relationship-first |
| Event streams | Kafka / Redpanda | Ordered append-only log, high throughput |
| Analytics / OLAP | ClickHouse / BigQuery / Snowflake | Columnar storage, fast aggregations |
| Binary/object storage | S3 / GCS / R2 | Cheap, durable, scalable blob storage |

### Decision Criteria

```text
Choosing a database:
  ├─ What is the access pattern?
  │   ├─ Key-value lookups → Redis, DynamoDB
  │   ├─ Complex joins → PostgreSQL
  │   ├─ Free-text search → Elasticsearch
  │   └─ Graph traversal → Neo4j
  ├─ What are the consistency needs?
  │   ├─ Strong ACID → PostgreSQL, MySQL
  │   └─ Eventual consistency OK → DynamoDB, Cassandra
  ├─ What is the write volume?
  │   ├─ < 10K writes/sec → PostgreSQL handles it
  │   └─ > 100K writes/sec → Kafka, Cassandra, DynamoDB
  └─ What is the data lifecycle?
      ├─ Short-lived (cache) → Redis with TTL
      ├─ Append-only (logs) → Kafka, ClickHouse
      └─ Long-lived (records) → PostgreSQL, S3
```

### Operational Considerations

| Factor | Impact |
|--------|--------|
| Backup and restore | Each DB has different tooling; automate all |
| Connection management | Pooling differs per store; budget connections |
| Monitoring | Unified dashboards across heterogeneous stores |
| Schema migrations | Coordinate across services during deploys |
| Team expertise | Each new DB adds cognitive load |

**Rule of thumb:** Start with one database (usually PostgreSQL). Add specialized stores only when PostgreSQL demonstrably cannot meet a specific access pattern or performance requirement.

---

## Saga Patterns

### Orchestration vs Choreography

| Aspect | Orchestration | Choreography |
|--------|---------------|--------------|
| Coordination | Central orchestrator directs steps | Each service listens and reacts |
| Coupling | Services coupled to orchestrator | Services coupled to event schema |
| Visibility | Single place to see the flow | Flow is distributed across services |
| Error handling | Orchestrator manages compensation | Each service manages its own rollback |
| Best for | Complex, multi-step business processes | Simple, loosely coupled workflows |
| Debugging | Easier — single flow view | Harder — distributed trace needed |

### Orchestration Example

```typescript
// Saga orchestrator — manages the multi-step order process
class OrderSaga {
  async execute(orderId: string): Promise<SagaResult> {
    const steps: SagaStep[] = [
      {
        name: 'reserveInventory',
        execute: () => this.inventoryService.reserve(orderId),
        compensate: () => this.inventoryService.release(orderId),
      },
      {
        name: 'processPayment',
        execute: () => this.paymentService.charge(orderId),
        compensate: () => this.paymentService.refund(orderId),
      },
      {
        name: 'shipOrder',
        execute: () => this.shippingService.schedule(orderId),
        compensate: () => this.shippingService.cancel(orderId),
      },
    ];

    const completedSteps: SagaStep[] = [];

    for (const step of steps) {
      try {
        await step.execute();
        completedSteps.push(step);
      } catch (error) {
        // Compensate in reverse order
        for (const completed of completedSteps.reverse()) {
          await completed.compensate();
        }
        return { status: 'failed', failedStep: step.name, error };
      }
    }

    return { status: 'completed' };
  }
}
```

### Choreography Example

```typescript
// Each service subscribes to events and publishes next steps

// Inventory service
class InventoryEventHandler {
  async handleOrderCreated(event: OrderCreatedEvent): Promise<void> {
    try {
      await this.inventoryRepo.reserve(event.orderId, event.items);
      await this.eventBus.publish(new InventoryReservedEvent(event.orderId));
    } catch (error) {
      await this.eventBus.publish(new InventoryReservationFailedEvent(
        event.orderId, error.message
      ));
    }
  }

  // Compensation
  async handlePaymentFailed(event: PaymentFailedEvent): Promise<void> {
    await this.inventoryRepo.release(event.orderId);
  }
}

// Payment service
class PaymentEventHandler {
  async handleInventoryReserved(event: InventoryReservedEvent): Promise<void> {
    try {
      await this.paymentProcessor.charge(event.orderId);
      await this.eventBus.publish(new PaymentProcessedEvent(event.orderId));
    } catch (error) {
      await this.eventBus.publish(new PaymentFailedEvent(
        event.orderId, error.message
      ));
    }
  }
}
```

### Saga State Machine

```text
OrderSaga States:
  [Pending] → ReserveInventory
       ├─ Success → [InventoryReserved] → ProcessPayment
       │       ├─ Success → [PaymentProcessed] → ScheduleShipping
       │       │       ├─ Success → [Completed]
       │       │       └─ Failure → RefundPayment → ReleaseInventory → [Failed]
       │       └─ Failure → ReleaseInventory → [Failed]
       └─ Failure → [Failed]
```

---

## Consistency Models

### Comparison

| Model | Guarantee | Latency | Use When |
|-------|-----------|---------|----------|
| Strong (linearizable) | Latest write always visible | Higher | Financial transactions, inventory counts |
| Sequential | Operations appear in agreed order | Medium | Distributed locks, leader election |
| Causal | Cause-and-effect order preserved | Medium | Chat messages, comment threads |
| Read-your-writes | Writer sees own writes immediately | Low | User profile updates, settings |
| Eventual | All replicas converge given time | Lowest | Social feeds, analytics, caches |
| Monotonic reads | Reader never sees older data after newer | Low | Dashboard displays, reporting |

### Read-Your-Writes Implementation

```typescript
// Pattern: Write to primary, read from primary for the writing user

class UserProfileService {
  async updateProfile(userId: string, data: ProfileData): Promise<void> {
    await this.primaryDb.users.update(userId, data);

    // Set a "read-from-primary" marker with short TTL
    await this.cache.set(`read-primary:${userId}`, '1', 'EX', 5);
  }

  async getProfile(userId: string, requestingUserId: string): Promise<Profile> {
    // If the requesting user just wrote, read from primary
    const readFromPrimary = await this.cache.get(`read-primary:${requestingUserId}`);

    if (readFromPrimary || userId === requestingUserId) {
      return this.primaryDb.users.findById(userId);
    }

    // Otherwise, read from replica (faster, eventually consistent)
    return this.replicaDb.users.findById(userId);
  }
}
```

### Conflict Resolution Strategies

| Strategy | Description | Use When |
|----------|-------------|----------|
| Last-write-wins (LWW) | Timestamp determines winner | Low-conflict data, user preferences |
| Merge (CRDTs) | Automatic conflict-free merge | Collaborative editing, counters |
| Application-level | Custom business logic resolves | Shopping carts, inventory |
| Manual | Flag conflict for human review | Legal documents, financial records |

---

## Anti-Patterns

### 1. Shared Database Across Services

```text
[FAIL] Service A and Service B both read/write to the same tables
       → Tight coupling, schema changes break both services, no independent deployment

[PASS] Each service owns its tables/schema; share data via APIs or events
```

### 2. Event Sourcing Everything

```text
[FAIL] Using event sourcing for simple CRUD entities (user profiles, settings)
       → Unnecessary complexity, painful schema evolution

[PASS] Use event sourcing for domains with complex state transitions, audit needs,
       or temporal queries. Use plain CRUD elsewhere.
```

### 3. Distributed Transactions (2PC)

```text
[FAIL] Two-phase commit across microservices
       → Blocks on slowest participant, single point of failure, poor availability

[PASS] Use sagas with compensating transactions for cross-service consistency
```

### 4. CQRS Without Justification

```text
[FAIL] Applying CQRS to a simple CRUD app with uniform read/write patterns
       → Doubles the code surface, adds sync complexity for no benefit

[PASS] Start with a single model. Split only when read/write patterns diverge
       or independent scaling is needed.
```

### 5. Ignoring Event Ordering

```text
[FAIL] Consuming events without partition keys → out-of-order processing
       → Inventory goes negative, payments double-charged

[PASS] Use aggregate ID as partition key. Process events per-partition in order.
       Handle idempotency for at-least-once delivery.
```

### 6. Fat Events

```text
[FAIL] Events carrying the entire entity state (100+ fields)
       → Tight coupling, bandwidth waste, hard to evolve

[PASS] Events carry only what changed plus correlation IDs.
       Consumers query for additional data if needed.
```

---

## Decision Framework

### Should You Use CQRS?

```text
1. Are read and write models structurally different?       [Yes → +2, No → 0]
2. Is read:write ratio > 10:1?                             [Yes → +2, No → 0]
3. Do you need independent scaling of reads vs writes?     [Yes → +2, No → 0]
4. Is the team experienced with event-driven systems?      [Yes → +1, No → -1]
5. Is this a greenfield project?                           [Yes → +1, No → -1]

Score: 0–3 → Stick with single model
Score: 4–6 → Consider CQRS (same-DB variant first)
Score: 7+  → Strong candidate for full CQRS
```

### Should You Use Event Sourcing?

```text
1. Is audit trail a legal/business requirement?            [Yes → +3, No → 0]
2. Do you need temporal queries ("state at time T")?       [Yes → +2, No → 0]
3. Is the domain event-driven by nature?                   [Yes → +2, No → 0]
4. Can the team handle eventual consistency?               [Yes → +1, No → -2]
5. Are events the natural language of the domain?          [Yes → +1, No → 0]

Score: 0–2 → Use traditional CRUD + audit log
Score: 3–5 → Consider event sourcing for key aggregates
Score: 6+  → Strong candidate for event sourcing
```

### Orchestration vs Choreography

```text
Process involves:
  ├─ 2–3 services, simple flow → Choreography
  ├─ 4+ services, complex branching → Orchestration
  ├─ Need single view of process state → Orchestration
  ├─ Services owned by different teams → Choreography (less central control)
  └─ Strict SLA on completion time → Orchestration (easier to monitor)
```

---

## Cross-References

- [modern-patterns.md](modern-patterns.md) — Architecture pattern overview including CQRS and event-driven
- [scalability-reliability-guide.md](scalability-reliability-guide.md) — CAP theorem, database scaling, caching strategies
- [../software-backend/references/database-patterns.md](../software-backend/references/database-patterns.md) — PostgreSQL-specific patterns, connection pooling, migrations
- [../software-backend/references/message-queues-background-jobs.md](../software-backend/references/message-queues-background-jobs.md) — BullMQ, Kafka, message broker comparison
- [../../assets/patterns/event-driven-template.md](../../assets/patterns/event-driven-template.md) — Event-driven architecture template with saga patterns
