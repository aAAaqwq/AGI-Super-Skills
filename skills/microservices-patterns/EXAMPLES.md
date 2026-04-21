# Microservices Patterns - Comprehensive Examples

This document provides detailed, production-ready examples of microservices patterns using Istio and Kubernetes.

## Table of Contents

1. [Istio Installation and Configuration](#example-1-istio-installation-and-configuration)
2. [Basic Service Deployment with Sidecar](#example-2-basic-service-deployment-with-sidecar)
3. [Virtual Service for Intelligent Routing](#example-3-virtual-service-for-intelligent-routing)
4. [Destination Rule with Load Balancing](#example-4-destination-rule-with-load-balancing)
5. [Circuit Breaker Implementation](#example-5-circuit-breaker-implementation)
6. [Retry and Timeout Policies](#example-6-retry-and-timeout-policies)
7. [Canary Deployment with Traffic Splitting](#example-7-canary-deployment-with-traffic-splitting)
8. [Blue-Green Deployment](#example-8-blue-green-deployment)
9. [Fault Injection for Chaos Testing](#example-9-fault-injection-for-chaos-testing)
10. [mTLS Security Configuration](#example-10-mtls-security-configuration)
11. [Authorization Policies](#example-11-authorization-policies)
12. [Gateway Configuration for Ingress](#example-12-gateway-configuration-for-ingress)
13. [Rate Limiting Implementation](#example-13-rate-limiting-implementation)
14. [Distributed Tracing Setup](#example-14-distributed-tracing-setup)
15. [Multi-Cluster Service Mesh](#example-15-multi-cluster-service-mesh)
16. [Service Mesh Federation](#example-16-service-mesh-federation)
17. [Observability with Kiali](#example-17-observability-with-kiali)
18. [Advanced Traffic Management](#example-18-advanced-traffic-management)
19. [Saga Pattern Implementation](#example-19-saga-pattern-implementation)
20. [API Gateway Pattern](#example-20-api-gateway-pattern)

---

## Example 1: Istio Installation and Configuration

### Prerequisites

```bash
# Ensure Kubernetes cluster is running
kubectl cluster-info

# Check kubectl version (1.28+ recommended)
kubectl version --client
```

### Install Istio

```bash
# Download Istio (latest stable version)
curl -L https://istio.io/downloadIstio | sh -

# Navigate to Istio directory
cd istio-1.20.0

# Add istioctl to PATH
export PATH=$PWD/bin:$PATH

# Verify istioctl installation
istioctl version
```

### Install Istio with Custom Profile

```bash
# Option 1: Demo profile (for learning/testing)
istioctl install --set profile=demo -y

# Option 2: Production profile
istioctl install --set profile=production -y

# Option 3: Custom configuration
cat <<EOF | istioctl install -y -f -
apiVersion: install.istio.io/v1alpha1
kind: IstioOperator
metadata:
  namespace: istio-system
  name: istio-controlplane
spec:
  profile: production
  meshConfig:
    accessLogFile: /dev/stdout
    enableTracing: true
    defaultConfig:
      tracing:
        sampling: 10.0
        zipkin:
          address: zipkin.istio-system:9411
  components:
    pilot:
      k8s:
        resources:
          requests:
            cpu: 500m
            memory: 2048Mi
        hpaSpec:
          minReplicas: 2
          maxReplicas: 5
    ingressGateways:
    - name: istio-ingressgateway
      enabled: true
      k8s:
        resources:
          requests:
            cpu: 500m
            memory: 512Mi
        hpaSpec:
          minReplicas: 2
          maxReplicas: 5
        service:
          type: LoadBalancer
          ports:
          - port: 80
            targetPort: 8080
            name: http2
          - port: 443
            targetPort: 8443
            name: https
EOF
```

### Verify Installation

```bash
# Check Istio components
kubectl get pods -n istio-system

# Expected output:
# istio-ingressgateway-xxx   1/1   Running
# istiod-xxx                 1/1   Running

# Verify installation
istioctl verify-install

# Check mesh configuration
kubectl get configmap istio -n istio-system -o yaml
```

### Enable Sidecar Injection

```bash
# Enable automatic sidecar injection for default namespace
kubectl label namespace default istio-injection=enabled

# Verify namespace label
kubectl get namespace -L istio-injection

# Enable for specific namespaces
kubectl label namespace production istio-injection=enabled
kubectl label namespace staging istio-injection=enabled
```

### Install Observability Add-ons

```bash
# Install Kiali, Prometheus, Grafana, Jaeger
kubectl apply -f samples/addons/

# Wait for deployments
kubectl rollout status deployment/kiali -n istio-system
kubectl rollout status deployment/prometheus -n istio-system
kubectl rollout status deployment/grafana -n istio-system
kubectl rollout status deployment/jaeger -n istio-system

# Access dashboards (in separate terminals)
istioctl dashboard kiali
istioctl dashboard prometheus
istioctl dashboard grafana
istioctl dashboard jaeger
```

---

## Example 2: Basic Service Deployment with Sidecar

### Application Deployment

```yaml
# deployment.yaml
apiVersion: v1
kind: Service
metadata:
  name: product-service
  labels:
    app: product
    service: product
spec:
  ports:
  - port: 8080
    name: http
    targetPort: 8080
  selector:
    app: product
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: product-v1
  labels:
    app: product
    version: v1
spec:
  replicas: 3
  selector:
    matchLabels:
      app: product
      version: v1
  template:
    metadata:
      labels:
        app: product
        version: v1
    spec:
      containers:
      - name: product
        image: myregistry/product-service:v1
        ports:
        - containerPort: 8080
        env:
        - name: VERSION
          value: "v1"
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 500m
            memory: 512Mi
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 5
```

### Deploy and Verify Sidecar

```bash
# Deploy the service
kubectl apply -f deployment.yaml

# Verify pods have 2 containers (app + sidecar)
kubectl get pods -l app=product

# Expected output:
# NAME                          READY   STATUS    RESTARTS   AGE
# product-v1-xxx                2/2     Running   0          1m

# Check sidecar injection
kubectl describe pod product-v1-xxx | grep -A 10 "istio-proxy"

# View sidecar logs
kubectl logs product-v1-xxx -c istio-proxy

# Check proxy configuration
istioctl proxy-config listeners product-v1-xxx
istioctl proxy-config routes product-v1-xxx
istioctl proxy-config clusters product-v1-xxx
```

### Manual Sidecar Injection (Alternative)

```bash
# For namespaces without automatic injection
istioctl kube-inject -f deployment.yaml | kubectl apply -f -

# Or generate injected YAML
istioctl kube-inject -f deployment.yaml > deployment-injected.yaml
kubectl apply -f deployment-injected.yaml
```

---

## Example 3: Virtual Service for Intelligent Routing

### Header-Based Routing

```yaml
# virtualservice-header-routing.yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: product-routes
spec:
  hosts:
  - product-service
  http:
  # Route premium users to v2
  - match:
    - headers:
        user-tier:
          exact: premium
    route:
    - destination:
        host: product-service
        subset: v2
  # Route mobile app to v2
  - match:
    - headers:
        user-agent:
          regex: ".*Mobile.*"
    route:
    - destination:
        host: product-service
        subset: v2
  # Default route to v1
  - route:
    - destination:
        host: product-service
        subset: v1
```

### URI-Based Routing

```yaml
# virtualservice-uri-routing.yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: api-routes
spec:
  hosts:
  - api.example.com
  http:
  # Route /api/v2/* to new service
  - match:
    - uri:
        prefix: /api/v2
    rewrite:
      uri: /
    route:
    - destination:
        host: api-service-v2
        port:
          number: 8080
  # Route /api/v1/* to legacy service
  - match:
    - uri:
        prefix: /api/v1
    rewrite:
      uri: /
    route:
    - destination:
        host: api-service-v1
        port:
          number: 8080
  # Redirect old paths
  - match:
    - uri:
        exact: /old-api
    redirect:
      uri: /api/v2
      authority: api.example.com
```

### Method-Based Routing

```yaml
# virtualservice-method-routing.yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: order-routes
spec:
  hosts:
  - order-service
  http:
  # Read operations to read-optimized service
  - match:
    - method:
        exact: GET
    route:
    - destination:
        host: order-read-service
  # Write operations to write service
  - match:
    - method:
        regex: "POST|PUT|DELETE"
    route:
    - destination:
        host: order-write-service
```

### Apply and Test

```bash
# Apply virtual service
kubectl apply -f virtualservice-header-routing.yaml

# Test header-based routing
kubectl run -it --rm test-pod --image=curlimages/curl --restart=Never -- \
  curl -H "user-tier: premium" http://product-service:8080/

# Verify routing
istioctl proxy-config routes product-v1-xxx --name 8080 -o json
```

---

## Example 4: Destination Rule with Load Balancing

### Round Robin Load Balancing

```yaml
# destinationrule-roundrobin.yaml
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: product-lb
spec:
  host: product-service
  trafficPolicy:
    loadBalancer:
      simple: ROUND_ROBIN
    connectionPool:
      tcp:
        maxConnections: 100
      http:
        http1MaxPendingRequests: 50
        http2MaxRequests: 100
        maxRequestsPerConnection: 2
  subsets:
  - name: v1
    labels:
      version: v1
  - name: v2
    labels:
      version: v2
```

### Least Request Load Balancing

```yaml
# destinationrule-leastrequest.yaml
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: recommendation-lb
spec:
  host: recommendation-service
  trafficPolicy:
    loadBalancer:
      simple: LEAST_REQUEST
      leastRequestLbConfig:
        choiceCount: 2  # P2C (Power of Two Choices)
    connectionPool:
      tcp:
        maxConnections: 50
        connectTimeout: 5s
        tcpKeepalive:
          time: 7200s
          interval: 75s
      http:
        http2MaxRequests: 100
        maxRequestsPerConnection: 5
```

### Consistent Hash Load Balancing

```yaml
# destinationrule-consistenthash.yaml
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: session-lb
spec:
  host: session-service
  trafficPolicy:
    loadBalancer:
      consistentHash:
        # Option 1: Hash by HTTP header
        httpHeaderName: "user-id"
        # Option 2: Hash by cookie
        # httpCookie:
        #   name: "session-cookie"
        #   ttl: 3600s
        # Option 3: Hash by source IP
        # useSourceIp: true
```

### Apply and Monitor

```bash
# Apply destination rule
kubectl apply -f destinationrule-roundrobin.yaml

# Verify configuration
istioctl proxy-config cluster product-v1-xxx --fqdn product-service.default.svc.cluster.local -o json

# Monitor load balancing
kubectl logs -l app=product -c istio-proxy --tail=100 -f
```

---

## Example 5: Circuit Breaker Implementation

### Comprehensive Circuit Breaker

```yaml
# destinationrule-circuitbreaker.yaml
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: payment-circuit-breaker
spec:
  host: payment-service
  trafficPolicy:
    loadBalancer:
      simple: LEAST_REQUEST
    connectionPool:
      tcp:
        maxConnections: 100
      http:
        http1MaxPendingRequests: 50
        http2MaxRequests: 100
        maxRequestsPerConnection: 2
        idleTimeout: 60s
    outlierDetection:
      consecutiveGatewayErrors: 5
      consecutive5xxErrors: 5
      interval: 30s
      baseEjectionTime: 30s
      maxEjectionPercent: 50
      minHealthPercent: 40
      splitExternalLocalOriginErrors: true
  subsets:
  - name: v1
    labels:
      version: v1
    trafficPolicy:
      outlierDetection:
        consecutiveGatewayErrors: 3
        consecutive5xxErrors: 3
        interval: 20s
        baseEjectionTime: 60s
```

### Test Circuit Breaker

```bash
# Deploy test client
kubectl apply -f - <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: load-test
spec:
  containers:
  - name: fortio
    image: fortio/fortio
    command: ["/bin/sh", "-c", "sleep 3600"]
EOF

# Wait for pod
kubectl wait --for=condition=Ready pod/load-test

# Test normal load
kubectl exec load-test -c fortio -- \
  fortio load -c 2 -qps 0 -n 20 -loglevel Warning \
  http://payment-service:8080/

# Test circuit breaker triggering
kubectl exec load-test -c fortio -- \
  fortio load -c 10 -qps 0 -n 1000 -loglevel Warning \
  http://payment-service:8080/

# Check ejected instances
istioctl proxy-config endpoints load-test | grep payment-service

# View circuit breaker stats
kubectl exec load-test -c istio-proxy -- \
  curl localhost:15000/stats | grep payment-service | grep outlier
```

### Circuit Breaker Monitoring

```yaml
# servicemonitor.yaml (for Prometheus)
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: circuit-breaker-monitor
spec:
  selector:
    matchLabels:
      app: payment
  endpoints:
  - port: http-envoy-prom
    interval: 15s
```

**Key Metrics to Monitor:**

```promql
# Ejection rate
sum(rate(envoy_cluster_outlier_detection_ejections_active[5m]))

# Consecutive errors
sum(rate(envoy_cluster_outlier_detection_ejections_consecutive_5xx[5m]))

# Overflow requests (circuit open)
sum(rate(envoy_cluster_upstream_rq_pending_overflow[5m]))
```

---

## Example 6: Retry and Timeout Policies

### Comprehensive Retry Configuration

```yaml
# virtualservice-retry-timeout.yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: order-resilience
spec:
  hosts:
  - order-service
  http:
  - route:
    - destination:
        host: order-service
        subset: v1
    retries:
      attempts: 3
      perTryTimeout: 2s
      retryOn: 5xx,reset,connect-failure,refused-stream,retriable-status-codes
      retryRemoteLocalities: true
    timeout: 10s
    fault:
      delay:
        percentage:
          value: 0.1
        fixedDelay: 5s
```

### Per-Route Timeout Policies

```yaml
# virtualservice-route-timeouts.yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: api-timeouts
spec:
  hosts:
  - api-service
  http:
  # Fast endpoint with short timeout
  - match:
    - uri:
        prefix: /api/fast
    route:
    - destination:
        host: api-service
    timeout: 1s
    retries:
      attempts: 2
      perTryTimeout: 500ms
  # Slow endpoint with longer timeout
  - match:
    - uri:
        prefix: /api/slow
    route:
    - destination:
        host: api-service
    timeout: 30s
    retries:
      attempts: 1
      perTryTimeout: 15s
  # Default
  - route:
    - destination:
        host: api-service
    timeout: 5s
```

### Exponential Backoff Configuration

```yaml
# envoyfilter-retry-backoff.yaml
apiVersion: networking.istio.io/v1alpha3
kind: EnvoyFilter
metadata:
  name: retry-backoff
spec:
  workloadSelector:
    labels:
      app: order
  configPatches:
  - applyTo: HTTP_ROUTE
    match:
      context: SIDECAR_OUTBOUND
      routeConfiguration:
        vhost:
          name: order-service.default.svc.cluster.local:8080
    patch:
      operation: MERGE
      value:
        route:
          retry_policy:
            retry_back_off:
              base_interval: 0.5s
              max_interval: 10s
            num_retries: 5
```

### Test Retry and Timeout

```bash
# Deploy test service with delays
kubectl apply -f - <<EOF
apiVersion: v1
kind: Service
metadata:
  name: slow-service
spec:
  selector:
    app: slow
  ports:
  - port: 8080
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: slow-service
spec:
  replicas: 2
  selector:
    matchLabels:
      app: slow
  template:
    metadata:
      labels:
        app: slow
    spec:
      containers:
      - name: httpbin
        image: kennethreitz/httpbin
        ports:
        - containerPort: 80
EOF

# Test timeout
kubectl run -it --rm test --image=curlimages/curl --restart=Never -- \
  curl -v http://slow-service:8080/delay/15

# Monitor retries
kubectl logs -l app=order -c istio-proxy --tail=100 | grep -i retry
```

---

## Example 7: Canary Deployment with Traffic Splitting

### Initial Setup - Deploy v1

```yaml
# product-v1-deployment.yaml
apiVersion: v1
kind: Service
metadata:
  name: product-service
spec:
  selector:
    app: product
  ports:
  - port: 8080
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: product-v1
spec:
  replicas: 3
  selector:
    matchLabels:
      app: product
      version: v1
  template:
    metadata:
      labels:
        app: product
        version: v1
    spec:
      containers:
      - name: product
        image: myregistry/product:v1
        ports:
        - containerPort: 8080
```

### Deploy Canary v2

```yaml
# product-v2-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: product-v2
spec:
  replicas: 1  # Start with 1 replica for canary
  selector:
    matchLabels:
      app: product
      version: v2
  template:
    metadata:
      labels:
        app: product
        version: v2
        canary: "true"
    spec:
      containers:
      - name: product
        image: myregistry/product:v2
        ports:
        - containerPort: 8080
```

### Traffic Splitting Configuration

```yaml
# canary-virtualservice.yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: product-canary
spec:
  hosts:
  - product-service
  http:
  - match:
    - headers:
        canary:
          exact: "true"
    route:
    - destination:
        host: product-service
        subset: v2
  - route:
    - destination:
        host: product-service
        subset: v1
      weight: 95
    - destination:
        host: product-service
        subset: v2
      weight: 5
---
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: product-canary
spec:
  host: product-service
  subsets:
  - name: v1
    labels:
      version: v1
  - name: v2
    labels:
      version: v2
```

### Progressive Rollout Script

```bash
#!/bin/bash
# canary-rollout.sh

# Stage 1: 5% canary
echo "Stage 1: 5% traffic to v2"
kubectl apply -f - <<EOF
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: product-canary
spec:
  hosts:
  - product-service
  http:
  - route:
    - destination:
        host: product-service
        subset: v1
      weight: 95
    - destination:
        host: product-service
        subset: v2
      weight: 5
EOF

echo "Monitoring for 5 minutes..."
sleep 300

# Check error rates
ERROR_RATE=$(kubectl logs -l app=product,version=v2 -c istio-proxy --tail=1000 | \
  grep -c "HTTP/1.1\" 5[0-9][0-9]")

if [ $ERROR_RATE -gt 10 ]; then
  echo "High error rate detected! Rolling back..."
  kubectl delete virtualservice product-canary
  exit 1
fi

# Stage 2: 25% canary
echo "Stage 2: 25% traffic to v2"
kubectl apply -f - <<EOF
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: product-canary
spec:
  hosts:
  - product-service
  http:
  - route:
    - destination:
        host: product-service
        subset: v1
      weight: 75
    - destination:
        host: product-service
        subset: v2
      weight: 25
EOF

sleep 300

# Stage 3: 50% canary
echo "Stage 3: 50% traffic to v2"
kubectl apply -f - <<EOF
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: product-canary
spec:
  hosts:
  - product-service
  http:
  - route:
    - destination:
        host: product-service
        subset: v1
      weight: 50
    - destination:
        host: product-service
        subset: v2
      weight: 50
EOF

sleep 300

# Stage 4: 100% canary
echo "Stage 4: 100% traffic to v2"
kubectl apply -f - <<EOF
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: product-canary
spec:
  hosts:
  - product-service
  http:
  - route:
    - destination:
        host: product-service
        subset: v2
      weight: 100
EOF

# Scale down v1
kubectl scale deployment product-v1 --replicas=0

echo "Canary rollout complete!"
```

### Monitor Canary Deployment

```bash
# Monitor traffic distribution
watch -n 1 'kubectl logs -l app=product -c istio-proxy --tail=50 | grep "HTTP/1.1" | tail -10'

# Check metrics in Prometheus
# v1 traffic
sum(rate(istio_requests_total{destination_service="product-service",destination_version="v1"}[1m]))

# v2 traffic
sum(rate(istio_requests_total{destination_service="product-service",destination_version="v2"}[1m]))

# Error rate comparison
sum(rate(istio_requests_total{destination_service="product-service",destination_version="v2",response_code=~"5.."}[1m]))
```

---

## Example 8: Blue-Green Deployment

### Setup Blue (Current) and Green (New) Deployments

```yaml
# bluegreen-deployment.yaml
apiVersion: v1
kind: Service
metadata:
  name: app-service
spec:
  selector:
    app: myapp
  ports:
  - port: 8080
---
# Blue deployment (current production)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: app-blue
spec:
  replicas: 3
  selector:
    matchLabels:
      app: myapp
      deployment: blue
  template:
    metadata:
      labels:
        app: myapp
        deployment: blue
        version: v1
    spec:
      containers:
      - name: app
        image: myregistry/myapp:v1.0
        ports:
        - containerPort: 8080
---
# Green deployment (new version)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: app-green
spec:
  replicas: 3
  selector:
    matchLabels:
      app: myapp
      deployment: green
  template:
    metadata:
      labels:
        app: myapp
        deployment: green
        version: v2
    spec:
      containers:
      - name: app
        image: myregistry/myapp:v2.0
        ports:
        - containerPort: 8080
```

### Blue-Green Traffic Control

```yaml
# bluegreen-virtualservice.yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: app-bluegreen
spec:
  hosts:
  - app-service
  http:
  - route:
    - destination:
        host: app-service
        subset: blue
      weight: 100
    - destination:
        host: app-service
        subset: green
      weight: 0
---
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: app-bluegreen
spec:
  host: app-service
  subsets:
  - name: blue
    labels:
      deployment: blue
  - name: green
    labels:
      deployment: green
```

### Switch Traffic to Green

```bash
#!/bin/bash
# switch-to-green.sh

echo "Switching traffic from blue to green..."

# Switch all traffic to green
kubectl apply -f - <<EOF
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: app-bluegreen
spec:
  hosts:
  - app-service
  http:
  - route:
    - destination:
        host: app-service
        subset: green
      weight: 100
EOF

echo "Traffic switched to green deployment"
echo "Blue deployment still running for quick rollback if needed"

# Monitor for 30 minutes before scaling down blue
echo "Monitoring green deployment..."
sleep 1800

# If all good, scale down blue
read -p "Scale down blue deployment? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
  kubectl scale deployment app-blue --replicas=0
  echo "Blue deployment scaled down"
fi
```

### Instant Rollback

```bash
# rollback-to-blue.sh
#!/bin/bash

echo "Rolling back to blue deployment..."

kubectl apply -f - <<EOF
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: app-bluegreen
spec:
  hosts:
  - app-service
  http:
  - route:
    - destination:
        host: app-service
        subset: blue
      weight: 100
EOF

# Scale up blue if needed
kubectl scale deployment app-blue --replicas=3

echo "Rollback complete - traffic routed to blue"
```

---

## Example 9: Fault Injection for Chaos Testing

### HTTP Delay Injection

```yaml
# fault-injection-delay.yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: reviews-delay
spec:
  hosts:
  - reviews-service
  http:
  - match:
    - headers:
        test-fault:
          exact: "delay"
    fault:
      delay:
        percentage:
          value: 100
        fixedDelay: 7s
    route:
    - destination:
        host: reviews-service
  - route:
    - destination:
        host: reviews-service
```

### HTTP Abort Injection

```yaml
# fault-injection-abort.yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: payment-abort
spec:
  hosts:
  - payment-service
  http:
  - match:
    - headers:
        test-fault:
          exact: "abort"
    fault:
      abort:
        percentage:
          value: 100
        httpStatus: 503
    route:
    - destination:
        host: payment-service
  - route:
    - destination:
        host: payment-service
```

### Gradual Fault Injection (Chaos Engineering)

```yaml
# chaos-engineering.yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: cart-chaos
spec:
  hosts:
  - cart-service
  http:
  - fault:
      delay:
        percentage:
          value: 10  # 10% of requests
        fixedDelay: 5s
      abort:
        percentage:
          value: 5  # 5% of requests
        httpStatus: 500
    route:
    - destination:
        host: cart-service
```

### Test Fault Injection

```bash
# Test delay injection
kubectl run -it --rm test --image=curlimages/curl --restart=Never -- \
  time curl -H "test-fault: delay" http://reviews-service:8080/

# Test abort injection
kubectl run -it --rm test --image=curlimages/curl --restart=Never -- \
  curl -v -H "test-fault: abort" http://payment-service:8080/

# Monitor impact on dependent services
kubectl logs -l app=frontend -c istio-proxy --tail=100 -f
```

### Advanced Chaos Testing

```yaml
# multi-fault-chaos.yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: order-chaos-test
spec:
  hosts:
  - order-service
  http:
  # Simulate database slowdown
  - match:
    - uri:
        prefix: /api/orders
    fault:
      delay:
        percentage:
          value: 30
        fixedDelay: 2s
    route:
    - destination:
        host: order-service
    timeout: 5s
    retries:
      attempts: 2
      perTryTimeout: 2s
      retryOn: 5xx
  # Simulate payment gateway failures
  - match:
    - uri:
        prefix: /api/payment
    fault:
      abort:
        percentage:
          value: 20
        httpStatus: 503
    route:
    - destination:
        host: order-service
```

---

## Example 10: mTLS Security Configuration

### Enable Mesh-Wide mTLS (STRICT Mode)

```yaml
# mtls-strict.yaml
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default
  namespace: istio-system
spec:
  mtls:
    mode: STRICT
```

### Namespace-Level mTLS

```yaml
# mtls-namespace.yaml
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: production-mtls
  namespace: production
spec:
  mtls:
    mode: STRICT
---
# Staging with permissive mode (for migration)
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: staging-mtls
  namespace: staging
spec:
  mtls:
    mode: PERMISSIVE
```

### Service-Level mTLS

```yaml
# mtls-service.yaml
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: payment-mtls
  namespace: default
spec:
  selector:
    matchLabels:
      app: payment
  mtls:
    mode: STRICT
  portLevelMtls:
    8080:
      mode: STRICT
    8090:
      mode: DISABLE  # Health check port
```

### Destination Rule for mTLS

```yaml
# destinationrule-mtls.yaml
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: backend-mtls
spec:
  host: backend-service
  trafficPolicy:
    tls:
      mode: ISTIO_MUTUAL  # Use Istio-generated certificates
    connectionPool:
      tcp:
        maxConnections: 100
```

### Verify mTLS Configuration

```bash
# Check mTLS status for all services
istioctl authn tls-check product-v1-xxx payment-service

# Expected output:
# HOST:PORT                          STATUS     SERVER        CLIENT     AUTHN POLICY        DESTINATION RULE
# payment-service.default.svc.cluster.local:8080  OK         STRICT        ISTIO_MUTUAL  /default                 payment-service/default

# View certificates
istioctl proxy-config secret product-v1-xxx -o json | jq '.dynamicActiveSecrets[0].secret.tlsCertificate.certificateChain.inlineBytes' | sed 's/"//g' | base64 -d | openssl x509 -text -noout

# Monitor mTLS metrics
kubectl exec product-v1-xxx -c istio-proxy -- \
  curl -s localhost:15000/stats | grep ssl
```

---

## Example 11: Authorization Policies

### Deny All Traffic (Secure by Default)

```yaml
# authz-deny-all.yaml
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: deny-all
  namespace: production
spec:
  {}  # Empty spec = deny all
```

### Allow Specific Service-to-Service Communication

```yaml
# authz-service-to-service.yaml
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: payment-policy
  namespace: default
spec:
  selector:
    matchLabels:
      app: payment
  action: ALLOW
  rules:
  # Allow from order service
  - from:
    - source:
        principals:
        - "cluster.local/ns/default/sa/order-service"
    to:
    - operation:
        methods: ["POST"]
        paths: ["/api/process-payment"]
  # Allow from admin service
  - from:
    - source:
        principals:
        - "cluster.local/ns/default/sa/admin-service"
    to:
    - operation:
        methods: ["GET", "POST"]
        paths: ["/api/*"]
```

### Path-Based Authorization

```yaml
# authz-path-based.yaml
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: api-authorization
  namespace: default
spec:
  selector:
    matchLabels:
      app: api-gateway
  action: ALLOW
  rules:
  # Public endpoints - no authentication needed
  - to:
    - operation:
        paths:
        - "/health"
        - "/metrics"
        - "/api/public/*"
  # Protected endpoints - require authentication
  - from:
    - source:
        requestPrincipals: ["*"]
    to:
    - operation:
        paths: ["/api/protected/*"]
  # Admin endpoints - specific principals only
  - from:
    - source:
        principals:
        - "cluster.local/ns/default/sa/admin-user"
    to:
    - operation:
        paths: ["/api/admin/*"]
```

### Method and Header-Based Authorization

```yaml
# authz-advanced.yaml
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: order-advanced-authz
  namespace: default
spec:
  selector:
    matchLabels:
      app: order
  action: ALLOW
  rules:
  # Read operations allowed for all authenticated users
  - from:
    - source:
        requestPrincipals: ["*"]
    to:
    - operation:
        methods: ["GET", "HEAD"]
  # Write operations require specific role
  - from:
    - source:
        requestPrincipals: ["*"]
    when:
    - key: request.auth.claims[role]
      values: ["admin", "order-manager"]
    to:
    - operation:
        methods: ["POST", "PUT", "DELETE"]
  # Specific IPs for sensitive operations
  - from:
    - source:
        ipBlocks:
        - "10.0.0.0/8"
        - "172.16.0.0/12"
    to:
    - operation:
        paths: ["/api/sensitive/*"]
```

### Deny Policy Example

```yaml
# authz-deny.yaml
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: deny-external-access
  namespace: default
spec:
  selector:
    matchLabels:
      app: internal-service
  action: DENY
  rules:
  # Deny traffic not from cluster
  - from:
    - source:
        notNamespaces: ["default", "production", "staging"]
  # Deny specific paths
  - to:
    - operation:
        paths:
        - "/admin/*"
        - "/debug/*"
```

### Test Authorization

```bash
# Test allowed request
kubectl exec frontend-xxx -c istio-proxy -- \
  curl -v http://payment-service:8080/api/process-payment

# Test denied request
kubectl exec unauthorized-pod -c istio-proxy -- \
  curl -v http://payment-service:8080/api/process-payment

# Check authorization logs
kubectl logs payment-v1-xxx -c istio-proxy | grep RBAC
```

---

## Example 12: Gateway Configuration for Ingress

### Basic Ingress Gateway

```yaml
# gateway-basic.yaml
apiVersion: networking.istio.io/v1beta1
kind: Gateway
metadata:
  name: app-gateway
spec:
  selector:
    istio: ingressgateway
  servers:
  - port:
      number: 80
      name: http
      protocol: HTTP
    hosts:
    - "example.com"
    - "www.example.com"
---
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: app-routes
spec:
  hosts:
  - "example.com"
  - "www.example.com"
  gateways:
  - app-gateway
  http:
  - match:
    - uri:
        prefix: /api
    route:
    - destination:
        host: api-service
        port:
          number: 8080
  - match:
    - uri:
        prefix: /
    route:
    - destination:
        host: frontend-service
        port:
          number: 3000
```

### HTTPS Gateway with TLS

```yaml
# gateway-https.yaml
apiVersion: networking.istio.io/v1beta1
kind: Gateway
metadata:
  name: secure-gateway
spec:
  selector:
    istio: ingressgateway
  servers:
  # HTTP to HTTPS redirect
  - port:
      number: 80
      name: http
      protocol: HTTP
    hosts:
    - "secure.example.com"
    tls:
      httpsRedirect: true
  # HTTPS endpoint
  - port:
      number: 443
      name: https
      protocol: HTTPS
    tls:
      mode: SIMPLE
      credentialName: example-com-cert  # Kubernetes secret
    hosts:
    - "secure.example.com"
```

### Create TLS Secret

```bash
# Create self-signed certificate (for testing)
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes \
  -subj "/CN=secure.example.com"

# Create Kubernetes secret in istio-system namespace
kubectl create -n istio-system secret tls example-com-cert \
  --key=key.pem \
  --cert=cert.pem

# Or use cert-manager for automatic certificate management
kubectl apply -f - <<EOF
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: example-com
  namespace: istio-system
spec:
  secretName: example-com-cert
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  dnsNames:
  - secure.example.com
  - www.secure.example.com
EOF
```

### Multi-Host Gateway

```yaml
# gateway-multi-host.yaml
apiVersion: networking.istio.io/v1beta1
kind: Gateway
metadata:
  name: multi-host-gateway
spec:
  selector:
    istio: ingressgateway
  servers:
  # API subdomain
  - port:
      number: 443
      name: https-api
      protocol: HTTPS
    tls:
      mode: SIMPLE
      credentialName: api-example-com-cert
    hosts:
    - "api.example.com"
  # App subdomain
  - port:
      number: 443
      name: https-app
      protocol: HTTPS
    tls:
      mode: SIMPLE
      credentialName: app-example-com-cert
    hosts:
    - "app.example.com"
  # Admin subdomain with client cert
  - port:
      number: 443
      name: https-admin
      protocol: HTTPS
    tls:
      mode: MUTUAL
      credentialName: admin-example-com-cert
      caCertificates: /etc/istio/admin-ca-cert/ca.crt
    hosts:
    - "admin.example.com"
---
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: api-routes
spec:
  hosts:
  - "api.example.com"
  gateways:
  - multi-host-gateway
  http:
  - route:
    - destination:
        host: api-service
---
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: app-routes
spec:
  hosts:
  - "app.example.com"
  gateways:
  - multi-host-gateway
  http:
  - route:
    - destination:
        host: frontend-service
---
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: admin-routes
spec:
  hosts:
  - "admin.example.com"
  gateways:
  - multi-host-gateway
  http:
  - route:
    - destination:
        host: admin-service
```

### Get Gateway External IP

```bash
# Get LoadBalancer IP/hostname
kubectl get svc istio-ingressgateway -n istio-system

# Test gateway
curl -H "Host: example.com" http://GATEWAY_IP/

# Test HTTPS
curl -k https://secure.example.com/
```

---

## Example 13: Rate Limiting Implementation

### Local Rate Limiting (EnvoyFilter)

```yaml
# ratelimit-local.yaml
apiVersion: networking.istio.io/v1alpha3
kind: EnvoyFilter
metadata:
  name: filter-local-ratelimit-svc
  namespace: default
spec:
  workloadSelector:
    labels:
      app: api-gateway
  configPatches:
  - applyTo: HTTP_FILTER
    match:
      context: SIDECAR_INBOUND
      listener:
        filterChain:
          filter:
            name: "envoy.filters.network.http_connection_manager"
    patch:
      operation: INSERT_BEFORE
      value:
        name: envoy.filters.http.local_ratelimit
        typed_config:
          "@type": type.googleapis.com/udpa.type.v1.TypedStruct
          type_url: type.googleapis.com/envoy.extensions.filters.http.local_ratelimit.v3.LocalRateLimit
          value:
            stat_prefix: http_local_rate_limiter
            token_bucket:
              max_tokens: 100
              tokens_per_fill: 100
              fill_interval: 1s
            filter_enabled:
              runtime_key: local_rate_limit_enabled
              default_value:
                numerator: 100
                denominator: HUNDRED
            filter_enforced:
              runtime_key: local_rate_limit_enforced
              default_value:
                numerator: 100
                denominator: HUNDRED
            response_headers_to_add:
            - append: false
              header:
                key: x-local-rate-limit
                value: 'true'
```

### Per-User Rate Limiting

```yaml
# ratelimit-per-user.yaml
apiVersion: networking.istio.io/v1alpha3
kind: EnvoyFilter
metadata:
  name: filter-ratelimit-per-user
  namespace: default
spec:
  workloadSelector:
    labels:
      app: api-service
  configPatches:
  - applyTo: HTTP_FILTER
    match:
      context: SIDECAR_INBOUND
      listener:
        filterChain:
          filter:
            name: "envoy.filters.network.http_connection_manager"
    patch:
      operation: INSERT_BEFORE
      value:
        name: envoy.filters.http.local_ratelimit
        typed_config:
          "@type": type.googleapis.com/udpa.type.v1.TypedStruct
          type_url: type.googleapis.com/envoy.extensions.filters.http.local_ratelimit.v3.LocalRateLimit
          value:
            stat_prefix: http_local_rate_limiter
            token_bucket:
              max_tokens: 10
              tokens_per_fill: 10
              fill_interval: 60s
            filter_enabled:
              runtime_key: local_rate_limit_enabled
              default_value:
                numerator: 100
                denominator: HUNDRED
            filter_enforced:
              runtime_key: local_rate_limit_enforced
              default_value:
                numerator: 100
                denominator: HUNDRED
            descriptors:
            - entries:
              - key: header_match
                value: user_id
            local_rate_limit_per_downstream_connection: false
```

### Test Rate Limiting

```bash
# Test without rate limiting
for i in {1..200}; do
  curl -s -o /dev/null -w "%{http_code}\n" http://api-service:8080/
done

# Expected: 100x 200, then 100x 429 (Too Many Requests)

# Monitor rate limit stats
kubectl exec api-service-xxx -c istio-proxy -- \
  curl -s localhost:15000/stats | grep local_rate_limit
```

---

## Example 14: Distributed Tracing Setup

### Enable Tracing

```yaml
# telemetry-tracing.yaml
apiVersion: telemetry.istio.io/v1alpha1
kind: Telemetry
metadata:
  name: mesh-tracing
  namespace: istio-system
spec:
  tracing:
  - providers:
    - name: jaeger
    randomSamplingPercentage: 10.0  # 10% sampling
    customTags:
      environment:
        literal:
          value: "production"
      cluster:
        literal:
          value: "us-west-1"
```

### Deploy Jaeger

```bash
# Install Jaeger operator
kubectl create namespace observability
kubectl create -f https://github.com/jaegertracing/jaeger-operator/releases/download/v1.51.0/jaeger-operator.yaml -n observability

# Deploy Jaeger instance
kubectl apply -f - <<EOF
apiVersion: jaegertracing.io/v1
kind: Jaeger
metadata:
  name: jaeger
  namespace: istio-system
spec:
  strategy: production
  storage:
    type: elasticsearch
    options:
      es:
        server-urls: http://elasticsearch:9200
  ingress:
    enabled: true
    hosts:
    - jaeger.example.com
EOF
```

### Application Instrumentation

```python
# Python FastAPI example with trace context propagation
from fastapi import FastAPI, Request
import httpx
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

app = FastAPI()

# Configure tracing
trace.set_tracer_provider(TracerProvider())
jaeger_exporter = JaegerExporter(
    agent_host_name="localhost",
    agent_port=6831,
)
trace.get_tracer_provider().add_span_processor(
    BatchSpanProcessor(jaeger_exporter)
)

# Auto-instrument FastAPI
FastAPIInstrumentor.instrument_app(app)

@app.get("/api/orders/{order_id}")
async def get_order(order_id: str, request: Request):
    tracer = trace.get_tracer(__name__)

    # Create custom span
    with tracer.start_as_current_span("fetch-order-details") as span:
        span.set_attribute("order.id", order_id)

        # Call another service (propagates trace context)
        async with httpx.AsyncClient() as client:
            # Extract trace context from incoming request
            headers = dict(request.headers)

            response = await client.get(
                f"http://payment-service:8080/payments/{order_id}",
                headers=headers  # Propagate trace context
            )

        return {"order_id": order_id, "payment": response.json()}
```

### View Traces

```bash
# Port forward Jaeger UI
kubectl port-forward -n istio-system svc/jaeger-query 16686:16686

# Open browser
open http://localhost:16686

# Query traces
# - Service: product-service
# - Operation: all
# - Lookback: Last hour
# - Limit: 20
```

### Analyze Trace Data

```bash
# Get trace statistics
kubectl exec -n istio-system jaeger-xxx -- \
  curl -s "http://localhost:16686/api/traces?service=product-service&limit=100" | \
  jq '.data[] | {traceID, duration: .spans[0].duration}'

# Find slow traces (>1s)
kubectl exec -n istio-system jaeger-xxx -- \
  curl -s "http://localhost:16686/api/traces?service=product-service&minDuration=1000000" | \
  jq '.data[] | {traceID, duration: .spans[0].duration, operation: .spans[0].operationName}'
```

---

## Example 15: Multi-Cluster Service Mesh

### Primary-Remote Cluster Setup

**On Primary Cluster:**

```bash
# Set cluster context
kubectl config use-context primary-cluster

# Install Istio with multi-cluster configuration
cat <<EOF | istioctl install -y -f -
apiVersion: install.istio.io/v1alpha1
kind: IstioOperator
spec:
  values:
    global:
      meshID: mesh1
      multiCluster:
        clusterName: primary
      network: network1
EOF

# Install east-west gateway
samples/multicluster/gen-eastwest-gateway.sh \
    --mesh mesh1 --cluster primary --network network1 | \
    istioctl install -y -f -

# Expose control plane
kubectl apply -f samples/multicluster/expose-istiod.yaml

# Expose services
kubectl apply -n istio-system -f samples/multicluster/expose-services.yaml
```

**On Remote Cluster:**

```bash
# Set cluster context
kubectl config use-context remote-cluster

# Create remote secret on primary
istioctl x create-remote-secret \
    --context=remote-cluster \
    --name=remote | \
    kubectl apply -f - --context=primary-cluster

# Install Istio in remote cluster
cat <<EOF | istioctl install -y -f -
apiVersion: install.istio.io/v1alpha1
kind: IstioOperator
spec:
  values:
    global:
      meshID: mesh1
      multiCluster:
        clusterName: remote
      network: network1
      remotePilotAddress: ${ISTIOD_REMOTE_EP}
EOF
```

### Deploy Service Across Clusters

```yaml
# product-service-multicluster.yaml
# Deploy in both clusters
apiVersion: v1
kind: Service
metadata:
  name: product-service
  labels:
    app: product
spec:
  ports:
  - port: 8080
    name: http
  selector:
    app: product
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: product
spec:
  replicas: 2
  selector:
    matchLabels:
      app: product
  template:
    metadata:
      labels:
        app: product
    spec:
      containers:
      - name: product
        image: product-service:v1
        ports:
        - containerPort: 8080
```

### Cross-Cluster Traffic Management

```yaml
# virtualservice-multicluster.yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: product-multicluster
spec:
  hosts:
  - product-service
  http:
  - route:
    - destination:
        host: product-service
        port:
          number: 8080
      weight: 50  # 50% to primary cluster
    - destination:
        host: product-service.remote.global
        port:
          number: 8080
      weight: 50  # 50% to remote cluster
```

### Verify Multi-Cluster Setup

```bash
# From primary cluster, check endpoints
istioctl proxy-config endpoints product-xxx | grep product-service

# Should show endpoints from both clusters

# Test cross-cluster communication
kubectl exec -it product-xxx -- curl product-service:8080

# Monitor cross-cluster traffic
kubectl logs -l app=product -c istio-proxy --tail=100
```

---

## Example 16: Service Mesh Federation

### Setup Federation Between Meshes

**Mesh A Configuration:**

```yaml
# mesh-a-federation.yaml
apiVersion: networking.istio.io/v1alpha3
kind: ServiceEntry
metadata:
  name: mesh-b-services
spec:
  hosts:
  - "*.mesh-b.global"
  location: MESH_EXTERNAL
  ports:
  - number: 443
    name: tls
    protocol: TLS
  resolution: DNS
  endpoints:
  - address: istio-ingressgateway.mesh-b.svc.cluster.local
    ports:
      tls: 15443
```

**Mesh B Configuration:**

```yaml
# mesh-b-federation.yaml
apiVersion: networking.istio.io/v1alpha3
kind: Gateway
metadata:
  name: mesh-b-gateway
spec:
  selector:
    istio: ingressgateway
  servers:
  - port:
      number: 15443
      name: tls
      protocol: TLS
    tls:
      mode: AUTO_PASSTHROUGH
    hosts:
    - "*.mesh-b.global"
---
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: mesh-b-services
spec:
  hosts:
  - "payment-service.mesh-b.global"
  gateways:
  - mesh-b-gateway
  tls:
  - match:
    - sniHosts:
      - "payment-service.mesh-b.global"
    route:
    - destination:
        host: payment-service.default.svc.cluster.local
```

---

## Example 17: Observability with Kiali

### Configure Kiali

```yaml
# kiali-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: kiali
  namespace: istio-system
data:
  config.yaml: |
    auth:
      strategy: anonymous
    deployment:
      accessible_namespaces:
      - '**'
    external_services:
      prometheus:
        url: http://prometheus:9090
      grafana:
        url: http://grafana:3000
      tracing:
        enabled: true
        in_cluster_url: http://tracing.istio-system:16686
        url: http://jaeger.example.com
    server:
      web_root: /kiali
```

### Access Kiali Dashboard

```bash
# Port forward Kiali
kubectl port-forward svc/kiali -n istio-system 20001:20001

# Open browser
open http://localhost:20001

# Or expose via LoadBalancer
kubectl patch svc kiali -n istio-system -p '{"spec":{"type":"LoadBalancer"}}'
```

### Generate Traffic for Visualization

```bash
# Install test application (Bookinfo)
kubectl apply -f samples/bookinfo/platform/kube/bookinfo.yaml
kubectl apply -f samples/bookinfo/networking/bookinfo-gateway.yaml

# Generate load
for i in {1..1000}; do
  curl -s http://GATEWAY_IP/productpage > /dev/null
  sleep 0.5
done
```

---

## Example 18: Advanced Traffic Management

### Weighted Routing with Headers

```yaml
# advanced-routing.yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: advanced-product-routing
spec:
  hosts:
  - product-service
  http:
  # Internal testing - route to v3
  - match:
    - headers:
        x-internal-test:
          exact: "true"
    route:
    - destination:
        host: product-service
        subset: v3
      weight: 100
  # Premium users - 50% to v2
  - match:
    - headers:
        user-tier:
          exact: "premium"
    route:
    - destination:
        host: product-service
        subset: v2
      weight: 50
    - destination:
        host: product-service
        subset: v1
      weight: 50
  # Default - mostly v1
  - route:
    - destination:
        host: product-service
        subset: v1
      weight: 95
    - destination:
        host: product-service
        subset: v2
      weight: 5
```

---

## Example 19: Saga Pattern Implementation

### Orchestration-Based Saga

```yaml
# saga-orchestrator.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-saga-orchestrator
spec:
  replicas: 2
  selector:
    matchLabels:
      app: order-saga
  template:
    metadata:
      labels:
        app: order-saga
    spec:
      containers:
      - name: orchestrator
        image: order-saga-orchestrator:v1
        env:
        - name: INVENTORY_SERVICE_URL
          value: "http://inventory-service:8080"
        - name: PAYMENT_SERVICE_URL
          value: "http://payment-service:8080"
        - name: SHIPPING_SERVICE_URL
          value: "http://shipping-service:8080"
```

### Saga Virtual Services with Compensation

```yaml
# saga-virtualservices.yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: inventory-saga
spec:
  hosts:
  - inventory-service
  http:
  - match:
    - headers:
        x-saga-id:
          regex: ".*"
    route:
    - destination:
        host: inventory-service
    timeout: 5s
    retries:
      attempts: 3
      perTryTimeout: 2s
      retryOn: 5xx,reset
```

---

## Example 20: API Gateway Pattern

### Complete API Gateway Implementation

```yaml
# api-gateway-complete.yaml
apiVersion: networking.istio.io/v1beta1
kind: Gateway
metadata:
  name: api-gateway
spec:
  selector:
    istio: ingressgateway
  servers:
  - port:
      number: 443
      name: https
      protocol: HTTPS
    tls:
      mode: SIMPLE
      credentialName: api-cert
    hosts:
    - "api.example.com"
---
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: api-routes
spec:
  hosts:
  - "api.example.com"
  gateways:
  - api-gateway
  http:
  # Rate limit all endpoints
  - match:
    - uri:
        prefix: /api/
    route:
    - destination:
        host: api-aggregator
    timeout: 30s
    retries:
      attempts: 3
      perTryTimeout: 10s
      retryOn: 5xx
    corsPolicy:
      allowOrigins:
      - exact: "https://app.example.com"
      allowMethods:
      - GET
      - POST
      - PUT
      - DELETE
      allowHeaders:
      - authorization
      - content-type
      maxAge: 24h
---
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: api-gateway-authz
spec:
  selector:
    matchLabels:
      app: api-aggregator
  action: ALLOW
  rules:
  - from:
    - source:
        requestPrincipals: ["*"]
    to:
    - operation:
        paths: ["/api/*"]
```

---

## Summary

These 20 comprehensive examples cover the most important microservices patterns with Istio:

1. **Installation & Configuration** - Complete Istio setup
2. **Basic Deployment** - Service with sidecar injection
3. **Virtual Services** - Intelligent routing
4. **Destination Rules** - Load balancing strategies
5. **Circuit Breakers** - Fault tolerance
6. **Retry & Timeout** - Resilience policies
7. **Canary Deployment** - Progressive rollout
8. **Blue-Green** - Zero-downtime deployment
9. **Fault Injection** - Chaos engineering
10. **mTLS** - Security configuration
11. **Authorization** - Access control
12. **Gateway** - Ingress management
13. **Rate Limiting** - Traffic control
14. **Distributed Tracing** - Observability
15. **Multi-Cluster** - Cross-cluster mesh
16. **Federation** - Mesh interconnection
17. **Kiali** - Visualization
18. **Advanced Routing** - Complex traffic patterns
19. **Saga Pattern** - Distributed transactions
20. **API Gateway** - Complete gateway implementation

Each example is production-ready and includes deployment, configuration, testing, and monitoring steps.

---

**Version**: 1.0.0
**Last Updated**: October 2025
