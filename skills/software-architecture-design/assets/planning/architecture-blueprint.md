# Service Architecture Blueprint

Use this when drafting a new service or major redesign.

- **Service name / domain:** Bounded context, upstream/downstream dependencies  
- **Non-negotiable requirements:** Latency/throughput targets, availability %, data retention, compliance  
- **Architecture diagram link:** C4 level 2/3 diagrams, sequence for critical paths  
- **Data flows:** Read/write paths, schemas, partitioning/replication strategy  
- **Integration contracts:** APIs/events with SLAs, versioning, idempotency rules, consumers/providers  
- **Resilience:** Timeouts, retries, circuit breakers, bulkheads, backpressure, graceful degradation  
- **Security:** AuthN/AuthZ model, secrets handling, ingress/egress policies, audit requirements  
- **Deployability:** CI/CD steps, canary/blue-green, rollback, migration plan  
- **Observability:** Golden signals, dashboards, alert rules, trace spans, log fields  
- **Risks & assumptions:** Unknowns, kill criteria, contingency plans  
