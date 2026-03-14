---
name: google-drive
description: Upload files, create folders, list and search Google Drive via CLI
---
# Google Drive

> Upload files, create folders, list and search Google Drive via CLI.

## When to use

- Upload proposals, invoices, contracts to client folders
- Create new client folder structure
- List or search files in Drive
- Any Google Drive file management task

## Dependencies

- Other skills: `google-auth` (if token expired)
- External: Python 3, `google-api-python-client`, `google-auth`

## Paths

| What | Path |
|------|------|
| Script | `$GOOGLE_TOOLS_PATH/drive_manager.py` |
| Token | `$GOOGLE_TOOLS_PATH/token.json` |
| Credentials | `$GOOGLE_TOOLS_PATH/credentials.json` |
| Venv Python | `$GOOGLE_TOOLS_PATH/.venv/bin/python3` |

## Known Folder IDs

| Folder | ID |
|--------|----|
| Root (WeLabelData) | `<YOUR_DRIVE_ROOT_ID>` |
| Clients | `<YOUR_CLIENTS_FOLDER_ID>` |
| Templates | `<YOUR_TEMPLATES_FOLDER_ID>` |

## How to execute

### List folder contents

```bash
cd $GOOGLE_TOOLS_PATH && python3 drive_manager.py list FOLDER_ID
```

### Create a folder

```bash
cd $GOOGLE_TOOLS_PATH && python3 drive_manager.py create-folder "Folder Name" --parent FOLDER_ID
```

### Upload a file

```bash
cd $GOOGLE_TOOLS_PATH && python3 drive_manager.py upload /path/to/file.pdf --folder FOLDER_ID
cd $GOOGLE_TOOLS_PATH && python3 drive_manager.py upload /path/to/file.pdf --folder FOLDER_ID --name "Custom Name.pdf"
```

### Search by name

```bash
cd $GOOGLE_TOOLS_PATH && python3 drive_manager.py search "query"
cd $GOOGLE_TOOLS_PATH && python3 drive_manager.py search "query" --folder FOLDER_ID
```

### Share file/folder

```bash
cd $GOOGLE_TOOLS_PATH && ./.venv/bin/python3 drive_manager.py share FILE_ID --email user@example.com --role writer
cd $GOOGLE_TOOLS_PATH && ./.venv/bin/python3 drive_manager.py share FILE_ID --email user@example.com --role reader --notify --message "Please review"
```

### Check permissions

```bash
cd $GOOGLE_TOOLS_PATH && ./.venv/bin/python3 drive_manager.py permissions FILE_ID
```

### Create Google Doc

```bash
cd $GOOGLE_TOOLS_PATH && ./.venv/bin/python3 drive_manager.py create-doc "Title" --folder FOLDER_ID
cd $GOOGLE_TOOLS_PATH && ./.venv/bin/python3 drive_manager.py create-doc "Title" --folder FOLDER_ID --html /path/to/content.html
```

### File info (modified time, last editor)

```bash
cd $GOOGLE_TOOLS_PATH && ./.venv/bin/python3 drive_manager.py info FILE_ID
```

## Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `folder_id` | Folder ID for `list` command | required |
| `--parent` | Parent folder ID for `create-folder` | root |
| `--folder` | Target folder ID for `upload` / `search` / `create-doc` | none |
| `--name` | Custom filename for `upload` | original filename |
| `--email` | Email to share with (`share` command) | required |
| `--role` | Permission role: `reader`, `writer`, `commenter` | writer |
| `--notify` | Send email notification when sharing | false |
| `--message` | Custom notification message | none |
| `--html` | Path to HTML file for doc content (`create-doc`) | empty doc |

## Examples

### List all client folders

```bash
cd $GOOGLE_TOOLS_PATH && python3 drive_manager.py list <YOUR_CLIENTS_FOLDER_ID>
```

### Create a new client folder

```bash
cd $GOOGLE_TOOLS_PATH && python3 drive_manager.py create-folder "Acme Corp" --parent <YOUR_CLIENTS_FOLDER_ID>
```

### Upload invoice to client folder

```bash
cd $GOOGLE_TOOLS_PATH && python3 drive_manager.py upload ~/invoices/inv-100.pdf --folder CLIENT_FOLDER_ID --name "Invoice #100.pdf"
```

### Search for proposals

```bash
cd $GOOGLE_TOOLS_PATH && python3 drive_manager.py search "proposal" --folder <YOUR_CLIENTS_FOLDER_ID>
```

## Output Format

All commands output JSON array. Each entry has:
- `id` — Google Drive file ID
- `name` — file/folder name
- `mimeType` — MIME type (`application/vnd.google-apps.folder` for folders)
- `webViewLink` — direct link to open in browser

## Limitations

- Scopes: uses `drive.readonly` (list/search) + `drive.file` (create/upload/share). Cannot modify files not created by this app.
- Upload: single file at a time. For bulk uploads, loop in bash.
- Search: name-based only. Use Google Drive web UI for full-text content search.
- Sharing: can only share files created by this app (drive.file scope). Cannot share files created elsewhere.
- Create-doc: uses Drive API upload with HTML conversion (no Docs API needed). Formatting via HTML.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `token.json` expired | Run `google-auth` skill to refresh |
| 403 insufficient permissions | Check scopes in `google_scopes.py`, may need to re-auth |
| File not found on upload | Use absolute path or `~` expansion |
| Empty list result | Verify folder ID is correct, check trashed status |

## Related skills

- `google-auth` — OAuth token management
- `invoice-generator-agent` — generates invoices that can be uploaded here
