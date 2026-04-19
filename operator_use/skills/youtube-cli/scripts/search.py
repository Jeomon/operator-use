import argparse
from youtubesearchpython import VideosSearch
import json

def search_videos(query, limit=5, language="en", region="US"):
    # This library defaults to 'video' type search
    videos_search = VideosSearch(query, limit=limit, language=language, region=region)
    results = videos_search.result()
    print(json.dumps(results, indent=2))

def main():
    parser = argparse.ArgumentParser(description="YouTube search processor")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--limit", type=int, default=5, help="Number of results to return")
    parser.add_argument("--language", default="en", help="Language code (default: en)")
    parser.add_argument("--region", default="US", help="Region code (default: US)")
    parser.add_argument("--output", "-o", help="Output file path to save JSON result")

    args = parser.parse_args()

    results = VideosSearch(args.query, limit=args.limit, language=args.language, region=args.region).result()

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2)
    else:
        print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()
