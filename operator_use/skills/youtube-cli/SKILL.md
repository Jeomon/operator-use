---
name: youtube-cli
description: Extract information and transcript from a YouTube video given its ID. Use when the agent needs to analyze video content, summarize videos, or retrieve specific details from YouTube URLs.
---

## What This Skill Does
This skill uses `yt-dlp` to fetch metadata (title, uploader, views, duration) and `youtube-transcript-api` to retrieve the closed captions for a given YouTube video. It also includes search functionality using `youtube-search-python`.

## Search Videos
1. Use the script `skills/youtube-cli/scripts/search.py`.
2. Run the command: `python skills/youtube-cli/scripts/search.py "<query>" [flags]`
3. Available flags: `--limit <N>`, `--language <code>`, `--region <code>`, `--output` (`-o`).
4. The script outputs the top search results in JSON format. Use `--output <path>` to save the results to a file.

## Steps
1. Use the script `skills/youtube-cli/scripts/video.py` via the terminal.
2. Run the command: `python skills/youtube-cli/scripts/video.py <video_id> [flags]`
3. Available flags: `--title`, `--uploader`, `--duration`, `--views`, `--likes`, `--transcript`, `--description`, `--comments`, `--output` (`-o`).
4. If no flags are specified, it defaults to: `--title`, `--uploader`, `--duration`, `--views`.
5. Run `python skills/youtube-cli/scripts/video.py --help` for usage details.
6. The script outputs the requested information in JSON format. Use `--output <path>` to save the transcript text, description text, or comments (as JSON) directly to a file. Use this to avoid terminal truncation for long transcripts or descriptions.

## Common Failures
- **400 Bad Request**: Often caused by outdated `pytube` libraries; this skill uses `yt-dlp` as a more robust alternative.
- **No transcript available**: Some videos do not have captions or the transcript service is disabled for that video.
