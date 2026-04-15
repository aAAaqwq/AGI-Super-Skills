# PostgreSQL Database Engineering

Master professional PostgreSQL database engineering with comprehensive coverage of performance optimization, high availability, replication, and production database management.

## Overview

PostgreSQL is the world's most advanced open-source relational database, powering applications from startups to Fortune 500 companies. This skill equips you with expert-level knowledge to design, optimize, and maintain high-performance PostgreSQL databases at scale.

**What You'll Master:**
- Query optimization and EXPLAIN plan analysis
- Advanced indexing strategies (B-tree, GIN, GiST, BRIN)
- Table partitioning for large datasets
- Streaming and logical replication
- High availability and failover
- Performance tuning and configuration
- Connection pooling and resource management
- Backup and recovery procedures
- VACUUM and maintenance operations
- Monitoring and troubleshooting

## Why PostgreSQL?

**Technical Excellence:**
- Full ACID compliance with true transaction isolation
- MVCC for high concurrency without read locks
- Rich data types: JSON, arrays, ranges, custom types
- Extensible architecture with custom functions and extensions
- Advanced features: CTEs, window functions, full-text search
- Robust ecosystem: PostGIS, TimescaleDB, Citus

**Production-Ready:**
- Battle-tested for 25+ years
- Zero-downtime upgrades and migrations
- Enterprise-grade security and auditing
- Horizontal and vertical scalability
- Active community and commercial support
- Cloud-native (AWS RDS, Azure PostgreSQL, Google Cloud SQL)

**Use Cases:**
- Web applications (Django, Rails, Node.js)
- Analytics and data warehousing
- Geospatial applications (PostGIS)
- Time-series data (TimescaleDB)
- Multi-tenant SaaS platforms
- Financial systems requiring ACID guarantees
- Real-time applications with logical replication

## Installation and Setup

### Linux (Ubuntu/Debian)

```bash
# Add PostgreSQL repository
sudo sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -

# Update and install
sudo apt-get update
sudo apt-get install postgresql-15 postgresql-contrib-15

# Start PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Access PostgreSQL
sudo -u postgres psql
```

### macOS

```bash
# Using Homebrew
brew install postgresql@15

# Start PostgreSQL
brew services start postgresql@15

# Access PostgreSQL
psql postgres
```

### Docker

```bash
# Run PostgreSQL container
docker run -d \
    --name postgres \
    -e POSTGRES_PASSWORD=secure_password \
    -e POSTGRES_DB=mydb \
    -v pgdata:/var/lib/postgresql/data \
    -p 5432:5432 \
    postgres:15

# Access PostgreSQL
docker exec -it postgres psql -U postgres -d mydb
```

### Initial Configuration

```bash
# Locate configuration files
sudo -u postgres psql -c "SHOW config_file;"
sudo -u postgres psql -c "SHOW hba_file;"
sudo -u postgres psql -c "SHOW data_directory;"

# Edit postgresql.conf
sudo nano /etc/postgresql/15/main/postgresql.conf

# Edit pg_hba.conf for authentication
sudo nano /etc/postgresql/15/main/pg_hba.conf

# Reload configuration
sudo systemctl reload postgresql
```

## Core PostgreSQL Concepts

### MVCC Architecture

PostgreSQL's Multi-Version Concurrency Control is fundamental to understanding its behavior:

**How MVCC Works:**
- Each row has hidden columns: `xmin` (creating transaction) and `xmax` (deleting transaction)
- Transactions see a snapshot of the database at transaction start
- Updates create new row versions rather than modifying in place
- Old row versions remain until VACUUM removes them
- No read locks needed - readers never block writers

**Implications:**
- High concurrency with minimal locking
- Dead tuples accumulate after updates/deletes
- Regular VACUUM is essential for performance
- Table and index bloat if VACUUM doesn't keep up
- Long-running transactions prevent VACUUM cleanup

**Transaction Isolation:**
- Read Committed: See changes from committed transactions (default)
- Repeatable Read: See snapshot from transaction start
- Serializable: Full serializable isolation with SSI

### Storage and TOAST

**Storage Organization:**
- Tables stored in 8KB pages
- Tuples (rows) stored within pages
- Free Space Map (FSM) tracks available space
- Visibility Map (VM) tracks pages with all visible tuples

**TOAST (The Oversized-Attribute Storage Technique):**
- Automatically manages large column values
- Compresses large values in-line
- Stores very large values in separate TOAST table
- Transparent to applications
- Strategies: PLAIN, EXTENDED, EXTERNAL, MAIN

### Write-Ahead Logging (WAL)

**Purpose:**
- Durability guarantee for committed transactions
- Point-in-time recovery (PITR)
- Streaming replication data source
- Crash recovery mechanism

**WAL Process:**
1. Transaction makes changes in shared buffers
2. WAL records written to WAL buffers
3. WAL flushed to disk at commit (fsync)
4. Checkpoint periodically writes dirty pages to disk
5. Old WAL files archived or recycled

**Configuration:**
- `wal_level`: minimal, replica, logical
- `max_wal_size`: WAL size before checkpoint
- `checkpoint_timeout`: Time between checkpoints
- `archive_mode`: Enable WAL archiving
- `archive_command`: Command to archive WAL files

## Performance Fundamentals

### Query Execution Pipeline

1. **Parsing**: SQL text parsed into parse tree
2. **Rewriting**: Apply rules and views
3. **Planning**: Generate optimal execution plan
4. **Optimization**: Cost-based query optimization
5. **Execution**: Execute plan and return results

**Planner Statistics:**
- Table row counts and page counts
- Column statistics (n_distinct, correlation, MCV, histogram)
- Collected by ANALYZE
- Used for cardinality estimation
- Critical for optimal query plans

### Index Performance

**Index Selection Criteria:**
- Query selectivity (how many rows match)
- Index size vs table size
- Random I/O cost vs sequential scan
- Index maintenance overhead

**When Indexes Aren't Used:**
- Query returns large percentage of table
- Statistics are stale
- Type mismatch between query and column
- Function applied to indexed column
- OR conditions (use IN instead)

**Index Maintenance:**
- Indexes grow larger than tables with MVCC
- Dead tuple space in indexes
- Periodic REINDEX or REINDEX CONCURRENTLY
- Monitor with pg_stat_user_indexes

### Buffer Cache and I/O

**Shared Buffers:**
- PostgreSQL's internal page cache
- Typically 25% of RAM
- Stores frequently accessed pages
- LRU eviction policy

**Effective Cache Size:**
- Tells planner about OS cache + shared buffers
- Typically 50-75% of RAM
- Influences query plan costs
- Doesn't allocate memory

**Cache Hit Ratio:**
- Target: 99%+ for OLTP workloads
- < 95% suggests insufficient memory or wrong queries
- Monitor with pg_stat_database

**I/O Patterns:**
- Sequential I/O: Fast, good for scans
- Random I/O: Slow, necessary for index lookups
- `random_page_cost`: Planner's random I/O cost (default 4.0)
- Lower for SSDs (1.1-2.0)

## Indexing Deep Dive

### B-Tree Index Internals

**Structure:**
- Balanced tree with sorted keys
- Leaf pages contain pointers to table rows
- Internal pages guide searches
- Height typically 3-4 for millions of rows

**Operations:**
- Search: O(log n) traversal to leaf
- Insert: Add to leaf, may split pages
- Delete: Mark entry dead, reclaim with VACUUM
- Scan: Follow leaf page chain

**Optimal Use:**
- Equality: `WHERE id = 5`
- Range: `WHERE created_at > '2024-01-01'`
- Sorting: `ORDER BY name`
- Prefix matching: `WHERE email LIKE 'user%'`

### GIN Index for Complex Types

**When to Use:**
- JSONB containment: `WHERE data @> '{"status": "active"}'`
- Array operations: `WHERE tags @> ARRAY['sql']`
- Full-text search: `WHERE search_vector @@ query`
- Multi-valued columns

**Index Options:**
```sql
-- Standard GIN (supports more operators)
CREATE INDEX idx_data_gin ON documents USING GIN (data);

-- jsonb_path_ops (smaller, faster for @>)
CREATE INDEX idx_data_path_ops ON documents USING GIN (data jsonb_path_ops);

-- Fast update (larger index, faster inserts)
CREATE INDEX idx_data_fastupdate ON documents
USING GIN (data) WITH (fastupdate = on);
```

**Performance Characteristics:**
- Slower inserts/updates (rebuilds posting lists)
- Very fast for containment queries
- Can be large for high-cardinality data
- Benefits from pending list for batched updates

### GiST Index for Geometric Data

**Use Cases:**
- Spatial queries: `WHERE location <-> point(0,0) < 100`
- Range types: `WHERE period @> '2024-01-01'::date`
- Full-text search (alternative to GIN)
- Nearest neighbor searches

**Example with PostGIS:**
```sql
-- Install PostGIS
CREATE EXTENSION postgis;

-- Create spatial table
CREATE TABLE locations (
    id SERIAL PRIMARY KEY,
    name TEXT,
    location GEOGRAPHY(POINT, 4326)
);

-- Create GiST index
CREATE INDEX idx_locations_spatial ON locations USING GiST (location);

-- Spatial queries
SELECT name FROM locations
WHERE ST_DWithin(location, ST_MakePoint(-122.42, 37.77)::geography, 1000);
```

### BRIN Index for Large Tables

**When BRIN Excels:**
- Very large tables (billions of rows)
- Naturally ordered data (timestamps, IDs)
- Append-only or sorted data
- Low selectivity queries acceptable

**Characteristics:**
- Tiny index size (100x-1000x smaller than B-tree)
- Stores min/max values per block range
- Fast creation and updates
- Less precise than B-tree (more false positives)

**Example:**
```sql
-- Time-series table
CREATE TABLE sensor_data (
    id BIGSERIAL PRIMARY KEY,
    sensor_id INTEGER NOT NULL,
    value NUMERIC NOT NULL,
    timestamp TIMESTAMP NOT NULL
);

-- BRIN index on timestamp (naturally ordered)
CREATE INDEX idx_sensor_timestamp ON sensor_data
USING BRIN (timestamp) WITH (pages_per_range = 128);

-- Query uses BRIN for quick filtering
SELECT AVG(value) FROM sensor_data
WHERE timestamp > NOW() - INTERVAL '1 hour';
```

### Index-Only Scans

**How It Works:**
- Query satisfied entirely from index
- No table heap access needed
- Requires visibility map (updated by VACUUM)
- Dramatically faster for large tables

**Enabling Index-Only Scans:**
```sql
-- Include columns in index
CREATE INDEX idx_users_email_include ON users(email)
INCLUDE (first_name, last_name);

-- Query uses index-only scan
SELECT first_name, last_name FROM users
WHERE email = 'user@example.com';

-- Check with EXPLAIN
EXPLAIN SELECT first_name, last_name FROM users
WHERE email = 'user@example.com';
-- Shows: Index Only Scan using idx_users_email_include
```

## Query Optimization Strategies

### Analyzing Query Plans

**EXPLAIN Options:**
```sql
-- Show plan without execution
EXPLAIN SELECT ...;

-- Execute and show actual times
EXPLAIN ANALYZE SELECT ...;

-- Show buffer usage
EXPLAIN (ANALYZE, BUFFERS) SELECT ...;

-- Verbose output with schema info
EXPLAIN (ANALYZE, BUFFERS, VERBOSE) SELECT ...;

-- JSON output for tools
EXPLAIN (ANALYZE, FORMAT JSON) SELECT ...;
```

**Reading EXPLAIN Output:**
- **Seq Scan**: Full table scan (potentially slow)
- **Index Scan**: Index lookup with table access
- **Index Only Scan**: Satisfied from index alone
- **Bitmap Heap Scan**: Index scan + sort + table access
- **Nested Loop**: For each outer row, scan inner
- **Hash Join**: Build hash table, probe with other table
- **Merge Join**: Sort both inputs, merge scan

**Cost Analysis:**
- First number: Startup cost
- Second number: Total cost
- Rows: Estimated row count
- Width: Estimated row size in bytes

### Common Optimization Techniques

**1. Add Indexes:**
```sql
-- Identify missing indexes
EXPLAIN ANALYZE SELECT * FROM orders WHERE user_id = 123;
-- Shows Seq Scan -> needs index

-- Create index
CREATE INDEX CONCURRENTLY idx_orders_user ON orders(user_id);

-- Verify index usage
EXPLAIN ANALYZE SELECT * FROM orders WHERE user_id = 123;
-- Shows Index Scan using idx_orders_user
```

**2. Optimize Joins:**
```sql
-- Poor: Cartesian product
SELECT * FROM users, orders WHERE users.id = orders.user_id;

-- Better: Explicit JOIN
SELECT * FROM users
JOIN orders ON users.id = orders.user_id;

-- Best: Add indexes on join columns
CREATE INDEX idx_orders_user ON orders(user_id);
```

**3. Avoid SELECT *:**
```sql
-- Poor: Fetches unnecessary columns
SELECT * FROM users WHERE email = 'user@example.com';

-- Better: Select only needed columns
SELECT id, email, name FROM users WHERE email = 'user@example.com';

-- Enables index-only scans with covering indexes
```

**4. Use CTEs for Readability:**
```sql
-- Complex query split into readable CTEs
WITH active_users AS (
    SELECT id, email FROM users WHERE status = 'active'
),
recent_orders AS (
    SELECT user_id, COUNT(*) as order_count
    FROM orders
    WHERE created_at > NOW() - INTERVAL '30 days'
    GROUP BY user_id
)
SELECT u.email, COALESCE(o.order_count, 0) as orders
FROM active_users u
LEFT JOIN recent_orders o ON u.id = o.user_id;
```

**5. Batch Operations:**
```sql
-- Poor: One row at a time
INSERT INTO users (email) VALUES ('user1@example.com');
INSERT INTO users (email) VALUES ('user2@example.com');

-- Better: Batch insert
INSERT INTO users (email) VALUES
    ('user1@example.com'),
    ('user2@example.com'),
    ('user3@example.com');

-- Or use COPY for bulk loads
COPY users (email) FROM '/tmp/users.csv' CSV;
```

### Statistics and ANALYZE

**Updating Statistics:**
```sql
-- Analyze entire database
ANALYZE;

-- Analyze specific table
ANALYZE users;

-- Analyze with verbose output
ANALYZE VERBOSE users;

-- Check statistics age
SELECT schemaname, tablename, last_analyze, last_autoanalyze
FROM pg_stat_user_tables
ORDER BY last_analyze NULLS FIRST;
```

**Adjusting Statistics Target:**
```sql
-- Increase statistics detail for important columns
ALTER TABLE users ALTER COLUMN email SET STATISTICS 1000;

-- Default is 100, range 1-10000
-- Higher values = better estimates, slower ANALYZE
```

## Production Database Management

### Configuration Tuning

**Memory Settings:**
```conf
# Total system RAM: 16GB
# PostgreSQL allocation: ~4GB

shared_buffers = 4GB              # 25% of RAM
effective_cache_size = 12GB       # 75% of RAM
work_mem = 64MB                   # Per operation (sort, hash)
maintenance_work_mem = 1GB        # VACUUM, CREATE INDEX
```

**Checkpoint Settings:**
```conf
checkpoint_timeout = 15min        # Time between checkpoints
max_wal_size = 4GB               # WAL size before checkpoint
checkpoint_completion_target = 0.9 # Spread I/O over 90% of interval
wal_buffers = 16MB               # WAL buffer size
```

**Connection Settings:**
```conf
max_connections = 200            # Maximum connections
superuser_reserved_connections = 3
idle_in_transaction_session_timeout = 60000  # 1 minute
```

**Query Planner:**
```conf
random_page_cost = 1.1           # Lower for SSD (default 4.0)
effective_io_concurrency = 200   # Concurrent I/O (SSD)
default_statistics_target = 100  # Statistics detail
```

**Autovacuum:**
```conf
autovacuum = on
autovacuum_max_workers = 4
autovacuum_naptime = 10s         # Check interval
autovacuum_vacuum_scale_factor = 0.1
autovacuum_analyze_scale_factor = 0.05
```

### Connection Pooling with pgBouncer

**Installation:**
```bash
sudo apt-get install pgbouncer
```

**Configuration (/etc/pgbouncer/pgbouncer.ini):**
```ini
[databases]
mydb = host=localhost port=5432 dbname=mydb

[pgbouncer]
listen_addr = *
listen_port = 6432
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt
pool_mode = transaction
max_client_conn = 1000
default_pool_size = 25
reserve_pool_size = 5
reserve_pool_timeout = 3
```

**User Authentication (/etc/pgbouncer/userlist.txt):**
```
"username" "md5hashed_password"
```

**Application Connection:**
```python
# Connect to pgBouncer instead of PostgreSQL
import psycopg2
conn = psycopg2.connect(
    host='localhost',
    port=6432,  # pgBouncer port
    dbname='mydb',
    user='username',
    password='password'
)
```

### Monitoring and Alerting

**Key Metrics:**
- Connection count and state
- Query latency (p50, p95, p99)
- Cache hit ratio (target >99%)
- Replication lag (target <1s)
- Disk space utilization
- Transaction rate
- Lock waits and deadlocks

**Monitoring Tools:**
- **pg_stat_statements**: Query performance tracking
- **pgAdmin**: GUI for management and monitoring
- **pgBadger**: Log analysis and reporting
- **Prometheus + postgres_exporter**: Metrics collection
- **Grafana**: Visualization dashboards
- **Datadog, New Relic**: Commercial APM solutions

**Health Check Query:**
```sql
-- Overall database health
SELECT
    (SELECT count(*) FROM pg_stat_activity) as connections,
    (SELECT count(*) FROM pg_stat_activity WHERE state = 'active') as active,
    (SELECT pg_database_size(current_database())) as db_size,
    (SELECT setting::int FROM pg_settings WHERE name = 'max_connections') as max_conn;
```

## Real-World Patterns

### Multi-Tenant Database Design

**Approach 1: Shared Schema with tenant_id**
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    email TEXT NOT NULL,
    UNIQUE (tenant_id, email)
);

-- Row-level security
CREATE POLICY tenant_isolation ON users
    USING (tenant_id = current_setting('app.current_tenant')::INTEGER);

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
```

**Approach 2: Schema per Tenant**
```sql
-- Create schema for each tenant
CREATE SCHEMA tenant_1;
CREATE SCHEMA tenant_2;

-- Tables in tenant schema
CREATE TABLE tenant_1.users (
    id SERIAL PRIMARY KEY,
    email TEXT NOT NULL UNIQUE
);

-- Set search path per connection
SET search_path TO tenant_1, public;
```

**Approach 3: Database per Tenant**
- Complete isolation
- Independent backups and scaling
- Higher operational overhead

### Time-Series Data Management

**Hypertable Pattern with TimescaleDB:**
```sql
-- Install TimescaleDB
CREATE EXTENSION timescaledb;

-- Create hypertable
CREATE TABLE metrics (
    time TIMESTAMPTZ NOT NULL,
    device_id INTEGER NOT NULL,
    temperature NUMERIC,
    humidity NUMERIC
);

SELECT create_hypertable('metrics', 'time');

-- Automatic partitioning by time
-- Compression for old data
ALTER TABLE metrics SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'device_id'
);

-- Compression policy
SELECT add_compression_policy('metrics', INTERVAL '7 days');

-- Retention policy
SELECT add_retention_policy('metrics', INTERVAL '90 days');
```

### Audit Logging Pattern

```sql
-- Audit table
CREATE TABLE audit_log (
    id BIGSERIAL PRIMARY KEY,
    table_name TEXT NOT NULL,
    operation TEXT NOT NULL,
    old_data JSONB,
    new_data JSONB,
    changed_by TEXT NOT NULL,
    changed_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Audit trigger function
CREATE OR REPLACE FUNCTION audit_trigger_func()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO audit_log (table_name, operation, old_data, new_data, changed_by)
    VALUES (
        TG_TABLE_NAME,
        TG_OP,
        CASE WHEN TG_OP IN ('UPDATE', 'DELETE') THEN row_to_json(OLD) END,
        CASE WHEN TG_OP IN ('INSERT', 'UPDATE') THEN row_to_json(NEW) END,
        current_user
    );
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- Apply to tables
CREATE TRIGGER users_audit
AFTER INSERT OR UPDATE OR DELETE ON users
FOR EACH ROW EXECUTE FUNCTION audit_trigger_func();
```

## Resources and Community

**Official Documentation:**
- PostgreSQL Documentation: https://www.postgresql.org/docs/
- PostgreSQL Wiki: https://wiki.postgresql.org/
- PostgreSQL Mailing Lists: https://www.postgresql.org/list/

**Learning Resources:**
- PostgreSQL Tutorial: https://www.postgresqltutorial.com/
- Use The Index, Luke: https://use-the-index-luke.com/
- Postgres Weekly Newsletter: https://postgresweekly.com/

**Tools and Extensions:**
- PostGIS (spatial): https://postgis.net/
- TimescaleDB (time-series): https://www.timescale.com/
- pgBouncer (pooling): https://www.pgbouncer.org/
- Citus (sharding): https://www.citusdata.com/
- pgAdmin (GUI): https://www.pgadmin.org/

**Community:**
- PostgreSQL Slack: postgres-slack.herokuapp.com
- Reddit: r/PostgreSQL
- Stack Overflow: postgresql tag
- Planet PostgreSQL: https://planet.postgresql.org/

---

**Skill Version**: 1.0.0
**Last Updated**: October 2025
**PostgreSQL Compatibility**: 12, 13, 14, 15, 16+
