# Scalability & Reliability Architecture Guide

## Core Principles

### CAP Theorem

You can only achieve 2 out of 3:
- **C**onsistency - All nodes see the same data
- **A**vailability - Every request receives a response
- **P**artition tolerance - System continues despite network failures

**Practical choices**:
- **CP**: Traditional databases (PostgreSQL, MongoDB with strong consistency)
- **AP**: NoSQL databases (Cassandra, DynamoDB), eventual consistency
- **Reality**: Partition tolerance is mandatory (networks fail), so choose CA or AP

### Scalability Dimensions

**Vertical scaling** (scale up):
- Add more CPU, RAM, storage to single machine
- Limits: Hardware maximums (~1TB RAM, ~128 CPU cores)
- Use case: Databases, monolithic apps

**Horizontal scaling** (scale out):
- Add more machines
- Limits: Architecture complexity
- Use case: Stateless services, distributed systems

## Scalability Patterns

### 1. Database Scaling

**Read replicas**:
```
┌───────────┐
│  Primary  │───┐ (writes)
│  (Write)  │   │
└───────────┘   │
                ├──▶ Replica 1 (reads)
                ├──▶ Replica 2 (reads)
                └──▶ Replica 3 (reads)
```

**Sharding** (horizontal partitioning):
```
User IDs 1-1000000    → Shard 1
User IDs 1000001-2000000 → Shard 2
User IDs 2000001-3000000 → Shard 3

Sharding strategies:
- Hash-based: hash(userId) % num_shards
- Range-based: users 1-1M on shard 1, etc.
- Geo-based: US users on shard 1, EU users on shard 2
```

**Example - PostgreSQL**:
```sql
-- Partition by range
CREATE TABLE orders (
    id BIGSERIAL,
    created_at TIMESTAMP,
    customer_id BIGINT,
    total DECIMAL
) PARTITION BY RANGE (created_at);

CREATE TABLE orders_q1 PARTITION OF orders
    FOR VALUES FROM ('2023-01-01') TO ('2023-04-01');

CREATE TABLE orders_q2 PARTITION OF orders
    FOR VALUES FROM ('2023-04-01') TO ('2023-07-01');
```

**CQRS for read scaling**:
```typescript
// Write model (normalized)
class OrderWriteModel {
  async createOrder(data: OrderData) {
    await db.orders.insert(data);
    await eventBus.publish(new OrderCreated(data));
  }
}

// Read model (denormalized for performance)
class OrderReadModel {
  async getCustomerOrders(customerId: string) {
    // Optimized read-only view
    return await readDb.customerOrderSummary.find({ customerId });
  }
}
```

### 2. Caching Strategies

**Cache hierarchy**:
```
Request
  │
  ├─▶ L1: In-memory cache (milliseconds)
  │   └─ Hit? Return
  │
  ├─▶ L2: Distributed cache (Redis/Memcached) (5-10ms)
  │   └─ Hit? Return and populate L1
  │
  └─▶ L3: Database (50-100ms+)
      └─ Populate L2 and L1
```

**Cache patterns**:

**Cache-Aside** (lazy loading):
```typescript
async function getUser(id: string): Promise<User> {
  // 1. Try cache
  const cached = await cache.get(`user:${id}`);
  if (cached) return JSON.parse(cached);

  // 2. Cache miss - fetch from DB
  const user = await db.users.findById(id);

  // 3. Populate cache
  await cache.set(`user:${id}`, JSON.stringify(user), { ttl: 3600 });

  return user;
}
```

**Write-Through**:
```typescript
async function updateUser(id: string, data: Partial<User>) {
  // 1. Write to database
  const user = await db.users.update(id, data);

  // 2. Write to cache
  await cache.set(`user:${id}`, JSON.stringify(user), { ttl: 3600 });

  return user;
}
```

**Write-Behind** (async):
```typescript
async function updateUser(id: string, data: Partial<User>) {
  // 1. Write to cache immediately (fast response)
  const user = { ...existingUser, ...data };
  await cache.set(`user:${id}`, JSON.stringify(user), { ttl: 3600 });

  // 2. Queue database write (async)
  await queue.publish('user.update', { id, data });

  return user;
}
```

**Cache invalidation strategies**:
```typescript
// 1. TTL (Time To Live)
cache.set('key', value, { ttl: 3600 }); // 1 hour

// 2. Event-based invalidation
eventBus.on('user.updated', async (userId) => {
  await cache.delete(`user:${userId}`);
});

// 3. Cache tags
cache.set('user:123', user, { tags: ['users', 'active-users'] });
cache.invalidateTag('active-users'); // Clear all with this tag
```

### 3. Load Balancing

**Algorithms**:

**Round Robin** (simplest):
```
Request 1 → Server A
Request 2 → Server B
Request 3 → Server C
Request 4 → Server A (cycle repeats)
```

**Least Connections**:
```
Server A: 5 connections
Server B: 3 connections  ← Route here
Server C: 8 connections
```

**Consistent Hashing** (for stateful sessions):
```typescript
function getServer(userId: string, servers: Server[]): Server {
  const hash = hashFunction(userId);
  const index = hash % servers.length;
  return servers[index];
}
// Same user always goes to same server
```

**Nginx configuration**:
```nginx
upstream backend {
  least_conn;  # Algorithm
  server backend1.example.com weight=3;
  server backend2.example.com weight=2;
  server backend3.example.com weight=1;
  server backend4.example.com backup;  # Only used if others fail
}

server {
  location / {
    proxy_pass http://backend;
    proxy_next_upstream error timeout invalid_header http_500;
    proxy_connect_timeout 2s;
  }
}
```

### 4. Asynchronous Processing

**Message Queue Pattern**:
```
┌────────┐       ┌───────┐       ┌────────┐
│  API   │──────▶│ Queue │──────▶│ Worker │
│        │       │ (SQS) │       │  Pool  │
└────────┘       └───────┘       └────────┘
   │                                  │
   └─ Immediate response              └─ Process async

Benefits:
- Decoupled components
- Handle traffic spikes (queue buffers)
- Retry failed jobs
- Scale workers independently
```

**Implementation**:
```typescript
// Producer (API)
app.post('/process-video', async (req, res) => {
  const videoId = req.body.videoId;

  // Queue the work (don't process synchronously)
  await queue.send('video-processing', {
    videoId,
    priority: req.body.priority || 'normal'
  });

  // Immediate response
  res.json({ status: 'queued', videoId });
});

// Consumer (Worker)
queue.on('video-processing', async (job) => {
  try {
    await processVideo(job.data.videoId);
    await job.complete();
  } catch (error) {
    // Retry with exponential backoff
    await job.retry({ delay: Math.pow(2, job.attemptsMade) * 1000 });
  }
});
```

### 5. Circuit Breaker Pattern

Prevent cascade failures when dependencies fail:

```typescript
class CircuitBreaker {
  private failureCount = 0;
  private lastFailureTime = 0;
  private state: 'closed' | 'open' | 'half-open' = 'closed';

  constructor(
    private threshold = 5,        // Failures before opening
    private timeout = 60000,      // Time to stay open (ms)
    private resetTimeout = 30000  // Time to try half-open
  ) {}

  async execute<T>(fn: () => Promise<T>): Promise<T> {
    if (this.state === 'open') {
      if (Date.now() - this.lastFailureTime > this.resetTimeout) {
        this.state = 'half-open';
      } else {
        throw new Error('Circuit breaker is OPEN');
      }
    }

    try {
      const result = await fn();
      this.onSuccess();
      return result;
    } catch (error) {
      this.onFailure();
      throw error;
    }
  }

  private onSuccess() {
    this.failureCount = 0;
    this.state = 'closed';
  }

  private onFailure() {
    this.failureCount++;
    this.lastFailureTime = Date.now();

    if (this.failureCount >= this.threshold) {
      this.state = 'open';
    }
  }
}

// Usage
const breaker = new CircuitBreaker();

app.get('/external-api', async (req, res) => {
  try {
    const data = await breaker.execute(() =>
      fetch('https://external-api.com/data')
    );
    res.json(data);
  } catch (error) {
    res.status(503).json({ error: 'Service temporarily unavailable' });
  }
});
```

## Reliability Patterns

### 1. Health Checks

**Kubernetes liveness & readiness**:
```yaml
apiVersion: v1
kind: Pod
spec:
  containers:
  - name: app
    image: myapp:1.0
    livenessProbe:
      httpGet:
        path: /health/live
        port: 8080
      initialDelaySeconds: 30
      periodSeconds: 10
      failureThreshold: 3

    readinessProbe:
      httpGet:
        path: /health/ready
        port: 8080
      initialDelaySeconds: 5
      periodSeconds: 5
      failureThreshold: 2
```

**Health check endpoint**:
```typescript
app.get('/health/live', (req, res) => {
  // Basic check: is the app running?
  res.json({ status: 'ok' });
});

app.get('/health/ready', async (req, res) => {
  // Comprehensive check: can the app serve traffic?
  const checks = await Promise.all([
    checkDatabase(),
    checkRedis(),
    checkMessageQueue()
  ]);

  const healthy = checks.every(c => c.healthy);

  res.status(healthy ? 200 : 503).json({
    status: healthy ? 'ready' : 'not ready',
    checks
  });
});

async function checkDatabase(): Promise<HealthCheck> {
  try {
    await db.raw('SELECT 1');
    return { name: 'database', healthy: true };
  } catch (error) {
    return { name: 'database', healthy: false, error: error.message };
  }
}
```

### 2. Retry with Exponential Backoff

```typescript
async function retryWithBackoff<T>(
  fn: () => Promise<T>,
  maxRetries = 3,
  baseDelay = 1000
): Promise<T> {
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      if (attempt === maxRetries) {
        throw error;
      }

      // Exponential backoff with jitter
      const delay = baseDelay * Math.pow(2, attempt);
      const jitter = Math.random() * 1000;
      await sleep(delay + jitter);

      logger.warn(`Retry attempt ${attempt + 1}/${maxRetries}`, { error });
    }
  }

  throw new Error('Max retries exceeded');
}

// Usage
const data = await retryWithBackoff(() =>
  fetch('https://api.example.com/data')
);
```

### 3. Rate Limiting

**Token bucket algorithm**:
```typescript
class RateLimiter {
  private tokens: Map<string, { count: number; lastRefill: number }>;

  constructor(
    private maxTokens = 100,
    private refillRate = 10, // tokens per second
  ) {
    this.tokens = new Map();
  }

  async isAllowed(key: string): Promise<boolean> {
    const now = Date.now();
    const bucket = this.tokens.get(key) || { count: this.maxTokens, lastRefill: now };

    // Refill tokens based on time elapsed
    const elapsed = (now - bucket.lastRefill) / 1000;
    bucket.count = Math.min(
      this.maxTokens,
      bucket.count + elapsed * this.refillRate
    );
    bucket.lastRefill = now;

    if (bucket.count >= 1) {
      bucket.count -= 1;
      this.tokens.set(key, bucket);
      return true;
    }

    this.tokens.set(key, bucket);
    return false;
  }
}

// Middleware
const limiter = new RateLimiter();

app.use(async (req, res, next) => {
  const key = req.ip;
  const allowed = await limiter.isAllowed(key);

  if (!allowed) {
    return res.status(429).json({ error: 'Too many requests' });
  }

  next();
});
```

**Redis-based distributed rate limiting**:
```typescript
async function isRateLimited(userId: string): Promise<boolean> {
  const key = `rate-limit:${userId}`;
  const limit = 100; // requests
  const window = 60;  // seconds

  const current = await redis.incr(key);

  if (current === 1) {
    await redis.expire(key, window);
  }

  return current > limit;
}
```

### 4. Graceful Degradation

**Feature flags**:
```typescript
const features = {
  recommendations: { enabled: true, fallback: 'popular' },
  search: { enabled: true, fallback: 'cached' },
  analytics: { enabled: true, fallback: 'disabled' }
};

async function getRecommendations(userId: string) {
  if (!features.recommendations.enabled) {
    return getPopularItems(); // Fallback
  }

  try {
    return await mlService.getPersonalizedRecommendations(userId);
  } catch (error) {
    logger.error('Recommendations service failed', { error });
    return getPopularItems(); // Graceful degradation
  }
}
```

### 5. Bulkhead Pattern

Isolate resources to prevent total system failure:

```typescript
// Separate connection pools for different operations
const pools = {
  critical: new Pool({ max: 50 }), // Always available
  analytics: new Pool({ max: 20 }), // Can fail without affecting critical
  background: new Pool({ max: 10 })  // Lowest priority
};

// Critical operation (user authentication)
async function authenticateUser(credentials: Credentials) {
  return pools.critical.query('SELECT * FROM users WHERE email = $1', [credentials.email]);
}

// Analytics (can fail without breaking core functionality)
async function trackEvent(event: Event) {
  try {
    return pools.analytics.query('INSERT INTO analytics ...', event);
  } catch (error) {
    logger.error('Analytics failed', { error }); // Log but don't throw
  }
}
```

## Monitoring & Observability

### Key Metrics (SRE)

**Golden Signals**:
1. **Latency** - Time to serve a request
2. **Traffic** - Requests per second
3. **Errors** - Rate of failed requests
4. **Saturation** - Resource utilization

**SLI/SLO/SLA**:
```yaml
# Service Level Indicator (SLI)
availability: "percentage of successful requests"
latency_p99: "99th percentile response time"

# Service Level Objective (SLO)
availability_target: 99.9%  # "Three nines"
latency_p99_target: 200ms

# Service Level Agreement (SLA) - Customer commitment
availability_commitment: 99.5%
penalty: "10% credit if violated"
```

**Error budget**:
```
Monthly error budget = (1 - SLO) × total requests
If SLO = 99.9%, error budget = 0.1% = 43.2 minutes/month downtime

Use budget for:
- Deployments
- Experiments
- Maintenance

If budget exhausted:
- Freeze feature releases
- Focus on reliability
```

### Distributed Tracing

**OpenTelemetry example**:
```typescript
import { trace } from '@opentelemetry/api';

const tracer = trace.getTracer('my-service');

async function handleRequest(req, res) {
  const span = tracer.startSpan('handle-request', {
    attributes: {
      'http.method': req.method,
      'http.url': req.url,
      'user.id': req.user?.id
    }
  });

  try {
    const user = await getUserWithTracing(req.user.id);
    const orders = await getOrdersWithTracing(user.id);

    span.setStatus({ code: SpanStatusCode.OK });
    res.json({ user, orders });
  } catch (error) {
    span.recordException(error);
    span.setStatus({ code: SpanStatusCode.ERROR, message: error.message });
    throw error;
  } finally {
    span.end();
  }
}

async function getUserWithTracing(userId: string) {
  return tracer.startActiveSpan('get-user', async (span) => {
    span.setAttribute('user.id', userId);
    const user = await db.users.findById(userId);
    span.end();
    return user;
  });
}
```

## Performance Benchmarks

**Target latencies (95th percentile)**:
- Database query: <10ms
- Cache hit: <1ms
- Internal API call: <50ms
- External API call: <200ms
- Page load: <2s
- API response: <100ms

**Capacity planning**:
```
Required capacity = (Peak RPS × Average latency) / Target CPU utilization

Example:
Peak RPS = 10,000
Average latency = 50ms = 0.05s
Target CPU = 70%

Capacity = (10,000 × 0.05) / 0.70 = 714 concurrent requests
           ≈ 15-20 servers (assuming ~40 concurrent requests per server)
```

## Resources

- Google SRE Book
- AWS Well-Architected Framework
- Microsoft Azure Architecture Center
- Designing Data-Intensive Applications (Martin Kleppmann)
- Release It! (Michael Nygard)
