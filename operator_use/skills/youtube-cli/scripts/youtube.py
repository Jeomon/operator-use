#!/usr/bin/env python3
"""YouTube CLI for video/channel stats + transcript retrieval.

Requires:
  - YOUTUBE_API_KEY in environment or --api-key

Examples:
  youtube https://www.youtube.com/watch?v=dQw4w9WgXcQ --transcript --likes --views
  youtube https://www.youtube.com/@GoogleDevelopers --channel --subscribers --channel-videos
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
from dotenv import load_dotenv

API_BASE = "https://www.googleapis.com/youtube/v3"


def _load_env_candidates() -> None:
    script_dir = Path(__file__).resolve().parent
    skill_dir = script_dir.parent
    cwd = Path.cwd().resolve()
    project_root = script_dir.parents[3]
    workspaces_root = Path.home() / ".operator-use" / "workspaces"

    candidates: list[Path] = [
        # Primary project-level env (Operator/.env)
        project_root / ".env",
        # Skill-local env fallbacks
        skill_dir / ".env",
        script_dir / ".env",
        # Current execution cwd env
        cwd / ".env",
    ]

    # Optional explicit workspace hints.
    workspace_hint = os.environ.get("OPERATOR_WORKSPACE")
    if workspace_hint:
        candidates.append(Path(workspace_hint).expanduser().resolve() / ".env")

    agent_hint = os.environ.get("OPERATOR_AGENT_ID")
    if agent_hint:
        candidates.append(workspaces_root / agent_hint / ".env")

    # If cwd is inside ~/.operator-use/workspaces/<agent>/..., load that agent env.
    try:
        cwd_rel = cwd.relative_to(workspaces_root)
        parts = cwd_rel.parts
        if parts:
            candidates.append(workspaces_root / parts[0] / ".env")
    except Exception:
        pass

    # Keep parent traversal as broad fallback.
    for parent in cwd.parents:
        candidates.append(parent / ".env")

    seen: set[str] = set()
    for path in candidates:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        if path.exists() and path.is_file():
            load_dotenv(path, override=False)


def _api_get(endpoint: str, api_key: str, params: dict[str, Any]) -> dict[str, Any]:
    full_params = {"key": api_key, **params}
    url = f"{API_BASE}/{endpoint}"
    with httpx.Client(timeout=20) as client:
        response = client.get(url, params=full_params)
    if response.status_code != 200:
        raise RuntimeError(
            f"YouTube API error ({response.status_code}) for {endpoint}: {response.text[:400]}"
        )
    return response.json()


def _extract_video_id(target: str) -> str | None:
    target = target.strip()
    if len(target) == 11 and "/" not in target and "?" not in target:
        return target

    parsed = urlparse(target)
    host = parsed.netloc.lower()
    path = parsed.path

    if host in {"youtu.be", "www.youtu.be"}:
        vid = path.strip("/").split("/")[0]
        return vid or None

    if "youtube.com" in host:
        if path == "/watch":
            query = parse_qs(parsed.query)
            vids = query.get("v")
            return vids[0] if vids else None
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 2 and parts[0] in {"shorts", "live", "embed"}:
            return parts[1]

    return None


def _extract_channel_url_info(target: str) -> dict[str, str]:
    parsed = urlparse(target.strip())
    host = parsed.netloc.lower()
    if "youtube.com" not in host:
        return {}

    parts = [p for p in parsed.path.split("/") if p]
    if not parts:
        return {}

    if parts[0] == "channel" and len(parts) >= 2:
        return {"channel_id": parts[1]}
    if parts[0] == "user" and len(parts) >= 2:
        return {"username": parts[1]}
    if parts[0].startswith("@"):
        return {"handle": parts[0]}
    if parts[0] == "c" and len(parts) >= 2:
        return {"custom_name": parts[1]}
    return {}


def _resolve_channel_id_from_url_info(api_key: str, info: dict[str, str]) -> str | None:
    if "channel_id" in info:
        return info["channel_id"]
    if "username" in info:
        data = _api_get(
            "channels",
            api_key,
            {"part": "id", "forUsername": info["username"], "maxResults": 1},
        )
        items = data.get("items", [])
        return items[0]["id"] if items else None

    query = info.get("handle") or info.get("custom_name")
    if query:
        data = _api_get(
            "search",
            api_key,
            {
                "part": "snippet",
                "q": query,
                "type": "channel",
                "maxResults": 1,
            },
        )
        items = data.get("items", [])
        if items:
            return items[0]["snippet"]["channelId"]
    return None


def _get_video(api_key: str, video_id: str) -> dict[str, Any]:
    data = _api_get(
        "videos",
        api_key,
        {
            "part": "snippet,statistics",
            "id": video_id,
        },
    )
    items = data.get("items", [])
    if not items:
        raise RuntimeError(f"Video not found for id: {video_id}")
    return items[0]


def _get_channel(api_key: str, channel_id: str) -> dict[str, Any]:
    data = _api_get(
        "channels",
        api_key,
        {
            "part": "snippet,statistics",
            "id": channel_id,
        },
    )
    items = data.get("items", [])
    if not items:
        raise RuntimeError(f"Channel not found for id: {channel_id}")
    return items[0]


def _list_channel_videos(api_key: str, channel_id: str, limit: int) -> list[dict[str, Any]]:
    data = _api_get(
        "search",
        api_key,
        {
            "part": "snippet",
            "channelId": channel_id,
            "type": "video",
            "order": "date",
            "maxResults": min(max(limit, 1), 50),
        },
    )
    videos: list[dict[str, Any]] = []
    for item in data.get("items", []):
        vid = item.get("id", {}).get("videoId")
        snip = item.get("snippet", {})
        if vid:
            videos.append(
                {
                    "video_id": vid,
                    "title": snip.get("title"),
                    "published_at": snip.get("publishedAt"),
                }
            )
    return videos


def _get_comments(api_key: str, video_id: str, limit: int) -> list[dict[str, Any]]:
    data = _api_get(
        "commentThreads",
        api_key,
        {
            "part": "snippet",
            "videoId": video_id,
            "order": "relevance",
            "maxResults": min(max(limit, 1), 100),
            "textFormat": "plainText",
        },
    )
    comments: list[dict[str, Any]] = []
    for item in data.get("items", []):
        top = item.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
        text = top.get("textDisplay")
        if text:
            comments.append(
                {
                    "author": top.get("authorDisplayName"),
                    "like_count": top.get("likeCount"),
                    "text": text,
                }
            )
    return comments


def _fetch_timedtext_json(video_id: str, lang: str, kind: str | None = None) -> str | None:
    params: dict[str, str] = {"v": video_id, "fmt": "json3", "lang": lang}
    if kind:
        params["kind"] = kind
    with httpx.Client(timeout=20) as client:
        resp = client.get("https://www.youtube.com/api/timedtext", params=params)
    if resp.status_code != 200 or not resp.text.strip():
        return None
    try:
        payload = resp.json()
    except Exception:
        return None
    events = payload.get("events", [])
    chunks: list[str] = []
    for ev in events:
        for seg in ev.get("segs", []):
            txt = (seg.get("utf8") or "").replace("\n", " ").strip()
            if txt:
                chunks.append(txt)
    joined = " ".join(chunks).strip()
    return joined or None


def _fetch_timedtext_xml(video_id: str, lang: str) -> str | None:
    params = {"v": video_id, "lang": lang}
    with httpx.Client(timeout=20) as client:
        resp = client.get("https://video.google.com/timedtext", params=params)
    if resp.status_code != 200 or not resp.text.strip():
        return None
    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError:
        return None
    chunks: list[str] = []
    for node in root.findall(".//text"):
        text = "".join(node.itertext()).replace("\n", " ").strip()
        if text:
            chunks.append(text)
    joined = " ".join(chunks).strip()
    return joined or None


def _get_transcript(video_id: str, lang: str) -> str | None:
    for kind in (None, "asr"):
        txt = _fetch_timedtext_json(video_id, lang=lang, kind=kind)
        if txt:
            return txt
    return _fetch_timedtext_xml(video_id, lang=lang)


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except Exception:
        return None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="youtube",
        description="Fetch YouTube video/channel stats and transcript from URL or ID.",
    )
    parser.add_argument("target", help="YouTube video URL/ID or channel URL")
    parser.add_argument("--api-key", dest="api_key", default=None, help="YouTube API key")

    parser.add_argument("--likes", action="store_true", help="Show video likes")
    parser.add_argument("--views", action="store_true", help="Show video views")
    parser.add_argument("--comments", action="store_true", help="Show top comments")
    parser.add_argument("--dislikes", action="store_true", help="Show dislikes (if available)")
    parser.add_argument("--transcript", action="store_true", help="Show transcript text")
    parser.add_argument("--channel", action="store_true", help="Show channel information")
    parser.add_argument("--subscribers", action="store_true", help="Show channel subscribers")
    parser.add_argument("--channel-videos", action="store_true", help="List recent videos")
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    parser.add_argument("--lang", default="en", help="Transcript language code (default: en)")
    parser.add_argument("--max-comments", type=int, default=10, help="Comments to return")
    parser.add_argument("--max-videos", type=int, default=10, help="Channel videos to return")
    parser.add_argument(
        "--max-transcript-chars",
        type=int,
        default=12000,
        help="Trim transcript length in output",
    )
    return parser


def _needs_any_flags(args: argparse.Namespace) -> bool:
    return any(
        [
            args.likes,
            args.views,
            args.comments,
            args.dislikes,
            args.transcript,
            args.channel,
            args.subscribers,
            args.channel_videos,
        ]
    )


def _require_api_key(args: argparse.Namespace) -> str:
    _load_env_candidates()
    api_key = args.api_key or os.environ.get("YOUTUBE_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise SystemExit(
            "Missing API key. Set YOUTUBE_API_KEY (or GOOGLE_API_KEY) or pass --api-key."
        )
    return api_key


def _format_text(result: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"Input: {result.get('input')}")

    resolved = result.get("resolved", {})
    if resolved.get("video_id"):
        lines.append(f"Video ID: {resolved['video_id']}")
    if resolved.get("channel_id"):
        lines.append(f"Channel ID: {resolved['channel_id']}")

    notes = result.get("notes") or []
    if notes:
        lines.append("Notes:")
        for n in notes:
            lines.append(f"- {n}")

    video = result.get("video")
    if video:
        lines.append("")
        lines.append("Video:")
        for k in ("title", "channel_title", "published_at", "views", "likes", "comments_count"):
            if k in video:
                lines.append(f"- {k}: {video[k]}")
        if "dislikes" in video:
            lines.append(f"- dislikes: {video.get('dislikes')}")

    channel = result.get("channel")
    if channel:
        lines.append("")
        lines.append("Channel:")
        for k in ("title", "subscribers", "total_videos", "total_views"):
            if k in channel:
                lines.append(f"- {k}: {channel[k]}")

    vids = result.get("channel_videos")
    if vids:
        lines.append("")
        lines.append("Recent Channel Videos:")
        for item in vids:
            lines.append(f"- {item.get('title')} ({item.get('video_id')})")

    comments = result.get("comments")
    if comments:
        lines.append("")
        lines.append("Top Comments:")
        for idx, c in enumerate(comments, start=1):
            lines.append(f"{idx}. {c.get('author')}: {c.get('text')}")

    transcript = result.get("transcript")
    if transcript and transcript.get("text"):
        lines.append("")
        lines.append("Transcript:")
        lines.append(transcript["text"])

    return "\n".join(lines)


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    api_key = _require_api_key(args)
    show_all = not _needs_any_flags(args)

    result: dict[str, Any] = {
        "input": args.target,
        "resolved": {},
        "notes": [],
    }

    try:
        video_id = _extract_video_id(args.target)
        channel_url_info = _extract_channel_url_info(args.target)
        channel_id: str | None = None

        if video_id:
            result["resolved"]["video_id"] = video_id
            v = _get_video(api_key, video_id)
            stats = v.get("statistics", {})
            snippet = v.get("snippet", {})
            channel_id = snippet.get("channelId")
            if channel_id:
                result["resolved"]["channel_id"] = channel_id

            video_payload = {
                "title": snippet.get("title"),
                "channel_title": snippet.get("channelTitle"),
                "published_at": snippet.get("publishedAt"),
                "views": _int_or_none(stats.get("viewCount")),
                "likes": _int_or_none(stats.get("likeCount")),
                "comments_count": _int_or_none(stats.get("commentCount")),
                "dislikes": None,
            }
            if show_all or args.likes or args.views or args.dislikes:
                result["video"] = video_payload
            if args.dislikes or show_all:
                result["notes"].append(
                    "Public dislike count is not available in YouTube Data API for most videos."
                )

            if args.comments or show_all:
                result["comments"] = _get_comments(api_key, video_id, limit=args.max_comments)

            if args.transcript or show_all:
                transcript = _get_transcript(video_id, lang=args.lang)
                if transcript:
                    result["transcript"] = {
                        "language": args.lang,
                        "text": transcript[: max(args.max_transcript_chars, 100)],
                    }
                else:
                    result["transcript"] = {
                        "language": args.lang,
                        "text": None,
                    }
                    result["notes"].append("Transcript not available for this video/language.")
        else:
            channel_id = _resolve_channel_id_from_url_info(api_key, channel_url_info)
            if channel_id:
                result["resolved"]["channel_id"] = channel_id

        if channel_id and (show_all or args.channel or args.subscribers or args.channel_videos):
            c = _get_channel(api_key, channel_id)
            c_stats = c.get("statistics", {})
            c_snip = c.get("snippet", {})
            result["channel"] = {
                "title": c_snip.get("title"),
                "subscribers": _int_or_none(c_stats.get("subscriberCount")),
                "total_videos": _int_or_none(c_stats.get("videoCount")),
                "total_views": _int_or_none(c_stats.get("viewCount")),
            }

            if args.channel_videos or show_all:
                result["channel_videos"] = _list_channel_videos(
                    api_key, channel_id, limit=args.max_videos
                )

        if not result["resolved"]:
            raise RuntimeError(
                "Could not resolve a video or channel from input. "
                "Pass a valid YouTube video URL/ID or channel URL."
            )

        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(_format_text(result))
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
