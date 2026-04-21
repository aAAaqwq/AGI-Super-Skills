# Event-Driven Architecture Template

Use this template when designing event-driven systems with asynchronous communication.

## Event Schema Definition

### Event: [EventName]

```json
{
  "eventId": "uuid",
  "eventType": "[EventName]",
  "eventVersion": "1.0",
  "timestamp": "ISO8601",
  "source": "[ServiceName]",
  "correlationId": "uuid",
  "payload": {
    // Event-specific data
  },
  "metadata": {
    "userId": "string",
    "traceId": "string"
  }
}
```

**Trigger:** [When is this event published?]
**Consumers:** [Which services consume this event?]
**Retention:** [How long to keep in event store?]

## Event Catalog

| Event Name | Version | Producer | Consumers | Schema Registry |
|------------|---------|----------|-----------|-----------------|
| OrderPlaced | 1.0 | OrderService | PaymentService, InventoryService | schema-registry/order-placed-v1.json |
| PaymentProcessed | 1.0 | PaymentService | OrderService, NotificationService | schema-registry/payment-processed-v1.json |

## Event Broker Configuration

- **Platform:** [Kafka / RabbitMQ / AWS EventBridge / Google Pub/Sub]
- **Topics/Queues:**
  - `orders.placed` - Order creation events
  - `payments.processed` - Payment completion events
  - `inventory.updated` - Stock level changes
- **Partitioning strategy:** [By customer ID / By order ID / Round-robin]
- **Replication factor:** [3 for production]
- **Retention period:** [7 days for event replay]

## Producer Configuration

### Service: [ProducerServiceName]

**Events Published:**

- **[EventName]**: Published when [business event occurs]
  - Partition key: [customer_id / entity_id]
  - Ordering guarantee: [Yes/No]
  - Retry policy: [3 retries with exponential backoff]

**Reliability Patterns:**

- **Outbox pattern:** Write to database + outbox table atomically
- **At-least-once delivery:** Idempotent event production
- **Schema validation:** Validate against schema registry before publishing
- **Failure handling:** Store failed events in dead letter queue

**Code Example:**

```python
async def publish_event(event: OrderPlaced):
    # Transactional outbox pattern
    async with db.transaction():
        await db.orders.create(event.order)
        await db.outbox.insert({
            "event_id": event.id,
            "event_type": "OrderPlaced",
            "payload": event.to_json(),
            "status": "pending"
        })

    # Asynchronous event publishing (handled by outbox processor)
    await event_broker.publish(
        topic="orders.placed",
        key=event.customer_id,
        value=event.to_json(),
        headers={"trace_id": trace_id}
    )
```

## Consumer Configuration

### Service: [ConsumerServiceName]

**Events Consumed:**

- **[EventName]**: From [ProducerService]
  - Consumer group: `[service-name]-[event-name]`
  - Concurrency: [N parallel workers]
  - Max retries: [5 with exponential backoff]
  - Dead letter queue: `[event-name].dlq`

**Processing Patterns:**

- **Idempotency:** Check event ID before processing
- **Ordering:** Process events in order within partition
- **Error handling:** Retry transient errors, DLQ for permanent failures
- **Acknowledgment:** Acknowledge only after successful processing

**Code Example:**

```python
@consumer(topic="orders.placed", group="payment-service-orders")
async def process_order_placed(event: OrderPlaced):
    # Idempotency check
    if await db.processed_events.exists(event.id):
        logger.info(f"Event {event.id} already processed")
        return

    try:
        # Business logic
        payment = await payment_service.process_payment(event.order)

        # Mark as processed
        await db.processed_events.insert(event.id)

        # Publish downstream event
        await publish_event(PaymentProcessed(payment))

    except RetryableError as e:
        logger.warning(f"Retrying event {event.id}: {e}")
        raise  # Will be retried
    except PermanentError as e:
        logger.error(f"Sending event {event.id} to DLQ: {e}")
        await dlq.send(event, error=str(e))
```

## Event Sourcing

**Use when:** Need complete audit trail and event replay capabilities.

### Aggregate: [AggregateName]

**Command Handlers:**

- **CreateOrder**: Validates and produces OrderCreated event
- **UpdateOrderStatus**: Produces OrderStatusUpdated event

**Event Store:**

- **Storage:** [PostgreSQL event_store table / EventStoreDB / Kafka topic]
- **Schema:**
  ```sql
  CREATE TABLE events (
      event_id UUID PRIMARY KEY,
      aggregate_id UUID NOT NULL,
      aggregate_type VARCHAR(100),
      event_type VARCHAR(100),
      event_data JSONB,
      event_version INT,
      created_at TIMESTAMP,
      INDEX(aggregate_id, event_version)
  );
  ```

**Snapshot Strategy:**

- Create snapshot every [100] events
- Store in separate `snapshots` table
- Load latest snapshot + subsequent events for aggregate rebuild

## Saga Pattern (Distributed Transactions)

### Saga: [SagaName]

**Orchestration Approach:** [Choreography / Orchestrator]

**Steps:**

1. **OrderService** → Publish `OrderPlaced`
2. **PaymentService** → Process payment → Publish `PaymentProcessed` or `PaymentFailed`
3. **InventoryService** → Reserve stock → Publish `InventoryReserved` or `InventoryUnavailable`
4. **ShippingService** → Schedule shipment → Publish `ShipmentScheduled`

**Compensation (Rollback):**

- If `PaymentFailed` → Publish `OrderCancelled`
- If `InventoryUnavailable` → Publish `PaymentRefunded` → `OrderCancelled`

**State Machine:**

```
[Order Created] → [Payment Processing] → [Inventory Reserved] → [Shipment Scheduled] → [Order Completed]
      ↓                    ↓                       ↓
[Order Cancelled] ← [Payment Failed] ← [Inventory Unavailable]
```

## Schema Evolution

**Versioning Strategy:** [Backward compatible / Forward compatible / Full compatibility]

**Schema Registry:** [Confluent Schema Registry / AWS Glue Schema Registry]

**Version Migration:**

- **v1 → v2 Changes:**
  - Added optional field: `customer_email`
  - Deprecated field: `customer_address` (use `shipping_address` instead)
- **Consumer compatibility:** Old consumers can read v2 events (ignore new fields)
- **Producer compatibility:** New producers can emit v1 events if needed

## Monitoring & Observability

**Metrics:**

- Event publish rate and latency
- Consumer lag (events behind current offset)
- Processing errors and retry count
- Dead letter queue size

**Alerts:**

- Consumer lag > [1000 events]
- Error rate > [5%]
- DLQ messages > [100]
- Event processing latency p99 > [500ms]

**Distributed Tracing:**

- Propagate trace IDs across events
- Track event flow: Producer → Broker → Consumer → Downstream events

## Testing

**Unit Tests:**

- Event schema validation
- Idempotency logic
- Compensation logic (saga rollback)

**Integration Tests:**

- End-to-end event flow
- Consumer error handling and retries
- Dead letter queue behavior

**Chaos Testing:**

- Simulate broker downtime
- Duplicate event delivery
- Out-of-order event delivery
- Consumer crash mid-processing

## Security

- **Encryption:** TLS for data in transit, encryption at rest for event store
- **Authorization:** ACLs for topic access (producers/consumers)
- **Audit:** Log all event publications and consumptions
- **PII handling:** Encrypt sensitive fields in event payload

## Cost Optimization

- **Retention policy:** Delete events older than [X days]
- **Compaction:** Use log compaction for entity snapshots
- **Resource allocation:** Right-size broker and consumer resources
- **Batch processing:** Batch consume events to reduce overhead

## Disaster Recovery

- **Event replay:** Re-process events from timestamp/offset
- **Backup:** Regular snapshots of event store
- **Cross-region replication:** Mirror events to DR region
- **RTO/RPO:** Recovery time objective [X hours], Recovery point objective [X minutes]
