# Google Workspace CLI - Authentication Methods

## Overview

Google Workspace CLI supports four authentication methods. Choose based on your use case:

| Method | Use Case | Setup Complexity | Interactive |
|--------|----------|------------------|-------------|
| **OAuth Login** | Personal/user accounts, agents with browser access | Low | Yes |
| **Service Account** | Server-to-server, headless agents, production | Medium | No |
| **Pre-obtained Tokens** | When you already have access tokens | Low | No |
| **Credential Files** | Standard Google credential paths | Low | No |

## 1. OAuth Login (Interactive)

Best for agents running on user machines with browser access.

### First-Time Setup

```bash
gws auth setup
```

This creates a Cloud project, enables required Google Workspace APIs, and opens a browser for authentication.

### Subsequent Logins

```bash
gws auth login
```

Prompts to select OAuth scopes and opens browser for authentication.

### Storage

Tokens are stored in:
- **Linux/macOS**: `~/.config/gws/credentials.json`
- **Windows**: `%APPDATA%\gws\credentials.json`

Tokens are encrypted at rest using AES-256-GCM.

### Refresh

Tokens auto-refresh when expired. To force refresh:

```bash
gws auth refresh
```

### Logout

```bash
gws auth logout
```

### Checking Status

```bash
gws auth status
```

Shows current authentication details and available scopes.

## 2. Service Account (Machine-to-Machine)

Best for agents in production, headless environments, or requiring elevated permissions.

### Setup

1. **Create service account in Google Cloud Console**:
   - Go to `console.cloud.google.com`
   - Select your project
   - Navigate to "Service Accounts" under IAM & Admin
   - Click "Create Service Account"
   - Name it (e.g., `gws-agent`)
   - Click "Create and Continue"

2. **Create and download key**:
   - In the service account details, go to "Keys" tab
   - Click "Add Key" → "Create new key"
   - Choose JSON format
   - Download the credentials file

3. **Configure in CLI**:

```bash
gws auth config --service-account /path/to/service-account-key.json
```

4. **Grant permissions**:
   - Share Google Workspace resources (Drives, Calendars) with the service account email
   - Or use Google Admin to grant domain-wide delegation (advanced)

### Domain-wide Delegation (Optional)

For admin operations or accessing user resources without sharing:

1. In the service account details, copy the "Client ID"
2. In Google Admin Console: Security → API Controls → Domain-wide delegation
3. Click "Add new"
4. Paste the Client ID and grant required OAuth scopes

Then use in CLI:

```bash
gws auth config --service-account /path/to/key.json --impersonate user@domain.com
```

### Credential File Format

Example service account credential file:

```json
{
  "type": "service_account",
  "project_id": "my-project-123",
  "private_key_id": "key-id",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----",
  "client_email": "gws-agent@my-project.iam.gserviceaccount.com",
  "client_id": "123456789",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token"
}
```

**Security**: Store the credentials file securely. Never commit to version control.

## 3. Pre-obtained Tokens

If you already have an access token (from another OAuth flow):

```bash
gws auth token set --access-token "ya29.a0A..."
```

For refresh token:

```bash
gws auth token set --access-token "ya29.a0A..." --refresh-token "1//0A..."
```

Tokens expire after 1 hour. Provide a refresh token to auto-renew.

## 4. Credential Files (Standard Paths)

CLI checks these paths automatically if no auth is configured:

1. `GOOGLE_APPLICATION_CREDENTIALS` environment variable
2. `~/.config/gws/credentials.json` (user token)
3. `~/.config/gcloud/application_default_credentials.json` (gcloud SDK)

### Using Environment Variable

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
gws drive.files.list
```

## Checking Authentication Status

```bash
gws auth status
```

Output:

```
Auth Status:
  Type: service_account
  Email: gws-agent@my-project.iam.gserviceaccount.com
  Scopes: calendar, drive, gmail, sheets, docs
```

## Required Scopes

CLI automatically requests the minimum required scopes for each API call. Common scopes:

- `https://www.googleapis.com/auth/gmail.send` — Send emails
- `https://www.googleapis.com/auth/drive` — Read/write files
- `https://www.googleapis.com/auth/calendar` — Manage calendar
- `https://www.googleapis.com/auth/spreadsheets` — Read/write sheets
- `https://www.googleapis.com/auth/docs` — Read/write documents

For service accounts, explicitly grant scopes in admin console.

## Troubleshooting

### "Invalid credentials"

1. Check if token is expired: `gws auth status`
2. Refresh token: `gws auth refresh`
3. Re-authenticate: `gws auth login`

### "Access denied" (Service Account)

1. Ensure service account has been granted access to resources
2. Check domain-wide delegation if using impersonation
3. Verify scopes are enabled in Google Cloud Console

### "Credentials not found"

1. Check `GOOGLE_APPLICATION_CREDENTIALS` env var
2. Ensure credentials file exists at configured path
3. Try explicit auth: `gws auth login` or `gws auth config --service-account ...`

## Security Best Practices

1. **Never hardcode credentials** in scripts
2. **Use service accounts** for production/agents
3. **Enable domain-wide delegation carefully** (principle of least privilege)
4. **Rotate credentials** periodically
5. **Use environment variables** for file paths
6. **Audit permissions** in Google Admin Console
7. **Encrypt credentials at rest** (CLI does this automatically)

Credentials are encrypted using AES-256-GCM before storage on disk.
