---
name: youtube-cli
description: Search for videos, extract metadata, retrieve transcripts, and fetch comments from YouTube. Use when analyzing video content for research, summarizing long-form content, or gathering information from YouTube URLs.
---

## What This Skill Does
This skill uses `yt-dlp` to fetch metadata (title, uploader, views, duration, likes, optional comments) and `youtube-transcript-api` to retrieve captions for a YouTube video. It also includes search functionality via `yt-dlp`.

## Search Videos
1. Use the script `skills/youtube-cli/scripts/search.py`.
2. Run the command: `python skills/youtube-cli/scripts/search.py "<query>" [flags]`
3. Available flags: `--limit <N>`, `--json`, `--output` (`-o`).
4. By default, output is markdown. Use `--json` for raw JSON and `--output <path>` to save to file.

## Inspect a Video
1. Use the script `skills/youtube-cli/scripts/video.py`.
2. Run either:
   - `python skills/youtube-cli/scripts/video.py <video_id> [flags]`
   - `python skills/youtube-cli/scripts/video.py --url "<youtube_url>" [flags]`
3. Available flags: `--title`, `--uploader`, `--duration`, `--views`, `--likes`, `--transcript`, `--description`, `--comments`, `--json`, `--output` (`-o`).
4. If no field flags are provided, defaults are: `title`, `uploader`, `duration`, `views`.

## Steps
1. Use the script `skills/youtube-cli/scripts/search.py` via the terminal. Run `python skills/youtube-cli/scripts/search.py --help` for usage details.
2. Use the script `skills/youtube-cli/scripts/video.py` via the terminal. Run `python skills/youtube-cli/scripts/video.py --help` for usage details.
3. For long transcripts, descriptions, or comment threads, always use the `--output` flag to save the data to a file rather than printing to the terminal to avoid truncation.
4. If a video is part of a series or you need to process multiple videos, chain these calls as necessary.

## Common Failures
- **400 Bad Request**: Often caused by outdated `yt-dlp` or dependency issues.
- **No transcript available**: Some videos do not have captions, or the transcript service is disabled.
- **Argument error**: Use either positional `video_id` or `--url`; do not pass a URL as positional text with extra unsupported flags.
- **Terminal Truncation**: For long outputs, always use the `--output` flag.

## Pro-Tips for Research
- When researching, first search for the topic using `search.py` to identify the most relevant videos.
- Use `video.py` on the top results to extract metadata and assess relevance before extracting full transcripts.
- If you need to analyze a large number of videos, script the interaction using the terminal to batch process them.
