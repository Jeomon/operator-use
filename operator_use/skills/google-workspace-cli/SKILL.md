---
name: google-workspace-cli
description: Access Google Workspace services (Gmail, Drive, Calendar, Sheets, Docs, Chat, Admin APIs) through a unified CLI. Use when integrating with Google Workspace, automating workflows, sending emails, managing files, scheduling tasks, or querying Google Workspace data. Supports OAuth, service accounts, and multiple authentication methods with built-in agent skills and AI integration.
---

# Google Workspace CLI (gws)

A unified command-line interface for all Google Workspace services with AI agent integration and helper commands.

## Quick Start

### Installation

Choose your preferred method:

**1. Pre-built Binary (Recommended)**

Download from GitHub Releases: https://github.com/googleworkspace/cli/releases

Extract and add to PATH:

```bash
# macOS/Linux
tar -xzf gws-*.tar.gz
sudo mv gws /usr/local/bin/

# Windows: Extract .zip and add to PATH
```

**2. npm (Requires Node.js 18+)**

```bash
npm install -g @googleworkspace/cli
```

**3. Homebrew (macOS/Linux)**

```bash
brew install googleworkspace-cli
```

**4. From Source (Requires Rust/Cargo)**

```bash
cargo install --git https://github.com/googleworkspace/cli --locked
```

**5. Nix**

```bash
nix run github:googleworkspace/cli
```

### Verify Installation

```bash
gws --version
gws help
```

### Authentication

**First time setup:**

```bash
gws auth setup
```

This creates a Cloud project, enables APIs, and sets up OAuth.

**Subsequent logins:**

```bash
gws auth login
```

Or use a service account:

```bash
gws auth config --service-account /path/to/service-account-key.json
```

See `references/authentication.md` for all authentication methods and detailed setup.

## Common Tasks

### Gmail

List unread messages:

```bash
gws gmail users messages list --params '{"userId":"me","q":"is:unread","maxResults":10}'
```

### Drive

List files:

```bash
gws drive files list --params '{"pageSize":5}'
```

List files in a folder:

```bash
gws drive files list --params '{"q":"parents='"'"'FOLDER_ID'"'"'","pageSize":10}'
```

### Calendar

List events:

```bash
gws calendar events list --params '{"calendarId":"primary","maxResults":10}'
```

### Sheets

List spreadsheets:

```bash
gws sheets spreadsheets list --params '{"maxResults":5}'
```

### Docs

List documents:

```bash
gws docs documents list --params '{"pageSize":5}'
```

## Key Features

### Dynamic API Discovery

All Google Workspace API endpoints are automatically available—no need to wait for CLI updates when Google adds new features.

```bash
gws [service].[resource].[method] [--flags]
```

### Agent Skills

100+ pre-built agent skills for common workflows. Agents automatically detect available servers via the `mcp` tool or direct integration.

### Helper Commands

High-level commands for repetitive tasks:

- `+send` — Send emails with automatic formatting
- `+agenda` — Get calendar agenda with timezone support
- `+upload` — Upload files to Drive with automatic folder handling
- `+standup-report` — Generate activity reports from mail/calendar/docs

### AI Integration

Built-in support for Gemini CLI and other AI agents. Output is structured as JSON for programmatic use.

```bash
gws calendar.events.list --format json
```

## Credential Management

Credentials are encrypted at rest using AES-256-GCM. Multiple authentication methods supported:

- **OAuth login** — Interactive browser-based authentication
- **Service account** — Machine-to-machine with .json credentials
- **Pre-obtained tokens** — Use existing tokens
- **Credential files** — Load from standard Google credential paths

See `references/authentication.md` for detailed authentication setup.

## Command Structure

All commands follow the pattern:

```bash
gws [service].[resource].[method] [--flags] [--format json|text|table]
```

### Common Services

- `gmail` — Email management (draft, send, read, search, labels)
- `drive` — File storage (upload, download, list, delete, share)
- `calendar` — Event scheduling (create, list, update, delete)
- `sheets` — Spreadsheet operations (read, write, create, manage)
- `docs` — Document creation and editing (create, read, write, comments)
- `chat` — Team messaging (send messages, create spaces, manage threads)
- `admin` — Organization management (users, devices, security, groups)

See `references/api-overview.md` for complete service reference.

## Advanced Features

### Pagination

Automatic pagination with streaming for large result sets:

```bash
gws drive.files.list --pageSize 100 --stream
```

### Dry-run Mode

Preview changes without executing:

```bash
gws calendar.events.insert --dryrun --summary "Test" --start '2024-04-15T10:00:00'
```

### Timezone-aware Scheduling

Calendar operations automatically handle timezone conversions:

```bash
gws +agenda --timezone "America/Los_Angeles" --days 7
```

### Multipart Uploads

Efficient file uploads with automatic chunking and resumption:

```bash
gws +upload --file large-file.zip --parent-id [FOLDER_ID] --resume
```

## Learning More

- **Commands**: See `references/commands.md` for helper command details
- **APIs**: See `references/api-overview.md` for service reference
- **Authentication**: See `references/authentication.md` for credential setup
- **Official Docs**: https://github.com/googleworkspace/cli

## Tips for AI Agents

1. **Structured Output**: Use `--format json` for reliable parsing
2. **Error Handling**: Check exit codes; errors are logged to stderr
3. **Quota Awareness**: Google Workspace APIs have rate limits; implement backoff
4. **Batch Operations**: Group related operations to reduce API calls
5. **Credential Security**: Never expose credentials in logs; use environment variables

Set credentials via environment:

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
```

Or pass via flag:

```bash
gws --credentials /path/to/credentials.json [command]
```
