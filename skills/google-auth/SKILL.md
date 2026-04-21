---
name: google-auth
description: Google OAuth setup, refresh tokens
---
# Infra Google Auth

> Google OAuth setup, refresh tokens, troubleshooting

## When to use

- "Google API is not working"
- "401 Unauthorized"
- "token expired"
- Setting up a new project

## Paths

| What | Path |
|------|------|
| Credentials | `$GOOGLE_TOOLS_PATH/credentials.json` |
| Token | `$GOOGLE_TOOLS_PATH/token.json` |

## Scopes (permissions)

```python
SCOPES = [
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/drive',
]
```

## How to use existing token

```python
import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

with open('$GOOGLE_TOOLS_PATH/token.json', 'r') as f:
    token_data = json.load(f)

creds = Credentials(
    token=token_data.get('token'),
    refresh_token=token_data.get('refresh_token'),
    token_uri=token_data.get('token_uri'),
    client_id=token_data.get('client_id'),
    client_secret=token_data.get('client_secret')
)

# Gmail
gmail = build('gmail', 'v1', credentials=creds)

# Sheets
sheets = build('sheets', 'v4', credentials=creds)

# Drive
drive = build('drive', 'v3', credentials=creds)
```

## Refresh token manually

```python
from google.auth.transport.requests import Request

if creds.expired and creds.refresh_token:
    creds.refresh(Request())

    # Save the updated token
    with open('$GOOGLE_TOOLS_PATH/token.json', 'w') as f:
        json.dump({
            'token': creds.token,
            'refresh_token': creds.refresh_token,
            'token_uri': creds.token_uri,
            'client_id': creds.client_id,
            'client_secret': creds.client_secret,
        }, f)
```

## Create a new token (if the old one doesn't work)

```python
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [...]  # all required scopes

flow = InstalledAppFlow.from_client_secrets_file(
    '$GOOGLE_TOOLS_PATH/credentials.json',
    SCOPES
)
creds = flow.run_local_server(port=0)

# Save
with open('$GOOGLE_TOOLS_PATH/token.json', 'w') as f:
    json.dump({
        'token': creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri,
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
    }, f)
```

## Common API calls

### Reading Sheets

```python
result = sheets.spreadsheets().values().get(
    spreadsheetId='SPREADSHEET_ID',
    range="'Sheet Name'!A1:Z100"
).execute()
rows = result.get('values', [])
```

### Writing to Sheets

```python
sheets.spreadsheets().values().update(
    spreadsheetId='SPREADSHEET_ID',
    range="'Sheet Name'!A1",
    valueInputOption='RAW',
    body={'values': [['value1', 'value2']]}
).execute()
```

### Sending Email

```python
import base64
from email.mime.text import MIMEText

message = MIMEText('Body text', 'plain', 'utf-8')
message['to'] = 'recipient@email.com'
message['from'] = 'Your Name <your@email.com>'
message['subject'] = 'Subject'

raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
gmail.users().messages().send(userId='me', body={'raw': raw}).execute()
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| 401 Unauthorized | Refresh token or create a new one |
| invalid_grant | Token revoked, create a new one |
| Scope mismatch | Load token without scope verification |
| RefreshError | Create a new token via OAuth flow |

## Account

- Email: `your@email.com`
- Type: Google Workspace

## Related skills

- `email-send-direct` -- single email via Gmail API
- `email-send-bulk` -- bulk email via Gmail API
- `telegram-send` -- reads Sheets for data
