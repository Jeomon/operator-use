# Google Workspace CLI - Commands Reference

Standard command patterns for common Workspace operations.

## Common Patterns

### Get Help

```bash
# Show all available commands
gws help

# Get help for a service
gws gmail help
gws drive help
gws calendar help

# Get help for a specific resource
gws gmail users help
gws drive files help
```

## Quick Commands

### Gmail

List unread emails:

```bash
gws gmail users messages list --params '{"userId":"me","q":"is:unread"}'
```

Get message count:

```bash
gws gmail users messages list --params '{"userId":"me","q":"from:manager@example.com"}' --format json | wc -l
```

### Drive

List recent files:

```bash
gws drive files list --params '{"pageSize":10,"orderBy":"modifiedTime desc"}'
```

Search by name:

```bash
gws drive files list --params '{"q":"name contains '"'"'report'"'"'"}'
```

Find files modified today:

```bash
gws drive files list --params '{"q":"modifiedTime > '"'"'2024-04-01T00:00:00'"'"'"}'
```

### Calendar

Show today's events:

```bash
gws calendar events list --params '{"calendarId":"primary","timeMin":"2024-04-01T00:00:00Z","maxResults":10}'
```

List all calendars:

```bash
gws calendar calendarList list --params '{"pageSize":50}'
```

### Sheets

Get spreadsheet info:

```bash
gws sheets spreadsheets get --params '{"spreadsheetId":"SHEET_ID"}'
```

### Docs

Get document:

```bash
gws docs documents get --params '{"documentId":"DOC_ID"}' --format json
```

## Working with JSON Output

Use `--format json` for reliable parsing:

```bash
# Get JSON output
gws drive files list --params '{"pageSize":5}' --format json > files.json

# Extract field with jq (if installed)
gws drive files list --params '{"pageSize":5}' --format json | jq '.files[].name'

# Count results
gws drive files list --params '{"pageSize":100}' --format json | jq '.files | length'
```

## Piping and Scripting

### Export to CSV

```bash
gws drive files list --params '{"pageSize":100}' --format csv > files.csv
```

### Loop over results

```bash
# Get file IDs and list each one
for FILE_ID in $(gws drive files list --params '{"pageSize":10}' --format json | jq -r '.files[].id'); do
  gws drive files get --params "{\"fileId\":\"$FILE_ID\"}" --format json | jq '.name, .modifiedTime'
done
```

### Batch operations

```bash
# Upload all PDFs to a folder
for file in *.pdf; do
  echo "Uploading $file..."
  # Use raw API or upload directly with multipart
  gws drive files create --params '{"name":"'"$file"'"}'
done
```

## Error Handling in Scripts

Always check exit codes:

```bash
#!/bin/bash
gws gmail users messages list --params '{"userId":"me"}' --format json
if [ $? -eq 0 ]; then
  echo "Success"
else
  echo "Error: command failed with exit code $?"
  exit 1
fi
```

Catch and log errors:

```bash
#!/bin/bash
OUTPUT=$(gws drive files list --params '{"pageSize":5}' 2>&1)
if [ $? -ne 0 ]; then
  echo "Error: $OUTPUT" >> error.log
  exit 1
fi
echo "$OUTPUT"
```

## Tips for Automation

1. **Use `--format json`** for reliable parsing in scripts
2. **Start small** — test with `pageSize":5` before scaling
3. **Check exit codes** — exit code 0 = success, non-zero = error
4. **Handle auth** — set `GOOGLE_APPLICATION_CREDENTIALS` for service accounts
5. **Rate limiting** — add delays between requests if running many operations
6. **Logging** — redirect stdout/stderr to files for debugging

## Troubleshooting

### "Not found" errors

Check if resource exists:

```bash
# Gmail: verify user ID
gws gmail users list --params '{}'

# Drive: verify file/folder ID exists
gws drive files get --params '{"fileId":"FILE_ID"}'
```

### "Permission denied"

Verify scopes are granted:

```bash
gws auth status
```

### "Invalid parameter"

Check JSON syntax in params:

```bash
# Make sure JSON is valid
echo '{"userId":"me","q":"is:unread"}' | jq .

# Then use it
gws gmail users messages list --params '{"userId":"me","q":"is:unread"}'
```

## See Also

- `api-overview.md` — Complete API reference by service
- `authentication.md` — Auth setup and credential management
