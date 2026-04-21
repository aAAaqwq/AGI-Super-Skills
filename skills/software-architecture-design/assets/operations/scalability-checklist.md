# System Scalability Checklist

Use this checklist when designing for horizontal scalability and high availability.

## Load Estimation

- [ ] **Current load:** [N] requests/second, [N] concurrent users
- [ ] **Peak load:** [N] requests/second (expected during [event/time])
- [ ] **Growth projection:** [X]% yearly growth
- [ ] **Target capacity:** Support [N]x current load

## Scalability Dimensions

### Horizontal Scaling (Preferred)

- [ ] **Stateless services:** All application servers are stateless
- [ ] **Session storage:** Use Redis/Memcached for distributed sessions
- [ ] **File storage:** Use object storage (S3/GCS) instead of local filesystem
- [ ] **Auto-scaling:** Configure based on CPU/memory/RPS metrics
- [ ] **Load balancer:** Layer 7 (application-aware) load balancing

### Vertical Scaling (Limited)

- [ ] **Database instance:** Right-sized for current + 6 months growth
- [ ] **Cache instance:** Sized for working set + 20% headroom
- [ ] **Max capacity:** Identified vertical scaling limit

## Database Scalability

### Read Scaling

- [ ] **Read replicas:** [N] replicas for read-heavy workloads
- [ ] **Read/write splitting:** Route reads to replicas, writes to primary
- [ ] **Connection pooling:** PgBouncer/ProxySQL to limit connections
- [ ] **Query optimization:** Queries < [10ms] with proper indexing

### Write Scaling

- [ ] **Sharding strategy:** [Hash-based / Range-based / Geographic]
  - Shard key: [user_id / tenant_id / region]
  - Number of shards: [N] (plan for [10x] growth)
- [ ] **Write-ahead logging:** Asynchronous replication for replicas
- [ ] **Bulk operations:** Batch inserts/updates to reduce round trips

### Caching Strategy

- [ ] **Cache layers:**
  - L1: In-memory application cache ([Caffeine / Guava])
  - L2: Distributed cache ([Redis / Memcached])
  - L3: CDN for static assets ([CloudFront / Fastly])
- [ ] **Cache hit ratio:** Target > [90]%
- [ ] **TTL strategy:** Balance freshness vs load ([5min] for hot data, [1h] for warm)
- [ ] **Cache eviction:** LRU/LFU policy configured
- [ ] **Cache warming:** Pre-populate on deployment
- [ ] **Cache invalidation:** Event-driven invalidation for updates

## API Gateway

- [ ] **Rate limiting:**
  - Per-user: [N] req/min
  - Per-IP: [N] req/min
  - Burst allowance: [N] requests
- [ ] **Request throttling:** Queue requests during spikes
- [ ] **Response compression:** Gzip/Brotli enabled
- [ ] **API versioning:** Support [N] concurrent versions

## Asynchronous Processing

- [ ] **Message queue:** [Kafka / RabbitMQ / AWS SQS]
  - Throughput: [N] messages/second
  - Retention: [X] days
- [ ] **Worker pools:** [N] workers per queue
- [ ] **Backpressure:** Reject requests when queue length > [N]
- [ ] **Dead letter queue:** For failed message handling

## Content Delivery

- [ ] **CDN:** CloudFront/Fastly for static assets
- [ ] **Edge caching:** Cache-Control headers configured
- [ ] **Image optimization:** WebP format, lazy loading
- [ ] **Asset bundling:** Minified and bundled CSS/JS

## Data Storage Patterns

### Hot/Warm/Cold Data

- [ ] **Hot data:** Last [7] days in primary DB (fast access)
- [ ] **Warm data:** Last [30] days in read replicas
- [ ] **Cold data:** Older than [30] days archived to S3/Glacier
- [ ] **Archival strategy:** Automated data lifecycle policies

### Data Partitioning

- [ ] **Time-based partitioning:** Partition by month/year for time-series data
- [ ] **Hash partitioning:** Distribute by hash(user_id) for even distribution
- [ ] **List partitioning:** Partition by region/tenant for isolation

## Connection Management

- [ ] **Database connection pool:**
  - Min connections: [N]
  - Max connections: [N]
  - Connection timeout: [Xms]
- [ ] **HTTP keep-alive:** Reuse connections to upstream services
- [ ] **Circuit breaker:** Prevent cascade failures

## Observability for Scalability

### Key Metrics

- [ ] **Golden signals:**
  - Latency: p50, p95, p99 response times
  - Traffic: Requests per second
  - Errors: Error rate (4xx, 5xx)
  - Saturation: CPU, memory, disk, network usage
- [ ] **Capacity metrics:**
  - Database connections used/available
  - Queue depth and processing rate
  - Cache hit/miss ratio
  - Thread pool utilization

### Alerts

- [ ] CPU > [70]% for [5] minutes → Scale out
- [ ] Memory > [80]% for [5] minutes → Investigate memory leak
- [ ] Database connections > [80]% → Add replicas
- [ ] Queue depth > [1000] → Add workers
- [ ] Error rate > [1]% → Page on-call

## Load Testing

- [ ] **Baseline test:** Measure current performance under typical load
- [ ] **Stress test:** Identify breaking point (max capacity before failure)
- [ ] **Spike test:** Test behavior under sudden 10x traffic spike
- [ ] **Soak test:** Run at [2x] typical load for [24] hours
- [ ] **Tools:** [k6 / JMeter / Gatling / Locust]

### Load Test Scenarios

- [ ] Scenario 1: [N] users browsing product catalog
- [ ] Scenario 2: [N] users checking out simultaneously
- [ ] Scenario 3: [N] API clients polling for updates
- [ ] Target performance: p95 < [200ms], error rate < [0.1]%

## Cost Optimization

- [ ] **Right-sizing:** Use smallest instance that meets SLA
- [ ] **Reserved instances:** [70]% reserved, [30]% on-demand/spot
- [ ] **Auto-scaling policies:**
  - Scale up: When CPU > [70]% for [2] minutes
  - Scale down: When CPU < [30]% for [10] minutes
  - Min instances: [N], Max instances: [N]
- [ ] **Database optimization:** Remove unused indexes, optimize slow queries
- [ ] **CDN optimization:** Increase cache TTL where possible

## Geographic Distribution

- [ ] **Multi-region deployment:**
  - Primary region: [us-east-1]
  - Secondary region: [eu-west-1]
  - Failover: Automatic DNS failover
- [ ] **Data locality:** Store user data in nearest region (GDPR compliance)
- [ ] **Latency optimization:** < [100ms] within region, < [300ms] cross-region

## Disaster Recovery

- [ ] **RTO (Recovery Time Objective):** [X] hours
- [ ] **RPO (Recovery Point Objective):** [X] minutes
- [ ] **Backup frequency:** Database backup every [X] hours
- [ ] **Failover testing:** Quarterly DR drills
- [ ] **Data replication:** Asynchronous cross-region replication

## Security at Scale

- [ ] **DDoS protection:** CloudFlare/AWS Shield enabled
- [ ] **Rate limiting:** Per-IP and per-user limits
- [ ] **WAF rules:** Block common attack patterns
- [ ] **Certificate management:** Auto-renewal with Let's Encrypt/ACM

## Deployment Strategy

- [ ] **Blue-green deployment:** Zero-downtime releases
- [ ] **Canary releases:** [10]% traffic to new version initially
- [ ] **Feature flags:** Toggle features without deployment
- [ ] **Rollback plan:** Automated rollback if error rate > [X]%

## Checklist Before Production

- [ ] Load tested at [3x] expected peak traffic
- [ ] Auto-scaling policies validated
- [ ] Database read replicas configured
- [ ] Caching strategy implemented and tested
- [ ] Monitoring and alerts configured
- [ ] Disaster recovery plan documented and tested
- [ ] Cost monitoring and budgets set
- [ ] Security review completed
- [ ] Runbooks created for common incidents
- [ ] On-call rotation established
