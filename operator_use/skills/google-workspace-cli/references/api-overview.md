# Google Workspace CLI - API Overview

Google Workspace services are accessed through the CLI using a standard command structure.

## Command Syntax

All commands follow this pattern:

```bash
gws [SERVICE] [RESOURCE] [METHOD] [--params JSON] [--format json|table|csv]
```

### Examples

```bash
# List files in Drive
gws drive files list --params '{"pageSize":10}'

# List calendar events
gws calendar events list --params '{"calendarId":"primary","maxResults":5}'

# List Gmail messages
gws gmail users messages list --params '{"userId":"me","q":"is:unread"}'
```

### Using --params

Pass parameters as JSON:

```bash
# Simple parameter
gws drive files list --params '{"pageSize":10}'

# Nested parameters
gws drive files list --params '{"q":"parents='"'"'FOLDER_ID'"'"'","pageSize":20}'

# Complex filters
gws gmail users messages list --params '{"userId":"me","q":"from:user@example.com","pageSize":5}'
```

## Gmail API

Email management and messaging.

```bash
# List unread messages
gws gmail users messages list --params '{"userId":"me","q":"is:unread","maxResults":10}'

# Get message details
gws gmail users messages get --params '{"userId":"me","id":"MESSAGE_ID"}'

# List labels
gws gmail users labels list --params '{"userId":"me"}'

# List threads
gws gmail users threads list --params '{"userId":"me","q":"is:unread","maxResults":5}'
```

## Drive API

File storage and organization.

```bash
# List files (paginated)
gws drive files list --params '{"pageSize":5}'

# Search for files by name
gws drive files list --params '{"q":"name contains '"'"'report'"'"'","pageSize":10}'

# List files in specific folder
gws drive files list --params '{"q":"parents='"'"'FOLDER_ID'"'"'","pageSize":10}'

# Get file metadata
gws drive files get --params '{"fileId":"FILE_ID"}'
```

## Calendar API

Event scheduling and calendar management.

```bash
# List events
gws calendar events list --params '{"calendarId":"primary","maxResults":10}'

# List with time filter
gws calendar events list --params '{"calendarId":"primary","timeMin":"2024-04-01T00:00:00Z","timeMax":"2024-04-30T23:59:59Z"}'

# Get calendar list
gws calendar calendarList list --params '{"pageSize":10}'
```

## Sheets API

Spreadsheet operations and data management.

```bash
# List spreadsheets
gws sheets spreadsheets list --params '{"pageSize":5}'

# Get spreadsheet metadata
gws sheets spreadsheets get --params '{"spreadsheetId":"SHEET_ID"}'

# Batch get values
gws sheets spreadsheets values batchGet --params '{"spreadsheetId":"SHEET_ID","ranges":["Sheet1!A1:B5"]}'
```

## Docs API

Document creation and editing.

```bash
# List documents
gws docs documents list --params '{"pageSize":5}'

# Get document
gws docs documents get --params '{"documentId":"DOC_ID"}'
```

## Chat API

Team messaging and space management.

```bash
# List spaces
gws chat spaces list --params '{"pageSize":10}'

# List messages in a space
gws chat spaces messages list --params '{"parent":"spaces/SPACE_ID","pageSize":10}'
```

## Admin API

Organization administration.

```bash
# List users in domain
gws directory users list --params '{"domain":"example.com","maxResults":10}'

# Get user details
gws directory users get --params '{"userKey":"user@example.com"}'

# List groups
gws directory groups list --params '{"domain":"example.com","maxResults":10}'
```

## Output Formats

Control output format with `--format`:

```bash
# JSON (best for automation)
gws drive files list --params '{"pageSize":5}' --format json

# Table format (human-readable)
gws drive files list --params '{"pageSize":5}' --format table

# CSV format
gws drive files list --params '{"pageSize":5}' --format csv
```

## Rate Limits

Google Workspace APIs have quotas:

- **Gmail**: 250 MB/day, rate-limited per user
- **Drive**: 10,000 files/minute, 1 MB/second
- **Calendar**: ~1,000 requests/minute
- **Sheets**: ~500 requests/minute
- **Docs**: ~300 requests/minute

Implement exponential backoff for rate limit errors (429 status).

## Pagination

For large result sets:

```bash
# Get first page
gws drive files list --params '{"pageSize":10}'

# Continue with nextPageToken (from previous response)
gws drive files list --params '{"pageSize":10,"pageToken":"NEXT_TOKEN"}'
```

## Error Handling

Common errors and exit codes:

- `0` — Success
- `1` — General error
- `2` — Invalid arguments
- `3` — Authentication error

Errors include HTTP status:
```
401 Unauthorized — Authentication issue
403 Forbidden — Insufficient permissions
404 Not Found — Resource not found
429 Too Many Requests — Rate limit exceeded
```

## Tips for AI Agents

1. Always use `--format json` for reliable parsing
2. Start with small page sizes to test queries
3. Check exit codes to detect errors
4. Use filters in `--params` to reduce results
5. Implement pagination for large datasets
