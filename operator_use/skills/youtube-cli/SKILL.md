---
name: youtube-cli
description: Fetch YouTube video and channel intelligence from CLI. Use when you need views, likes, comments, channel details, subscriber count, recent channel videos, or transcript text from a YouTube URL/ID via commands like `youtube <url> --transcript --likes --channel`.
---

# YouTube CLI Skill

Use this skill to query YouTube data from the terminal with a single command.

## What It Supports

- Video stats: views, likes, comments
- Channel info: channel name, subscriber count, total videos
- Recent videos under a channel
- Public transcript/captions (when available)
- JSON or readable text output

## API Key

Set `YOUTUBE_API_KEY` before running:

```bash
export YOUTUBE_API_KEY="your_key_here"
```

```powershell
$env:YOUTUBE_API_KEY="your_key_here"
```

The script also accepts:

```bash
youtube <url> --api-key your_key_here
```

## Command

The skill ships wrappers so you can use:

```bash
youtube <url-or-id> --likes --views --channel --subscribers --comments --transcript
```

Or run directly:

```bash
python scripts/youtube.py <url-or-id> --likes --views --channel --subscribers --comments --transcript
```

## Common Examples

Get everything:

```bash
youtube https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

Only transcript:

```bash
youtube https://youtu.be/dQw4w9WgXcQ --transcript
```

Only channel summary + latest videos:

```bash
youtube https://www.youtube.com/watch?v=dQw4w9WgXcQ --channel --subscribers --channel-videos
```

JSON output:

```bash
youtube https://www.youtube.com/watch?v=dQw4w9WgXcQ --json
```

## Notes

- YouTube Data API does not expose public dislike counts for normal videos anymore.
- Transcript depends on whether captions are available for that video.
- For channel URLs (`/channel/...`, `/@handle`, `/user/...`), channel-first mode is used.

