---
name: api-designer
description: Design, document, and implement RESTful/GraphQL APIs with best practices. Use when: (1) creating new API endpoints, (2) designing API architecture, (3) generating OpenAPI/Swagger docs, (4) implementing authentication middleware, (5) building API mock servers, (6) optimizing API performance, (7) versioning APIs, (8) handling rate limiting and caching. Triggers: "design API", "create endpoint", "OpenAPI", "Swagger", "REST API", "GraphQL schema", "API documentation".
---

# API Designer

Professional API design, implementation, and documentation for production-grade services.

## Core Workflow

### 1. Design Phase

```bash
# Define API structure
- Resource modeling
- Endpoint naming (RESTful conventions)
- HTTP methods mapping
- Request/Response schemas
- Error handling strategy
```

### 2. Implementation Phase

```bash
# Framework-agnostic patterns
Express/Fastify (Node.js)
FastAPI (Python)
Gin/Echo (Go)
Spring Boot (Java)
```

### 3. Documentation Phase

```bash
# Generate OpenAPI 3.0+ specs
- Automatic schema generation
- Interactive docs (Swagger UI / ReDoc)
- Client SDK generation
```

## RESTful Best Practices

### Resource Naming

```
# Good - Nouns, plural, hierarchical
GET    /users                    # List users
GET    /users/{id}               # Get user
POST   /users                    # Create user
PUT    /users/{id}               # Update user
DELETE /users/{id}               # Delete user
GET    /users/{id}/orders        # User's orders

# Bad - Verbs, singular, inconsistent
GET    /getUser
POST   /createNewUser
GET    /user_order
```

### HTTP Status Codes

```
200 OK          - Successful GET/PUT/PATCH
201 Created     - Successful POST
204 No Content  - Successful DELETE
400 Bad Request - Invalid input
401 Unauthorized - Missing/invalid auth
403 Forbidden   - Insufficient permissions
404 Not Found   - Resource doesn't exist
409 Conflict    - Duplicate resource
422 Unprocessable - Validation error
429 Too Many Requests - Rate limited
500 Internal Server Error - Server failure
```

### Response Format

```json
// Success
{
  "data": { ... },
  "meta": {
    "page": 1,
    "limit": 20,
    "total": 100
  }
}

// Error
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Email is required",
    "details": [...]
  }
}
```

## Authentication Patterns

### JWT Implementation

```javascript
// Middleware
const authMiddleware = (req, res, next) => {
  const token = req.headers.authorization?.split(' ')[1];
  if (!token) return res.status(401).json({ error: 'No token' });
  
  try {
    req.user = jwt.verify(token, process.env.JWT_SECRET);
    next();
  } catch (err) {
    res.status(401).json({ error: 'Invalid token' });
  }
};
```

### API Key

```javascript
const apiKeyMiddleware = (req, res, next) => {
  const apiKey = req.headers['x-api-key'];
  if (!apiKey || !validateApiKey(apiKey)) {
    return res.status(401).json({ error: 'Invalid API key' });
  }
  next();
};
```

## Rate Limiting

```javascript
// Express + rate-limit
const rateLimit = require('express-rate-limit');

const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100, // limit each IP to 100 requests
  message: { error: 'Too many requests' }
});

app.use('/api/', limiter);
```

## Pagination

```javascript
// Cursor-based (recommended for large datasets)
GET /users?cursor=abc123&limit=20

// Offset-based (simple but can miss data)
GET /users?page=2&limit=20

// Response
{
  "data": [...],
  "pagination": {
    "next_cursor": "def456",
    "has_more": true
  }
}
```

## Versioning Strategies

```
# URL path (recommended)
/api/v1/users
/api/v2/users

# Header
GET /users
Accept: application/vnd.api+json;version=1

# Query param
GET /users?version=1
```

## Scripts

- `scripts/generate_openapi.js` - Auto-generate OpenAPI spec from code
- `scripts/mock_server.js` - Start mock API server from OpenAPI spec
- `scripts/validate_spec.js` - Validate OpenAPI specification

## References

- `references/openapi_template.yaml` - OpenAPI 3.0 boilerplate
- `references/error_codes.md` - Standard error code reference
- `references/security_schemes.md` - Auth patterns (OAuth2, JWT, API Key)
