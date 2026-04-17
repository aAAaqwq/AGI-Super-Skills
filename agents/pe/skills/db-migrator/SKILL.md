---
name: db-migrator
description: Database schema migration, versioning, and rollback management for SQL and NoSQL databases. Use when: (1) creating database migrations, (2) modifying table schemas, (3) adding/removing columns, (4) creating indexes, (5) data migrations, (6) rollback operations, (7) multi-environment sync, (8) seed data management. Supports PostgreSQL, MySQL, MongoDB, SQLite. Triggers: "migration", "alter table", "schema change", "database migration", "rollback migration", "knex", "prisma migrate", "flyway", "alembic".
---

# Database Migrator

Professional database schema migration and version control for production systems.

## Core Workflow

### 1. Create Migration

```bash
# Generate migration file
npm run migrate:make create_users_table
# or
npx prisma migrate dev --name add_user_email
# or
python -m alembic revision -m "add_user_email"
```

### 2. Write Migration

```javascript
// Knex.js example
exports.up = function(knex) {
  return knex.schema.createTable('users', table => {
    table.increments('id').primary();
    table.string('email').notNullable().unique();
    table.string('password_hash').notNullable();
    table.timestamp('created_at').defaultTo(knex.fn.now());
    table.timestamp('updated_at').defaultTo(knex.fn.now());
    
    // Indexes
    table.index('email');
  });
};

exports.down = function(knex) {
  return knex.schema.dropTable('users');
};
```

### 3. Run Migration

```bash
# Apply pending migrations
npm run migrate:up

# Rollback last migration
npm run migrate:down

# Rollback all
npm run migrate:reset

# Refresh (rollback + re-run)
npm run migrate:refresh
```

## Migration Best Practices

### Always Include Down Migration

```javascript
// ✅ Good - Reversible
exports.up = (knex) => knex.schema.alterTable('users', t => {
  t.string('phone').nullable();
});

exports.down = (knex) => knex.schema.alterTable('users', t => {
  t.dropColumn('phone');
});

// ❌ Bad - Irreversible
exports.up = (knex) => knex.schema.alterTable('users', t => {
  t.string('phone').nullable();
});
exports.down = () => {}; // Empty rollback!
```

### Atomic Migrations

```javascript
// ✅ Good - Single responsibility
// Migration 1: Add column
exports.up = (knex) => knex.schema.alterTable('users', t => {
  t.string('phone');
});

// Migration 2: Populate data
exports.up = (knex) => knex.raw(`
  UPDATE users SET phone = '000-000-0000' WHERE phone IS NULL
`);

// ❌ Bad - Mixed concerns
exports.up = async (knex) => {
  await knex.schema.alterTable('users', t => t.string('phone'));
  await knex.raw('UPDATE users SET phone = ...');
  await knex.schema.createTable('audit_log', ...);
};
```

### Safe Column Operations

```javascript
// Add column with default (avoid locking)
exports.up = (knex) => knex.raw(`
  ALTER TABLE users 
  ADD COLUMN phone VARCHAR(20) DEFAULT ''
`);

// Remove column safely
exports.down = (knex) => knex.raw(`
  ALTER TABLE users 
  DROP COLUMN phone
`);

// Rename column (data preserved)
exports.up = (knex) => knex.schema.alterTable('users', t => {
  t.renameColumn('phone', 'phone_number');
});
```

## Framework-Specific Patterns

### Prisma (Node.js)

```prisma
// schema.prisma
model User {
  id        Int      @id @default(autoincrement())
  email     String   @unique
  posts     Post[]
  createdAt DateTime @default(now())
}

// Run migration
npx prisma migrate dev --name init
npx prisma migrate deploy // Production
```

### Alembic (Python)

```python
# migrations/versions/abc123_add_email.py
def upgrade():
    op.add_column('users', sa.Column('email', sa.String(255)))

def downgrade():
    op.drop_column('users', 'email')

# Commands
alembic upgrade head
alembic downgrade -1
```

### Flyway (Java/General)

```sql
-- V1__create_users_table.sql
CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  email VARCHAR(255) NOT NULL UNIQUE,
  created_at TIMESTAMP DEFAULT NOW()
);

-- V2__add_phone_column.sql
ALTER TABLE users ADD COLUMN phone VARCHAR(20);
```

## Data Migrations

```javascript
// Transform data safely
exports.up = async (knex) => {
  const users = await knex('users').whereNull('full_name');
  
  for (const user of users) {
    await knex('users')
      .where({ id: user.id })
      .update({
        full_name: `${user.first_name} ${user.last_name}`
      });
  }
};
```

## Production Safety

```javascript
// Add timeout for large tables
exports.up = (knex) => knex.raw(`
  SET statement_timeout = '300s';
  ALTER TABLE large_table ADD COLUMN new_field TEXT;
`);

// Create index concurrently (PostgreSQL)
exports.up = (knex) => knex.raw(`
  CREATE INDEX CONCURRENTLY idx_users_email 
  ON users(email)
`);
```

## Scripts

- `scripts/create_migration.sh` - Generate migration file with timestamp
- `scripts/check_migrations.js` - Compare local vs remote migration status
- `scripts/seed_data.js` - Load seed data from JSON/CSV

## References

- `references/postgres_types.md` - PostgreSQL data types reference
- `references/mysql_types.md` - MySQL data types reference
- `references/migration_templates/` - Framework-specific templates
