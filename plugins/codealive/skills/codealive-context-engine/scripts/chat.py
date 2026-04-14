#!/usr/bin/env python3
"""
CodeAlive Consultant - AI-powered codebase Q&A

Ask questions about code architecture, implementation details, patterns, and best practices.
Works across your entire indexed codebase ecosystem.

Usage:
    python chat.py "How does authentication work?" my-repo
    python chat.py "Explain the database schema" workspace:backend-team
    python chat.py "What's the best way to add caching?" --continue CONV_ID

Examples:
    # Ask about current project
    python chat.py "How is user authentication implemented?" my-backend

    # Ask across multiple repos
    python chat.py "How do services communicate?" service-a service-b

    # Ask about dependencies/libraries
    python chat.py "How does lodash debounce work internally?" lodash

    # Continue previous conversation
    python chat.py "What about error handling?" --continue conv_abc123

    # Cross-project learning
    python chat.py "Show me authentication patterns across our org" workspace:all-backend
"""

import sys
import json
from pathlib import Path

# Add lib directory to path
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from api_client import CodeAliveClient


def main():
    """CLI interface for codebase consultant."""
    if len(sys.argv) < 2:
        print("Error: Missing required arguments.", file=sys.stderr)
        print("Usage: python chat.py <question> <data_source> [data_source2...] [--continue <conversation_id>]", file=sys.stderr)
        sys.exit(1)

    if sys.argv[1] == "--help":
        print(__doc__)
        sys.exit(0)

    question = sys.argv[1]
    conversation_id = None
    data_sources = []

    # Parse arguments
    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--continue" and i + 1 < len(sys.argv):
            conversation_id = sys.argv[i + 1]
            i += 2
        elif arg == "--conversation-id" and i + 1 < len(sys.argv):
            conversation_id = sys.argv[i + 1]
            i += 2
        else:
            data_sources.append(arg)
            i += 1

    if not conversation_id and not data_sources:
        print("Error: Either data sources or --continue <conversation_id> is required.", file=sys.stderr)
        print("Run datasources.py to see available sources.", file=sys.stderr)
        sys.exit(1)

    try:
        client = CodeAliveClient()

        print(f"💬 Question: {question}", file=sys.stderr)
        if conversation_id:
            print(f"🔄 Continuing conversation: {conversation_id}", file=sys.stderr)
        else:
            print(f"📚 Analyzing: {', '.join(data_sources)}", file=sys.stderr)
        print(file=sys.stderr)
        print("🤔 Thinking...", file=sys.stderr)
        print(file=sys.stderr)

        result = client.chat(
            question=question,
            data_sources=data_sources if data_sources else None,
            conversation_id=conversation_id
        )

        print("="*80)
        print(result["answer"])
        print("="*80)

        if result.get("conversation_id"):
            print()
            print(f"💾 Conversation ID: {result['conversation_id']}")
            print(f"   Use --continue {result['conversation_id']} to ask follow-up questions")

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
