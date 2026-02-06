# Docker Data Persistence

## Problem

Data is lost when Docker containers are restarted.

## Root Cause

Database file path doesn't point to mounted volume, or no volume is configured.

## Solution

### 1. Use Named Volumes in docker-compose.yml

```yaml
services:
  backend:
    volumes:
      - backend-data:/app/data    # Mount named volume
    environment:
      - DATABASE_URL=sqlite+aiosqlite:////app/data/auto_info.db

volumes:
  backend-data:
    driver: local
```

### 2. Key Points

| Issue | Solution |
|-------|----------|
| **Relative path** (`./db.sqlite`) | Use absolute path in mounted directory |
| **Database URL** | Point to mounted volume (`////app/data/...`) |
| **Container rebuild** | Named volumes persist independently |

### 3. SQLite Path Format

For SQLite in Docker with volume mount:

```python
# Correct (4 slashes = absolute path)
DATABASE_URL = "sqlite+aiosqlite:////app/data/auto_info.db"

# Wrong (relative path, loses data)
DATABASE_URL = "sqlite+aiosqlite:///./auto_info.db"
```

The `////` format: `sqlite:///` (3 slashes for SQLite protocol) + `/app/data/...` (absolute path)

### 4. Volume Management Commands

```bash
# List volumes
docker volume ls

# Inspect volume
docker volume inspect auto_info_backend-data

# Backup volume
docker run --rm -v auto_info_backend-data:/data -v $(pwd):/backup alpine tar czf /backup/backup.tar.gz /data

# Remove volume (WARNING: deletes data)
docker volume rm auto_info_backend-data
```

### 5. Volume vs Bind Mount

| Type | Use When |
|-------|----------|
| **Named Volume** | Persistent data (database, uploads) |
| **Bind Mount** | Development (live code reload) |

### 6. .dockerignore

Don't let sensitive data be copied into images:

```
*.db
*.sqlite
certificates/
```
