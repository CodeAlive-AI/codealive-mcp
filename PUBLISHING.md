# CodeAlive MCP Publishing Guide

This document explains how to publish new versions of the CodeAlive MCP server.

## 🚀 Quick Start

To publish a new version:

1. **Update version** in `pyproject.toml`:
   ```toml
   version = "0.3.0"  # Change this number
   ```

2. **Commit and push**:
   ```bash
   git add pyproject.toml
   git commit -m "Bump version to 0.3.0"
   git push
   ```

3. **Done!** The rest happens automatically.

## 🤖 What Happens Automatically

When you push a version change to `main`, the GitHub Action:

1. ✅ **Tests** - Runs pytest with coverage
2. 🏗️ **Builds** - Creates Docker image for multiple platforms
3. 🏷️ **Tags** - Creates git tag `v0.3.0` automatically
4. 📦 **Publishes** - Pushes to:
   - GitHub Container Registry (`ghcr.io/codealive-ai/codealive-mcp`)
   - MCP Registry (`io.github.codealive-ai/codealive-mcp`)
5. 📝 **Releases** - Creates GitHub release with usage examples

## 📋 Hybrid Deployment

Users can access your MCP server in two ways:

### Option 1: Docker Container (Local)
```json
{
  "name": "io.github.codealive-ai/codealive-mcp",
  "transport": {
    "type": "stdio",
    "command": "docker",
    "args": [
      "run", "--rm", "-i", "-e", "CODEALIVE_API_KEY",
      "ghcr.io/codealive-ai/codealive-mcp:v0.3.0"
    ]
  },
  "env": {
    "CODEALIVE_API_KEY": "your-api-key-here"
  }
}
```

> Replace `v0.3.0` with the version being published.

### Option 2: Remote HTTP Endpoint (Cloud)
```json
{
  "name": "io.github.codealive-ai/codealive-mcp",
  "transport": {
    "type": "http",
    "url": "https://mcp.codealive.ai/api"
  },
  "headers": {
    "Authorization": "Bearer your-api-key-here"
  }
}
```

## 📁 Project Structure

```
.github/workflows/main.yml    # Single workflow handles everything
server.json                   # MCP Registry configuration (hybrid)
pyproject.toml               # Python package config (version source)
Dockerfile                   # Container with MCP validation label
```

## 🔧 Configuration Files

### `server.json` (MCP Registry)
- **Hybrid deployment** with both Docker and remote options
- **Auto-synced version** from pyproject.toml
- **Validation** ensures proper structure

### `pyproject.toml` (Source of Truth)
- **Version control** - change here to trigger releases
- **Dependencies** and Python package metadata

### `.github/workflows/main.yml` (Automation)
- **Smart publishing** - only when version changes
- **Multi-platform** Docker builds (amd64 + arm64)
- **OIDC authentication** for MCP Registry

## 🛠️ Manual Testing

Test locally before pushing:

```bash
# Validate server.json structure
python -c "
import json
with open('server.json') as f:
    data = json.load(f)
print('✓ Valid JSON')
print(f'Name: {data[\"name\"]}')
print(f'Version: {data[\"version\"]}')
"

# Run tests
python -m pytest src/tests/ -v

# Build Docker image locally
docker build -t codealive-mcp-test .
```

## 🔍 Monitoring

- **GitHub Actions**: Check workflow runs
- **Releases**: View at https://github.com/CodeAlive-AI/codealive-mcp/releases
- **Docker Images**: Check https://github.com/CodeAlive-AI/codealive-mcp/pkgs/container/codealive-mcp
- **MCP Registry**: Server appears as `io.github.codealive-ai/codealive-mcp`

## ❓ Troubleshooting

**Workflow didn't trigger publishing?**
- Check if version in `pyproject.toml` actually changed
- Ensure push was to `main` branch
- Look for existing git tag with same version

**MCP Registry publishing failed?**
- Verify `server.json` structure is valid
- Check GitHub OIDC permissions are enabled
- Ensure namespace `io.github.codealive-ai` is correct

**Docker build failed?**
- Test locally: `docker build .`
- Check platform compatibility (we build for amd64 + arm64)
- Verify base image and dependencies are available
