# Microservices Architecture Template

Use this template when designing a microservices-based system.

## Service Definition

- **Service name:** [ServiceName]
- **Bounded context:** [Domain boundary this service owns]
- **Team owner:** [Team responsible for this service]

## Service Responsibilities

- **Core capabilities:**
  - [Primary business capability 1]
  - [Primary business capability 2]
- **Data ownership:**
  - [Entities this service owns]
  - [Events this service publishes]

## API Contract

### REST Endpoints

```http
GET    /api/v1/[resource]
POST   /api/v1/[resource]
PUT    /api/v1/[resource]/{id}
DELETE /api/v1/[resource]/{id}
```

### Events Published

- **[EventName]**: Published when [trigger condition]
- **[EventName]**: Published when [trigger condition]

### Events Consumed

- **[EventName]**: From [SourceService], triggers [action]

## Dependencies

### Upstream Services (Calls)

- **[ServiceName]**: For [purpose], timeout: [Xms], circuit breaker threshold: [N failures]

### Downstream Services (Called by)

- **[ServiceName]**: Expects [SLA], provides [data/functionality]

## Data Storage

- **Database type:** [PostgreSQL / MongoDB / Cassandra / etc.]
- **Schema approach:** [Database-per-service / Shared tables / etc.]
- **Replication:** [Primary-replica / Multi-master]
- **Backup strategy:** [Automated daily / Point-in-time recovery]

## Resilience

- **Timeouts:**
  - Database queries: [Xms]
  - External API calls: [Xms]
  - Internal service calls: [Xms]
- **Retry policy:** Exponential backoff, max [N] retries
- **Circuit breaker:** Open after [N] failures, half-open after [X] seconds
- **Rate limiting:** [N] requests per second per client
- **Fallback behavior:** [Return cached data / Default response / Graceful degradation]

## Observability

- **Metrics:**
  - Request rate, latency (p50, p95, p99)
  - Error rate (4xx, 5xx)
  - Dependency health
  - Business metrics: [specific to service]
- **Distributed tracing:** Jaeger/OpenTelemetry with trace IDs
- **Logging:**
  - Structured JSON logs
  - Log level: INFO in production, DEBUG in dev
  - Key fields: trace_id, user_id, service_name, timestamp
- **Health checks:**
  - Liveness: `/health/live` (basic ping)
  - Readiness: `/health/ready` (dependencies check)

## Deployment

- **Container:** Docker image, registry: [ECR / Docker Hub / etc.]
- **Orchestration:** Kubernetes
- **Scaling policy:**
  - Min replicas: [N]
  - Max replicas: [N]
  - Scale trigger: CPU > [X]% or Memory > [X]% or RPS > [N]
- **Deployment strategy:** Rolling update / Canary / Blue-green
- **Rollback plan:** Automated rollback if error rate > [X]%

## Security

- **Authentication:** JWT tokens, validated via [Auth service / API Gateway]
- **Authorization:** Role-based access control (RBAC)
- **Service-to-service auth:** mTLS via service mesh
- **Secrets:** Stored in [AWS Secrets Manager / Vault / Kubernetes Secrets]
- **Input validation:** All user inputs validated and sanitized
- **Rate limiting:** Per-user and per-IP limits

## Testing

- **Unit tests:** Coverage target: 80%+
- **Integration tests:** Test API contracts and database interactions
- **Contract tests:** Pact/Spring Cloud Contract for upstream/downstream
- **Load tests:** Target [N] RPS at p95 < [Xms]
- **Chaos testing:** Simulate dependency failures, network latency

## Communication Patterns

- **Synchronous:** REST/gRPC for request-response
- **Asynchronous:** Kafka/RabbitMQ for events
- **Idempotency:** All write operations support idempotency keys
- **Message format:** JSON for REST, Protobuf for gRPC, Avro for Kafka

## Cost Optimization

- **Resource allocation:**
  - CPU request: [Xm], limit: [Xm]
  - Memory request: [XMi], limit: [XMi]
- **Auto-scaling:** Scale down during off-peak hours
- **Data retention:** [X days] for logs, [X days] for metrics

## Migration Plan

- **Phase 1:** [Extract service from monolith / Build new service]
- **Phase 2:** [Gradual traffic migration / Feature flag rollout]
- **Phase 3:** [Full cutover / Decommission old system]
- **Rollback criteria:** [Error rate / Latency / Business metrics]

## ADR References

- [ADR-001]: [Decision about technology choice]
- [ADR-002]: [Decision about data model]
