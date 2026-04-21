# Modern Software Architecture Patterns 

Comprehensive guide to contemporary architecture patterns based on  industry trends and practices.

## Top Architecture Patterns

### 1. Microservices Architecture

**When to use**:
- Multiple independent teams
- Need independent deployment and scaling
- Different technologies for different services
- Clear bounded contexts

**Structure**:
```
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│   Service   │  │   Service   │  │   Service   │
│     A       │  │      B      │  │      C      │
│  (Node.js)  │  │   (Python)  │  │    (Go)     │
└─────────────┘  └─────────────┘  └─────────────┘
      │                 │                 │
      └─────────────────┴─────────────────┘
                       │
              ┌────────▼────────┐
              │  API Gateway    │
              │  (Kong/Nginx)   │
              └─────────────────┘
```

**Best practices**:
- **Service discovery**: Use Consul, Eureka, or Kubernetes DNS
- **API Gateway**: Single entry point, authentication, rate limiting
- **Communication**: REST for synchronous, message queues for async
- **Data**: Each service owns its database (no shared DB)
- **Deployment**: Containerization (Docker) + orchestration (Kubernetes)

**Challenges**:
- Distributed system complexity
- Network latency and failures
- Data consistency across services
- Testing and debugging
- Operational overhead

**Mitigation**:
```yaml
# Service mesh (Istio/Linkerd) for:
- Service-to-service authentication
- Load balancing
- Circuit breaking
- Distributed tracing
- Metrics collection
```

### 2. Event-Driven Architecture (EDA)

**When to use**:
- Real-time data processing
- Asynchronous workflows
- Decoupled systems
- High scalability requirements

**Structure**:
```
┌──────────┐       ┌──────────────┐       ┌──────────┐
│ Producer │──────▶│ Event Broker │──────▶│ Consumer │
│          │       │ (Kafka/RabbitMQ)     │          │
└──────────┘       └──────────────┘       └──────────┘
                          │
                          ├──────▶ Consumer 2
                          └──────▶ Consumer 3
```

**Event patterns**:

**Event Notification**:
```json
{
  "eventType": "OrderPlaced",
  "orderId": "12345",
  "timestamp": "2023-06-15T10:30:00Z"
}
```

**Event-Carried State Transfer**:
```json
{
  "eventType": "OrderPlaced",
  "orderId": "12345",
  "customer": {"id": "C123", "name": "John"},
  "items": [{"id": "P456", "qty": 2}],
  "total": 99.99,
  "timestamp": "2023-06-15T10:30:00Z"
}
```

**Event Sourcing**:
```json
[
  {"event": "OrderCreated", "orderId": "12345", "seq": 1},
  {"event": "ItemAdded", "orderId": "12345", "itemId": "P456", "seq": 2},
  {"event": "OrderPaid", "orderId": "12345", "amount": 99.99, "seq": 3}
]
```

**Best practices**:
- **Idempotency**: Handle duplicate events gracefully
- **Schema evolution**: Use versioned event schemas
- **Error handling**: Dead letter queues for failed events
- **Monitoring**: Track event lag and processing times
- **Ordering**: Use partition keys for ordered processing

**Tools**:
- Apache Kafka - High-throughput distributed streaming
- RabbitMQ - Flexible message broker
- AWS EventBridge - Serverless event bus
- Google Pub/Sub - Global messaging service

### 3. Serverless Architecture

**When to use**:
- Variable/unpredictable load
- Event-driven workloads
- Rapid development and deployment
- Cost optimization (pay per use)

**Structure**:
```
┌─────────┐      ┌──────────────┐      ┌─────────┐
│  Event  │─────▶│   Function   │─────▶│  Store  │
│ Source  │      │ (Lambda/CF)  │      │ (DynamoDB)
└─────────┘      └──────────────┘      └─────────┘

Event Sources:
- API Gateway (HTTP)
- S3 (file upload)
- DynamoDB Streams
- EventBridge (scheduled)
- SQS/SNS (messaging)
```

**Best practices**:
- **Cold start mitigation**: Keep functions warm with provisioned concurrency
- **Stateless design**: Use external state stores (Redis, DynamoDB)
- **Granular functions**: Single responsibility (≤300 LOC)
- **Resource limits**: Configure memory and timeout appropriately
- **Observability**: Use X-Ray, CloudWatch, or DataDog

**Example - AWS Lambda**:
```javascript
// Optimized function structure
export const handler = async (event) => {
  // Input validation
  const { userId, action } = JSON.parse(event.body);

  // Business logic
  const result = await processUserAction(userId, action);

  // Response
  return {
    statusCode: 200,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(result)
  };
};

// Keep external connections alive (outside handler)
const db = initDatabase();
```

**Cost optimization**:
- Use ARM-based functions (Graviton) - 20% cheaper
- Right-size memory allocation
- Use step functions for orchestration
- Implement caching to reduce invocations

### 4. Layered (N-Tier) Architecture

**When to use**:
- Monolithic applications
- Clear separation of concerns needed
- Team familiar with traditional patterns
- Moderate complexity

**Classic layers**:
```
┌──────────────────────────┐
│  Presentation Layer      │  ← Controllers, Views, API endpoints
├──────────────────────────┤
│  Business Logic Layer    │  ← Services, Domain models
├──────────────────────────┤
│  Data Access Layer       │  ← Repositories, ORM
├──────────────────────────┤
│  Database Layer          │  ← PostgreSQL, MongoDB
└──────────────────────────┘
```

**Dependency rule**: Outer layers depend on inner layers only

**Example structure**:
```
src/
├── controllers/          # HTTP request handlers
│   └── userController.js
├── services/            # Business logic
│   └── userService.js
├── repositories/        # Data access
│   └── userRepository.js
├── models/              # Domain models
│   └── user.js
└── database/            # DB configuration
    └── connection.js
```

**Best practices**:
- **Dependency injection**: Pass dependencies, don't hardcode
- **Interface segregation**: Define clear contracts between layers
- **Error propagation**: Handle errors at appropriate layer
- **Transaction management**: Handle at service layer

### 5. Hexagonal Architecture (Ports & Adapters)

**When to use**:
- Need high testability
- Multiple interfaces (REST, GraphQL, CLI)
- Business logic must be technology-agnostic
- Long-term maintainability priority

**Structure**:
```
        ┌─────────────────────────┐
        │   Application Core      │
        │   (Business Logic)      │
        │                         │
        │  ┌─────────────────┐    │
        │  │  Domain Model   │    │
        │  └─────────────────┘    │
        └────────┬──────┬──────────┘
                 │      │
    ┌────────────┘      └────────────┐
    │                                 │
┌───▼──────┐                   ┌─────▼────┐
│  Ports   │                   │  Ports   │
│ (Input)  │                   │ (Output) │
└───┬──────┘                   └─────┬────┘
    │                                 │
┌───▼──────────┐             ┌────────▼─────┐
│   Adapters   │             │   Adapters   │
│ REST, GraphQL│             │ DB, External │
└──────────────┘             └──────────────┘
```

**Implementation**:
```typescript
// Core domain (technology-agnostic)
interface UserRepository {
  findById(id: string): Promise<User>;
  save(user: User): Promise<void>;
}

class UserService {
  constructor(private userRepo: UserRepository) {}

  async activateUser(id: string): Promise<User> {
    const user = await this.userRepo.findById(id);
    user.activate();  // Business logic
    await this.userRepo.save(user);
    return user;
  }
}

// Adapters (technology-specific)
class PostgresUserRepository implements UserRepository {
  async findById(id: string): Promise<User> {
    const row = await db.query('SELECT * FROM users WHERE id = $1', [id]);
    return User.fromDatabase(row);
  }

  async save(user: User): Promise<void> {
    await db.query('UPDATE users SET ...', user.toDatabase());
  }
}

class RestAdapter {
  constructor(private userService: UserService) {}

  async handleActivateUser(req, res) {
    const user = await this.userService.activateUser(req.params.id);
    res.json(user);
  }
}
```

### 6. CQRS (Command Query Responsibility Segregation)

**When to use**:
- Read and write patterns are very different
- High read:write ratio
- Complex reporting requirements
- Need independent scaling of reads and writes

**Structure**:
```
           ┌─────────────┐
           │   Command   │
           │   (Write)   │
           └──────┬──────┘
                  │
        ┌─────────▼──────────┐
        │  Write Database    │
        │  (Normalized)      │
        └─────────┬──────────┘
                  │ (sync/async)
        ┌─────────▼──────────┐
        │   Read Database    │
        │  (Denormalized)    │
        └─────────┬──────────┘
                  │
           ┌──────▼──────┐
           │    Query    │
           │    (Read)   │
           └─────────────┘
```

**Example**:
```typescript
// Command (Write)
class CreateOrderCommand {
  constructor(
    public customerId: string,
    public items: OrderItem[]
  ) {}
}

class OrderCommandHandler {
  async handle(cmd: CreateOrderCommand) {
    const order = new Order(cmd.customerId, cmd.items);
    await writeDb.orders.save(order);

    // Publish event for read model update
    await eventBus.publish(new OrderCreatedEvent(order));
  }
}

// Query (Read)
class GetCustomerOrdersQuery {
  constructor(public customerId: string) {}
}

class OrderQueryHandler {
  async handle(query: GetCustomerOrdersQuery) {
    // Read from optimized read model
    return await readDb.customerOrders.find({
      customerId: query.customerId
    });
  }
}

// Event handler to sync read model
class OrderCreatedEventHandler {
  async handle(event: OrderCreatedEvent) {
    // Update denormalized read model
    await readDb.customerOrders.insert({
      customerId: event.customerId,
      orderId: event.orderId,
      total: event.total,
      // ... optimized for reads
    });
  }
}
```

### 7. Modular Monolith

**When to use**:
- Team size 5-30 developers
- Want clear boundaries without microservices overhead
- Need faster development than microservices
- Shared domain concepts across modules

**Structure**:
```
monolith/
├── modules/
│   ├── orders/
│   │   ├── api/          # Public interface
│   │   ├── domain/       # Business logic (private)
│   │   └── infrastructure/ # DB, external services (private)
│   ├── payments/
│   │   ├── api/
│   │   ├── domain/
│   │   └── infrastructure/
│   └── shipping/
│       ├── api/
│       ├── domain/
│       └── infrastructure/
└── shared/
    ├── database/
    └── messaging/
```

**Module boundaries**:
```typescript
// orders/api/OrdersModule.ts (public API)
export class OrdersModule {
  static async createOrder(data: CreateOrderDTO): Promise<Order> {
    // Implementation hidden
  }

  static async getOrder(id: string): Promise<Order> {
    // Implementation hidden
  }
}

// payments/PaymentsService.ts
import { OrdersModule } from '../orders/api/OrdersModule';

class PaymentsService {
  async processPayment(orderId: string) {
    // Use public API only, no direct access to orders internals
    const order = await OrdersModule.getOrder(orderId);
    // ...
  }
}
```

**Advantages over microservices**:
- Single deployment (simpler CI/CD)
- No network latency between modules
- Shared transactions possible
- Easier refactoring (can extract to microservice later)

### 8. Micro-Frontend Architecture

**When to use**:
- Multiple teams working on different features
- Different technology stacks for different parts
- Independent deployment of UI components
- Large-scale front-end applications

**Approaches**:

**A) Server-side composition (SSR)**:
```nginx
# Nginx routes different paths to different apps
location /products {
  proxy_pass http://products-frontend:3000;
}
location /checkout {
  proxy_pass http://checkout-frontend:3001;
}
```

**B) Build-time composition (Module Federation)**:
```javascript
// Webpack Module Federation
module.exports = {
  plugins: [
    new ModuleFederationPlugin({
      name: 'products',
      filename: 'remoteEntry.js',
      exposes: {
        './ProductList': './src/components/ProductList'
      },
      shared: ['react', 'react-dom']
    })
  ]
};

// Host app imports remote component
const ProductList = React.lazy(() => import('products/ProductList'));
```

**C) Runtime composition (Single-SPA)**:
```javascript
import { registerApplication, start } from 'single-spa';

registerApplication({
  name: 'products',
  app: () => import('./products/main.js'),
  activeWhen: location => location.pathname.startsWith('/products')
});

registerApplication({
  name: 'checkout',
  app: () => import('./checkout/main.js'),
  activeWhen: '/checkout'
});

start();
```

### 9. Service Mesh Architecture

**When to use**:
- Microservices at scale (10+ services)
- Need advanced traffic management
- Security and observability are critical
- Polyglot microservices

**Structure**:
```
Service A ──▶ Sidecar Proxy (Envoy)
               │                    ──▶ Sidecar Proxy ──▶ Service B
               └─ Control Plane (Istio)
                      │
                      ├─ Traffic management
                      ├─ Security (mTLS)
                      └─ Observability
```

**Features**:
- **Traffic management**: Load balancing, circuit breaking, retries
- **Security**: Mutual TLS, authorization policies
- **Observability**: Distributed tracing, metrics, logging

**Example - Istio**:
```yaml
# Virtual Service (traffic routing)
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: reviews
spec:
  hosts:
    - reviews
  http:
  - match:
    - headers:
        user-agent:
          regex: '.*Chrome.*'
    route:
    - destination:
        host: reviews
        subset: v2
  - route:
    - destination:
        host: reviews
        subset: v1

# Circuit breaker
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: reviews
spec:
  host: reviews
  trafficPolicy:
    connectionPool:
      tcp:
        maxConnections: 100
      http:
        http1MaxPendingRequests: 1
        maxRequestsPerConnection: 2
    outlierDetection:
      consecutive5xxErrors: 5
      interval: 30s
      baseEjectionTime: 30s
```

### 10. Edge Computing Architecture

**When to use**:
- Need ultra-low latency
- IoT applications
- Content delivery
- Real-time processing

**Structure**:
```
┌─────────────────────────────────────────┐
│         Cloud (Central)                 │
│  - Data aggregation                     │
│  - ML model training                    │
│  - Long-term storage                    │
└────────────┬────────────────────────────┘
             │
    ┌────────┴────────┐
    │                 │
┌───▼──────┐    ┌─────▼────┐
│  Edge    │    │  Edge    │
│  Node 1  │    │  Node 2  │
│ - Process│    │ - Process│
│ - Cache  │    │ - Cache  │
│ - Filter │    │ - Filter │
└───┬──────┘    └─────┬────┘
    │                 │
┌───▼──┐          ┌───▼──┐
│  IoT │          │  IoT │
│Device│          │Device│
└──────┘          └──────┘
```

**Use cases**:
- CDN edge workers (Cloudflare Workers, Lambda@Edge)
- Smart city sensors
- Industrial IoT
- Autonomous vehicles

**Example - Cloudflare Worker**:
```javascript
addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request));
});

async function handleRequest(request) {
  // Process at edge (near user)
  const cache = caches.default;
  let response = await cache.match(request);

  if (!response) {
    // Fetch from origin if not cached
    response = await fetch(request);
    // Cache at edge
    event.waitUntil(cache.put(request, response.clone()));
  }

  return response;
}
```

## Architecture Selection Decision Tree

```
Start: What are you building?

├─ Simple CRUD app
│  └─ Use: Layered Architecture
│
├─ Need independent team scaling?
│  ├─ Yes → Need independent deployments?
│  │  ├─ Yes → Use: Microservices
│  │  └─ No → Use: Modular Monolith
│  └─ No → Use: Layered or Hexagonal
│
├─ Event-driven requirements?
│  ├─ Primary pattern → Use: Event-Driven Architecture
│  └─ Secondary pattern → Add messaging to chosen architecture
│
├─ Unpredictable/variable load?
│  └─ Use: Serverless
│
├─ Different read/write patterns?
│  └─ Use: CQRS + Event Sourcing
│
└─ Multiple UI teams?
   └─ Use: Micro-Frontends
```

## Anti-Patterns to Avoid

### 1. Distributed Monolith
Microservices that are tightly coupled:
```
[FAIL] Service A calls Service B, which calls Service C, which calls Service A
[OK] Use message queues or events to decouple
```

### 2. God Service
One service that does everything:
```
[FAIL] UserOrderPaymentShippingService
[OK] UserService, OrderService, PaymentService, ShippingService
```

### 3. Anemic Domain Model
Models with no behavior, just getters/setters:
```typescript
[FAIL] // Anemic
class Order {
  items: OrderItem[];
  getItems() { return this.items; }
  setItems(items) { this.items = items; }
}

[OK] // Rich domain model
class Order {
  private items: OrderItem[];

  addItem(item: OrderItem) {
    this.validateItem(item);
    this.items.push(item);
    this.recalculateTotal();
  }

  canBeCancelled(): boolean {
    return this.status === 'pending' && !this.isPaid;
  }
}
```

### 4. Chatty APIs
Too many network calls:
```
[FAIL] GET /users/1, GET /users/1/orders, GET /orders/1/items
[OK] GET /users/1?include=orders.items
```

## Resources

- Martin Fowler - Architecture Patterns
- Microsoft Azure - Architecture Center
- AWS - Well-Architected Framework
- Google Cloud - Architecture Framework
- Microservices.io - Pattern catalog
