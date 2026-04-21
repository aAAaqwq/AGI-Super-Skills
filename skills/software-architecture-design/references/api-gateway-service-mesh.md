# API Gateway & Service Mesh Patterns

Deep reference for API gateway architectures, service mesh implementation (Istio, Linkerd, Envoy), sidecar patterns, and service-to-service communication. Use when designing inter-service communication, implementing traffic management, or choosing between gateway, mesh, or hybrid topologies.

## Contents

- [API Gateway Patterns](#api-gateway-patterns)
- [Service Mesh Architecture](#service-mesh-architecture)
- [Technology Comparison](#technology-comparison)
- [mTLS and Service Identity](#mtls-and-service-identity)
- [Observability Through Mesh](#observability-through-mesh)
- [Gateway vs Mesh vs Both](#gateway-vs-mesh-vs-both)
- [Implementation Patterns](#implementation-patterns)
- [Anti-Patterns](#anti-patterns)
- [Decision Framework](#decision-framework)
- [Cross-References](#cross-references)

---

## API Gateway Patterns

### Core Gateway Responsibilities

| Function | Description | Example |
|----------|-------------|---------|
| Routing | Route requests to backend services | `/api/orders/*` -> orders-service |
| Authentication | Validate tokens, API keys | JWT verification, OAuth introspection |
| Rate limiting | Throttle requests per client/endpoint | 100 req/min per API key |
| Request transformation | Modify headers, body, path | Add correlation IDs, strip internal headers |
| Response aggregation | Combine multiple backend responses | BFF pattern for mobile clients |
| Load balancing | Distribute traffic across instances | Round-robin, least connections, weighted |
| Caching | Cache responses at the edge | Cache GET responses with TTL |
| Circuit breaking | Fail fast when backend is unhealthy | Open circuit after 5 consecutive failures |
| TLS termination | Handle HTTPS at the gateway | Offload TLS from backend services |

### Gateway Topology Patterns

**Pattern 1: Single Gateway**

```text
┌────────┐     ┌──────────────┐     ┌──────────┐
│ Client │────▶│   Gateway    │────▶│ Service A│
└────────┘     │              │────▶│ Service B│
               │              │────▶│ Service C│
               └──────────────┘     └──────────┘
```

Best for: Small teams, <10 services, uniform client needs.

**Pattern 2: Backend-for-Frontend (BFF)**

```text
┌──────────┐     ┌───────────────┐
│  Mobile  │────▶│  Mobile BFF   │───▶ Services
└──────────┘     └───────────────┘

┌──────────┐     ┌───────────────┐
│   Web    │────▶│   Web BFF     │───▶ Services
└──────────┘     └───────────────┘

┌──────────┐     ┌───────────────┐
│ Partner  │────▶│ Partner API   │───▶ Services
│   API    │     │   Gateway     │
└──────────┘     └───────────────┘
```

Best for: Different client types with distinct data needs.

**Pattern 3: Federated Gateway**

```text
┌────────┐     ┌───────────────┐     ┌──────────────┐
│ Client │────▶│ Edge Gateway  │────▶│ Team A GW    │───▶ Team A services
└────────┘     │ (auth, rate   │────▶│ Team B GW    │───▶ Team B services
               │  limiting)    │────▶│ Team C GW    │───▶ Team C services
               └───────────────┘     └──────────────┘
```

Best for: Large organizations, multiple teams owning their own gateway configuration.

### Rate Limiting Patterns

```typescript
// Token bucket rate limiting (typical gateway configuration)
// Kong rate-limiting plugin configuration
const rateLimitConfig = {
  plugin: 'rate-limiting',
  config: {
    minute: 60,              // 60 requests per minute
    hour: 1000,              // 1000 requests per hour
    policy: 'redis',         // Use Redis for distributed counting
    fault_tolerant: true,    // Allow traffic if Redis is down
    hide_client_headers: false,
    redis_host: 'redis',
    redis_port: 6379,
  },
};

// Response headers
// X-RateLimit-Limit: 60
// X-RateLimit-Remaining: 45
// X-RateLimit-Reset: 1640000000
```

| Algorithm | Description | Use When |
|-----------|-------------|----------|
| Token bucket | Tokens replenish at fixed rate, consumed per request | Burst-tolerant, smooth throttling |
| Sliding window | Count requests in a rolling time window | Precise limits, no burst |
| Fixed window | Count requests per fixed time interval | Simple, slight burst at window edges |
| Leaky bucket | Process requests at fixed rate, queue excess | Smooth output rate |

### Request Aggregation

```typescript
// BFF aggregation pattern — single client request, multiple backend calls
app.get('/api/dashboard', async (req, res) => {
  const userId = req.user.id;

  // Parallel fetch from multiple services
  const [profile, orders, notifications, recommendations] = await Promise.all([
    userService.getProfile(userId),
    orderService.getRecent(userId, { limit: 5 }),
    notificationService.getUnread(userId),
    recommendationService.getForUser(userId),
  ]);

  // Aggregate into client-optimized response
  res.json({
    user: { name: profile.name, avatar: profile.avatar },
    recentOrders: orders.map(o => ({ id: o.id, status: o.status, total: o.total })),
    unreadCount: notifications.length,
    recommendations: recommendations.slice(0, 3),
  });
});
```

---

## Service Mesh Architecture

### Core Concepts

A service mesh is a dedicated infrastructure layer for service-to-service communication. It uses sidecar proxies deployed alongside each service to handle networking concerns.

```text
┌─────────────────────────────────────────────────┐
│                Control Plane                     │
│  (Configuration, certificates, policies)         │
└───────────┬──────────────┬──────────────┬────────┘
            │              │              │
     ┌──────▼──────┐ ┌────▼────────┐ ┌──▼──────────┐
     │  Service A  │ │  Service B  │ │  Service C  │
     │  ┌────────┐ │ │  ┌────────┐ │ │  ┌────────┐ │
     │  │  App   │ │ │  │  App   │ │ │  │  App   │ │
     │  └───┬────┘ │ │  └───┬────┘ │ │  └───┬────┘ │
     │  ┌───▼────┐ │ │  ┌───▼────┐ │ │  ┌───▼────┐ │
     │  │Sidecar │◄├─┼─▶│Sidecar │◄├─┼─▶│Sidecar │ │
     │  │Proxy   │ │ │  │Proxy   │ │ │  │Proxy   │ │
     │  └────────┘ │ │  └────────┘ │ │  └────────┘ │
     └─────────────┘ └────────────┘ └──────────────┘
           Data Plane (proxies handle all traffic)
```

### Sidecar Proxy Responsibilities

| Responsibility | Description |
|---------------|-------------|
| Traffic routing | Route requests based on rules (headers, weight, path) |
| Load balancing | Distribute traffic across service instances |
| mTLS encryption | Encrypt all service-to-service traffic |
| Circuit breaking | Prevent cascading failures |
| Retry and timeout | Automatic retry with configurable backoff |
| Observability | Emit metrics, traces, and access logs |
| Health checking | Active and passive health checks |
| Rate limiting | Per-service or per-route limits |
| Access control | Authorization policies between services |

### Control Plane vs Data Plane

| Component | Control Plane | Data Plane |
|-----------|--------------|------------|
| Role | Configuration and policy distribution | Request processing |
| Components | Istiod, Linkerd control plane | Envoy proxy, Linkerd proxy |
| Scaling | Single instance or HA pair | One per service instance (sidecar) |
| Failure impact | No new config updates, existing config works | Service-to-service traffic affected |
| Resource usage | Low (control only) | Per-pod overhead (CPU, memory, latency) |

---

## Technology Comparison

### Gateway Comparison

| Feature | Kong | AWS API Gateway | Envoy (standalone) | Traefik | NGINX |
|---------|------|----------------|--------------------|---------| ------|
| Deployment | Self-hosted / Cloud | Managed | Self-hosted | Self-hosted | Self-hosted |
| Plugin ecosystem | Large (Lua, Go) | AWS integrations | Filters (C++, Wasm) | Middleware | Modules |
| Rate limiting | Built-in | Built-in | Filter | Middleware | Module |
| Auth | JWT, OAuth, OIDC | IAM, Cognito, Lambda auth | ext_authz filter | ForwardAuth | Auth module |
| Observability | Prometheus, Datadog | CloudWatch | Prometheus, Zipkin | Prometheus | Stub status |
| gRPC support | Yes | Yes | Native | Yes | Yes |
| WebSocket | Yes | Yes | Yes | Yes | Yes |
| Best for | Multi-cloud, plugin needs | AWS-native workloads | High performance, mesh ingress | Docker/K8s auto-discovery | Simple, proven |

### Service Mesh Comparison

| Feature | Istio | Linkerd | AWS App Mesh | Cilium Service Mesh |
|---------|-------|---------|--------------|---------------------|
| Proxy | Envoy | linkerd2-proxy (Rust) | Envoy | eBPF (no sidecar) |
| Complexity | High | Low | Medium | Medium |
| Resource overhead | Higher (Envoy sidecar) | Lower (lightweight proxy) | Medium | Lowest (kernel-level) |
| mTLS | Automatic | Automatic | Manual config | Automatic |
| Multi-cluster | Yes | Yes (limited) | Cross-account | Yes |
| Traffic management | Advanced (fault injection, mirroring) | Basic (split, retry) | Basic | Advanced |
| Observability | Rich (Kiali, Jaeger, Prometheus) | Built-in dashboard | CloudWatch, X-Ray | Hubble |
| Learning curve | Steep | Gentle | Moderate | Moderate |
| Best for | Complex mesh, advanced traffic | Simple mesh, low overhead | AWS-native workloads | High performance, eBPF |

### Selection Quick Guide

```text
Service mesh selection:
  ├─ < 10 services → No mesh needed. Use library-based patterns.
  ├─ 10-50 services, want simplicity → Linkerd
  ├─ 10-50 services, need advanced traffic mgmt → Istio
  ├─ AWS-native, managed preference → App Mesh
  ├─ Performance-critical, eBPF available → Cilium
  └─ > 50 services, multi-cluster → Istio (with careful tuning)
```

---

## mTLS and Service Identity

### Mutual TLS in Service Mesh

```text
Service A                                         Service B
┌──────────┐                                     ┌──────────┐
│          │── 1. TLS handshake (client cert) ──▶│          │
│  App     │◀─ 2. TLS handshake (server cert) ──│  App     │
│          │── 3. Encrypted traffic ────────────▶│          │
└──────────┘                                     └──────────┘

Both sides present certificates issued by the mesh CA.
Identity is based on service account, not network address.
```

### Identity-Based Authorization

```yaml
# Istio AuthorizationPolicy
apiVersion: security.istio.io/v1
kind: AuthorizationPolicy
metadata:
  name: orders-policy
  namespace: production
spec:
  selector:
    matchLabels:
      app: orders-service
  rules:
    # Allow only payment-service and api-gateway to call orders
    - from:
        - source:
            principals:
              - cluster.local/ns/production/sa/payment-service
              - cluster.local/ns/production/sa/api-gateway
      to:
        - operation:
            methods: ["GET", "POST"]
            paths: ["/api/orders/*"]
    # Deny everything else (implicit deny)
```

### Certificate Management

| Approach | Description | Complexity |
|----------|-------------|------------|
| Mesh-managed CA | Mesh control plane issues and rotates certs | Low (automatic) |
| External CA (Vault) | HashiCorp Vault issues certs, mesh distributes | Medium |
| SPIFFE/SPIRE | Standard identity framework, pluggable CAs | Medium-High |
| Manual certs | Team manages certs manually | High (do not do this) |

**Recommended:** Use mesh-managed CA for most deployments. Integrate with external CA (Vault, AWS ACM PCA) for enterprise compliance requirements.

---

## Observability Through Mesh

### Distributed Tracing

Service mesh proxies automatically inject trace headers and emit spans.

```text
Client → [Gateway span] → [Service A span] → [Service B span] → [Database span]
                                                    │
                                              [Service C span]

Each proxy adds its own span without application code changes.
```

**Trace header propagation:**

| Header | Standard | Used By |
|--------|----------|---------|
| `traceparent` | W3C Trace Context | OpenTelemetry, modern systems |
| `x-request-id` | De facto | Envoy, Istio |
| `x-b3-traceid` | Zipkin B3 | Zipkin, older Istio |

### Mesh-Level Metrics

Standard metrics emitted by sidecar proxies (no application instrumentation needed):

| Metric | Description | Alert On |
|--------|-------------|----------|
| `request_count` | Total requests per service/route | Unexpected traffic drops |
| `request_duration` | Latency histogram (P50, P95, P99) | P99 > SLO threshold |
| `response_code` | Count by status code (2xx, 4xx, 5xx) | 5xx rate > 0.1% |
| `tcp_connections` | Active TCP connections | Approaching connection limits |
| `retry_count` | Automatic retries triggered | High retry rate = unhealthy upstream |

### Golden Signals Dashboard

```text
For each service, track:
  1. Latency     — P50, P95, P99 response time
  2. Traffic     — Requests per second
  3. Errors      — 5xx rate as percentage of total
  4. Saturation  — CPU, memory, connection pool usage

Service mesh provides signals 1-3 automatically.
Signal 4 requires application-level metrics.
```

### Service Topology Visualization

Mesh provides automatic service dependency mapping:

```text
Tools:
  - Kiali (Istio) — Service graph, health status, traffic flow
  - Linkerd Viz — Dashboard with golden metrics per service
  - Hubble (Cilium) — Network flow visibility
  - Jaeger/Tempo — Distributed trace visualization
```

---

## Gateway vs Mesh vs Both

### Comparison Matrix

| Concern | API Gateway | Service Mesh | Both (Recommended) |
|---------|-------------|-------------|-------------------|
| North-south traffic (client → service) | Primary role | Not designed for | Gateway handles |
| East-west traffic (service → service) | Not designed for | Primary role | Mesh handles |
| External authentication | Yes | No | Gateway handles |
| Service-to-service auth (mTLS) | No | Yes | Mesh handles |
| Public rate limiting | Yes | No | Gateway handles |
| Internal circuit breaking | Limited | Yes | Mesh handles |
| External API versioning | Yes | No | Gateway handles |
| Internal traffic splitting | No | Yes | Mesh handles |
| TLS termination (external) | Yes | No | Gateway handles |
| mTLS (internal) | No | Yes | Mesh handles |

### Recommended Architecture

```text
┌──────────────┐
│   Internet   │
└──────┬───────┘
       │
┌──────▼───────┐  ← North-south boundary
│ API Gateway  │  Auth, rate limiting, TLS termination, routing
│ (Kong/Envoy) │
└──────┬───────┘
       │
┌──────▼───────────────────────────────┐
│         Service Mesh (Istio/Linkerd) │  ← East-west boundary
│                                      │  mTLS, retries, circuit breaking,
│  ┌─────┐   ┌─────┐   ┌─────┐       │  observability, traffic management
│  │Svc A│◄─▶│Svc B│◄─▶│Svc C│       │
│  └─────┘   └─────┘   └─────┘       │
└──────────────────────────────────────┘
```

### When You Do NOT Need a Service Mesh

| Scenario | Why No Mesh |
|----------|-------------|
| < 10 services | Overhead exceeds benefit |
| Single team, single repo | Library-based patterns suffice |
| Serverless architecture | Functions are too short-lived for sidecars |
| Low traffic internal tools | Complexity not justified |
| Early-stage startup | Focus on product, not infrastructure |

**Alternatives to mesh for small deployments:**

- Library-based retries and circuit breaking (p-retry, opossum)
- Application-level mTLS (cert-manager + application config)
- OpenTelemetry SDK for observability (no mesh needed)

---

## Implementation Patterns

### Canary Deployment via Mesh

```yaml
# Istio: Route 95% to v1, 5% to v2
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: orders
spec:
  hosts:
    - orders
  http:
    - route:
        - destination:
            host: orders
            subset: v1
          weight: 95
        - destination:
            host: orders
            subset: v2
          weight: 5
---
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: orders
spec:
  host: orders
  subsets:
    - name: v1
      labels:
        version: v1
    - name: v2
      labels:
        version: v2
```

### Retry and Timeout Configuration

```yaml
# Istio retry policy
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: orders
spec:
  hosts:
    - orders
  http:
    - timeout: 3s
      retries:
        attempts: 3
        perTryTimeout: 1s
        retryOn: 5xx,reset,connect-failure,retriable-4xx
      route:
        - destination:
            host: orders
```

### Circuit Breaker Configuration

```yaml
# Istio circuit breaker
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: orders
spec:
  host: orders
  trafficPolicy:
    connectionPool:
      tcp:
        maxConnections: 100
      http:
        http1MaxPendingRequests: 100
        http2MaxRequests: 1000
        maxRequestsPerConnection: 10
    outlierDetection:
      consecutive5xxErrors: 5
      interval: 10s
      baseEjectionTime: 30s
      maxEjectionPercent: 50
```

---

## Anti-Patterns

### 1. Mesh for Everything

```text
[FAIL] Deploying a service mesh for 3 services because "everyone uses Istio"
       → Massive operational overhead for minimal benefit

[PASS] Start with library-based patterns. Adopt mesh when you have
       10+ services and measurable networking pain.
```

### 2. Gateway as Service Bus

```text
[FAIL] Putting business logic, data transformation, and orchestration in the gateway
       → Gateway becomes a bottleneck and single point of failure for logic

[PASS] Gateway handles cross-cutting concerns only (auth, rate limiting, routing).
       Business logic stays in services.
```

### 3. Ignoring Sidecar Resource Overhead

```text
[FAIL] Deploying mesh without accounting for sidecar CPU/memory per pod
       → Resource exhaustion, unexpected costs, latency increase

[PASS] Budget 50-128MB memory and 0.1-0.5 CPU per sidecar proxy.
       Monitor mesh overhead as a first-class metric.
```

### 4. No Mesh Bypass for Debugging

```text
[FAIL] No way to bypass the mesh for troubleshooting
       → Cannot isolate whether issues are mesh-related or application-related

[PASS] Maintain ability to disable sidecar injection per namespace or pod.
       Have runbooks for mesh-bypass debugging.
```

### 5. mTLS Without Identity Policies

```text
[FAIL] Enabling mTLS but no authorization policies → all services can call all services
       → mTLS only encrypts traffic, it does not authorize

[PASS] Pair mTLS with explicit AuthorizationPolicy rules.
       Default deny, explicit allow per service pair.
```

---

## Decision Framework

### Do You Need an API Gateway?

```text
1. Do you expose APIs to external clients?              [Yes → You need a gateway]
2. Do you need centralized auth for external traffic?   [Yes → Gateway]
3. Do you need rate limiting for public APIs?            [Yes → Gateway]
4. Do you have multiple BFF needs (mobile, web, partner)? [Yes → Multiple gateways]
5. Internal-only services?                               [Gateway optional, mesh sufficient]
```

### Do You Need a Service Mesh?

```text
1. How many services?                    [< 10 → No, 10-50 → Maybe, > 50 → Yes]
2. Do you need mTLS between services?    [Yes → +2]
3. Do you need advanced traffic management? [Yes → +2]
4. Is observability a gap today?          [Yes → +1]
5. Does the team have K8s experience?     [Yes → +1, No → -2]
6. Are you running on Kubernetes?         [Yes → +1, No → -2]

Score: 0-2 → Library-based patterns
Score: 3-4 → Linkerd (simpler mesh)
Score: 5+  → Istio or Cilium (full mesh)
```

### Gateway Selection

```text
Choosing a gateway:
  ├─ AWS-native, managed preference → AWS API Gateway
  ├─ Multi-cloud, plugin extensibility → Kong
  ├─ Performance-critical, already using Envoy → Envoy as gateway
  ├─ Kubernetes auto-discovery → Traefik
  ├─ Simple reverse proxy, proven → NGINX
  └─ GraphQL federation → Apollo Router
```

---

## Cross-References

- [modern-patterns.md](modern-patterns.md) — Service mesh and microservices overview
- [scalability-reliability-guide.md](scalability-reliability-guide.md) — Load balancing, circuit breakers, resilience
- [migration-modernization-guide.md](migration-modernization-guide.md) — Strangler fig pattern with gateway routing
- [data-architecture-patterns.md](data-architecture-patterns.md) — Service-to-service data patterns
- [../software-backend/SKILL.md](../software-backend/SKILL.md) — Backend service implementation
- [../../ops-devops-platform/SKILL.md](../../ops-devops-platform/SKILL.md) — Kubernetes, CI/CD, deployment strategies
- [../../software-security-appsec/SKILL.md](../../software-security-appsec/SKILL.md) — Zero-trust security, mTLS
