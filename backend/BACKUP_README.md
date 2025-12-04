# Weaviate Backup and Restore

Backup and restore utility for Weaviate collections with support for cross-system migration.

## Prerequisites

- Weaviate running with `backup-filesystem` module enabled (already configured in `docker-compose.yml`)
- Python 3.8+ with `requests` and `python-dotenv` packages

## Quick Start

### 1. Start Weaviate

```bash
docker-compose up -d weaviate
```

### 2. Create a Backup

```bash
python backend/weaviate_backup.py backup --id my-backup
```

Backups are stored in `./backups/<backup-id>/`

### 3. Restore a Backup

```bash
python backend/weaviate_backup.py restore --id my-backup
```

## Usage Examples

### List All Collections

```bash
python backend/weaviate_backup.py list-collections
```

### Backup All Collections

```bash
python backend/weaviate_backup.py backup --id backup-20250123
```

### Backup Specific Collections

```bash
python backend/weaviate_backup.py backup --id partial-backup --include KnowledgeBase UserProfiles
```

### Backup Excluding Collections

```bash
python backend/weaviate_backup.py backup --id backup-no-temp --exclude TempData TestCollection
```

### Restore All Collections

```bash
python backend/weaviate_backup.py restore --id backup-20250123
```

**Note:** Collections must not exist before restore. Delete them first or restore to a clean instance.

### Restore Specific Collections

```bash
python backend/weaviate_backup.py restore --id backup-20250123 --include KnowledgeBase
```

### Check Backup Status

```bash
python backend/weaviate_backup.py status --id my-backup --operation backup
```

### Check Restore Status

```bash
python backend/weaviate_backup.py status --id my-backup --operation restore
```

### Async Operations (Don't Wait)

```bash
# Start backup without waiting
python backend/weaviate_backup.py backup --id async-backup --no-wait

# Check status later
python backend/weaviate_backup.py status --id async-backup --operation backup
```

### Custom Timeouts

```bash
# For large databases
python backend/weaviate_backup.py backup --id large-backup --wait-timeout 600
```

### Connect to Remote Weaviate

```bash
python backend/weaviate_backup.py backup \
  --host 192.168.1.100 \
  --port 8080 \
  --id remote-backup
```

## Cross-System Migration

### Scenario: Migrate data from System A to System B

**On System A (Source):**

```bash
# Step 1: Create backup
python backend/weaviate_backup.py backup --id migration-backup-20250123
```

**Transfer Backup Files:**

Choose one method:

**Option 1: Using rsync**
```bash
rsync -avz ./backups/migration-backup-20250123/ \
  user@systemB:/path/to/onboarding-agent/backups/migration-backup-20250123/
```

**Option 2: Using scp**
```bash
scp -r ./backups/migration-backup-20250123 \
  user@systemB:/path/to/onboarding-agent/backups/
```

**Option 3: Create archive**
```bash
# On System A
tar -czf migration-backup-20250123.tar.gz -C backups migration-backup-20250123

# Transfer the file (via scp, USB, cloud storage, etc.)

# On System B
tar -xzf migration-backup-20250123.tar.gz -C backups/
```

**On System B (Target):**

```bash
# Step 2: Verify Weaviate is running
docker-compose up -d weaviate

# Step 3: Restore backup
python backend/weaviate_backup.py restore --id migration-backup-20250123

# Step 4: Verify collections
python backend/weaviate_backup.py list-collections
```

## Integration with Async Weaviate Client

The backup utility works alongside your existing `async_weaviate_client.py`. Here's how they complement each other:

### When to Use Backup Utility

- **Before schema changes**: Create safety backup
- **Production deployments**: Backup before updates
- **Data migration**: Move data between systems
- **Disaster recovery**: Regular scheduled backups
- **Development**: Copy production data to dev environment

### When to Use Async Client

- **Normal operations**: Insert, update, delete data
- **Search operations**: Semantic and hybrid search
- **Collection management**: Create, delete collections
- **Data operations**: CRUD operations on objects

### Example Workflow

```bash
# 1. Use async client to populate data (your application code)
# Your Python code using async_weaviate_client.py creates collections and inserts data

# 2. Create backup before making changes
python backend/weaviate_backup.py backup --id pre-update-backup

# 3. Make changes using your application
# Your Python code modifies schema or data

# 4. If something goes wrong, restore
python backend/weaviate_backup.py restore --id pre-update-backup
```

### Using with Environment Variables

The backup utility reads from the same environment variables as your async client:

```bash
# .env file
WEAVIATE_HOST=localhost
WEAVIATE_PORT=8080
```

Both tools will use these settings automatically.

## Command Reference

### Global Options

```
--host HOST           Weaviate host (default: localhost or WEAVIATE_HOST env)
--port PORT           Weaviate port (default: 8080 or WEAVIATE_PORT env)
--scheme SCHEME       Connection scheme: http or https (default: http)
--timeout TIMEOUT     Request timeout in seconds (default: 300)
```

### Backup Command

```bash
python backend/weaviate_backup.py backup --id BACKUP_ID [OPTIONS]
```

Options:
- `--id ID` - Unique backup identifier (required)
- `--include COL1 COL2` - Collections to include (default: all)
- `--exclude COL1 COL2` - Collections to exclude
- `--no-wait` - Don't wait for completion
- `--wait-timeout SECONDS` - Max wait time (default: 300)

### Restore Command

```bash
python backend/weaviate_backup.py restore --id BACKUP_ID [OPTIONS]
```

Options:
- `--id ID` - Backup identifier to restore (required)
- `--include COL1 COL2` - Collections to restore (default: all)
- `--exclude COL1 COL2` - Collections to exclude
- `--no-wait` - Don't wait for completion
- `--wait-timeout SECONDS` - Max wait time (default: 300)

### Status Command

```bash
python backend/weaviate_backup.py status --id BACKUP_ID --operation OPERATION
```

Options:
- `--id ID` - Backup identifier (required)
- `--operation TYPE` - Operation type: backup or restore (required)

### List Collections Command

```bash
python backend/weaviate_backup.py list-collections
```

## Common Scenarios

### Regular Backups (Cron Job)

```bash
# Add to crontab (crontab -e)
0 2 * * * cd /path/to/onboarding-agent && python backend/weaviate_backup.py backup --id daily-$(date +\%Y\%m\%d) >> /var/log/weaviate-backup.log 2>&1
```

### Pre-Deployment Backup Script

```bash
#!/bin/bash
# backup-before-deploy.sh

BACKUP_ID="pre-deploy-$(date +%Y%m%d-%H%M%S)"

python backend/weaviate_backup.py backup --id "$BACKUP_ID"

if [ $? -eq 0 ]; then
    echo "Backup successful: $BACKUP_ID"
    echo "$BACKUP_ID" > .last-backup-id
    exit 0
else
    echo "Backup failed!"
    exit 1
fi
```

### Development Data Sync

```bash
# On production server
python backend/weaviate_backup.py backup --id prod-snapshot-$(date +%Y%m%d)

# Transfer to dev machine
scp -r backups/prod-snapshot-20250123 dev-machine:/path/to/project/backups/

# On dev machine
python backend/weaviate_backup.py restore --id prod-snapshot-20250123
```

### Safe Schema Migration

```python
# safe-migration.py
import subprocess
import sys
from datetime import datetime

# Create backup
backup_id = f"pre-migration-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
print(f"Creating backup: {backup_id}")

result = subprocess.run([
    "python", "backend/weaviate_backup.py",
    "backup", "--id", backup_id
])

if result.returncode != 0:
    print("Backup failed. Aborting migration.")
    sys.exit(1)

print(f"Backup successful. You can restore with:")
print(f"  python backend/weaviate_backup.py restore --id {backup_id}")

# Now safe to run your migration
```

## Troubleshooting

### "Backup module not enabled"

Restart Weaviate to apply configuration:
```bash
docker-compose restart weaviate
```

### "Collection already exists" during restore

Delete existing collections before restore or use `--include` to restore only non-conflicting collections.

### "Connection refused"

Check if Weaviate is running:
```bash
docker-compose ps weaviate
curl http://localhost:8080/v1/meta
```

### Slow backup/restore

Increase timeout:
```bash
python backend/weaviate_backup.py backup --id my-backup --wait-timeout 600
```

### Check Weaviate logs

```bash
docker-compose logs -f weaviate
```

## Backup Storage

Backups are stored in `./backups/` directory with the following structure:

```
backups/
├── .gitkeep
├── backup-20250123/
│   ├── collection1/
│   │   └── data files...
│   └── collection2/
│       └── data files...
└── migration-backup/
    └── collection data...
```

## Best Practices

1. **Use descriptive backup IDs with timestamps**:
   ```bash
   --id "production-backup-$(date +%Y%m%d-%H%M%S)"
   ```

2. **Test restores regularly** to ensure backup integrity

3. **Automate daily backups** using cron jobs

4. **Keep multiple backup versions** for disaster recovery

5. **Backup before making schema changes**

6. **Document your backup schedule and retention policy**

7. **Store critical backups off-site** (copy to cloud storage)

## Help

Get detailed help for any command:

```bash
# General help
python backend/weaviate_backup.py --help

# Backup command help
python backend/weaviate_backup.py backup --help

# Restore command help
python backend/weaviate_backup.py restore --help
```

## References

- [Weaviate Backup Tutorial](https://weaviate.io/blog/tutorial-backup-and-restore-in-weaviate)
- [Weaviate Backup Configuration](https://docs.weaviate.io/deploy/configuration/backups)

