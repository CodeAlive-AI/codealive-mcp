# CodeAlive Context Engine

An [agent skill](https://skills.sh/) that gives your AI coding assistant semantic understanding of your entire codebase — not just the files open in front of you, but every indexed repository, dependency, and workspace in your organization.

Works with Claude Code, Cursor, GitHub Copilot, Windsurf, Gemini CLI, Codex, Goose, Amp, Roo Code, and [other agents](https://skills.sh/docs) that support the SKILL.md format.

**Without this skill**, your agent can only see files you explicitly open or search for with exact keywords.
**With this skill**, your agent understands codebase architecture, traces cross-service patterns, and answers questions about code it hasn't directly read.

## Quick Start

### 1. Install

**Via [skills.sh](https://skills.sh/)** (recommended):

```bash
npx skills add CodeAlive-AI/codealive-skills@codealive-context-engine
```

This auto-detects your agent and installs the skill to the right location.

**Manual install** — copy the skill folder to your agent's skills directory:

| Agent | Project scope | User scope (all projects) |
|-------|--------------|--------------------------|
| Claude Code | `.claude/skills/` | `~/.claude/skills/` |
| Cursor | `.cursor/skills/` | `~/.cursor/skills/` |
| GitHub Copilot | `.github/skills/` | `~/.copilot/skills/` |
| Windsurf | `.windsurf/skills/` | `~/.codeium/windsurf/skills/` |
| Gemini CLI | `.gemini/skills/` | `~/.gemini/skills/` |
| Codex | `.codex/skills/` | `~/.codex/skills/` |
| Goose | `.goose/skills/` | `~/.config/goose/skills/` |
| Amp | `.agents/skills/` | `~/.config/agents/skills/` |
| Roo Code | `.roo/skills/` | `~/.roo/skills/` |
| OpenCode | `.opencode/skill/` | `~/.config/opencode/skill/` |

### 2. Set up

Run the interactive setup — it will ask for your API key, store it securely, and verify everything works:

```bash
python setup.py
```

```
  CodeAlive Context Engine — Setup
  ======================================

  [1/3] Checking for existing API key...
  [2/3] API key required.
        Get yours at: https://app.codealive.ai/settings/api-keys

        Paste your API key (input is hidden): ****
        Key verified. Connected. 7 data sources available.
  [3/3] Storing API key...
        Saved to macOS Keychain.

  --------------------------------------
  Ready! Start your agent and ask:

    "How is authentication implemented?"
    "Show me error handling patterns"
    "Explain the payment processing flow"
```

The setup auto-detects your OS and stores the key in the right place (macOS Keychain, Linux secret-tool, or Windows Credential Manager).

### 3. Use

Start your AI coding agent and ask naturally. No special commands needed:

- *"How is user authentication implemented?"*
- *"Show me error handling patterns across our microservices"*
- *"What libraries do we use for caching?"*
- *"Help me understand the payment processing flow"*
- *"Find similar features to guide my rate limiting implementation"*

## Prerequisites

- Python 3.8+ (no third-party packages — stdlib only)
- A [CodeAlive](https://app.codealive.ai) account with indexed repositories
- API key from [app.codealive.ai/settings/api-keys](https://app.codealive.ai/settings/api-keys)

## How It Works

The skill provides your agent with four tools that it picks from automatically:

| Tool | Speed | Cost | What It Does |
|------|-------|------|--------------|
| **List Data Sources** | Instant | Free | Shows which repositories and workspaces are indexed |
| **Search** | Fast | Low | Finds code locations, file paths, and snippets |
| **Chat with Codebase** | Slower | Higher | Returns synthesized answers using server-side AI |
| **Explore** | Slower | Higher | Multi-step workflows combining search and chat |

Search is the default starting point — fast and cheap. Chat with Codebase is used when the agent needs a synthesized explanation rather than raw code locations.

## Alternative Setup Methods

The `setup.py` script is the recommended way. If you prefer manual configuration:

**Environment variable (all platforms):**
```bash
export CODEALIVE_API_KEY="your_key_here"
```

**macOS Keychain:**
```bash
security add-generic-password -a "$USER" -s "codealive-api-key" -w "YOUR_API_KEY"
```

**Linux (secret-tool):**
```bash
secret-tool store --label="CodeAlive API Key" service codealive-api-key
```

**Windows Credential Manager:**
```cmd
cmdkey /generic:codealive-api-key /user:codealive /pass:"YOUR_API_KEY"
```

**Self-hosted instance:**
```bash
export CODEALIVE_BASE_URL="https://your-instance.example.com"
```

**Non-interactive setup** (CI/CD, scripted environments):
```bash
python setup.py --key "YOUR_API_KEY"
python setup.py --key "YOUR_API_KEY" --env   # prints env var instruction instead of storing in credential manager
```

## Troubleshooting

| Error | Fix |
|-------|-----|
| "API key not found" | Run `python setup.py` to configure your key |
| "Authentication failed (401)" | Key is invalid or expired. Get a new one at [app.codealive.ai/settings/api-keys](https://app.codealive.ai/settings/api-keys) |
| "Data sources not found" | Repository name doesn't match. Run `python scripts/datasources.py` to see available names |
| "Cannot connect" | Check network. For self-hosted instances, verify `CODEALIVE_BASE_URL` |
| No results | Be more specific: *"error handling in API controllers"* not just *"error handling"* |

## File Structure

```
codealive-context-engine/
  setup.py                  # Interactive setup (start here)
  SKILL.md                  # Skill definition (read by your agent)
  README.md                 # This file
  scripts/
    datasources.py          # List indexed repos and workspaces
    search.py               # Semantic code search
    chat.py                 # AI-powered codebase Q&A
    explore.py              # Multi-step exploration workflows
    lib/
      api_client.py         # API client (auth + HTTP)
  references/
    query-patterns.md       # Effective query writing guide
    workflows.md            # Step-by-step workflow examples
```

## Platform Support

| Platform | Credential Store | Status |
|----------|-----------------|--------|
| macOS | Keychain | Fully supported |
| Linux | freedesktop Secret Service | Fully supported |
| Windows | Credential Manager | Fully supported |

All platforms also support the `CODEALIVE_API_KEY` environment variable.

No third-party Python packages required.
