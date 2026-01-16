# Deployment Guide

This guide covers publishing CodeAlive MCP to the MCP Registry.

## Prerequisites

### Install mcp-publisher

Build from source (documented install methods like `brew install` and `install.sh` are not available):

```bash
git clone https://github.com/modelcontextprotocol/registry.git
cd registry
make publisher
```

The binary will be at `./bin/mcp-publisher`.

### GitHub org membership (for org repos)

Your organization membership must be public:
1. Go to https://github.com/orgs/CodeAlive-AI/people
2. Find your username and set visibility to "Public"

## Publishing to MCP Registry

### 1. Login with GitHub

```bash
./bin/mcp-publisher login github
```

Follow the device authorization flow:
1. Go to the URL shown (e.g., https://github.com/login/device)
2. Enter the code displayed
3. Authorize the application

### 2. Update server.json

Before publishing, update `server.json`:

1. **Bump the version** field to match your release
2. **Use the latest schema** (currently `2025-12-11`)
3. **Update package identifier** with new version tag

Example `server.json` structure:
```json
{
  "$schema": "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json",
  "name": "io.github.CodeAlive-AI/codealive-mcp",
  "version": "0.4.7",
  ...
  "packages": [
    {
      "registryType": "oci",
      "identifier": "ghcr.io/codealive-ai/codealive-mcp:0.4.7",
      "runtimeHint": "docker",
      ...
    }
  ]
}
```

**Important notes:**
- OCI packages must NOT have a separate `version` field inside the package object - the version is embedded in the `identifier` tag
- Schema version must be current (check [changelog](https://github.com/modelcontextprotocol/registry/blob/main/docs/reference/server-json/CHANGELOG.md))

### 3. Publish

```bash
cd /path/to/codealive-mcp
/path/to/registry/bin/mcp-publisher publish
```

On success:
```
Publishing to https://registry.modelcontextprotocol.io...
✓ Successfully published
✓ Server io.github.CodeAlive-AI/codealive-mcp version 0.4.7
```

## Troubleshooting

### "not authenticated"
Re-run login:
```bash
./bin/mcp-publisher login github
```

### "403: your GitHub account doesn't have permission"
Make your organization membership public:
1. Go to https://github.com/orgs/CodeAlive-AI/people
2. Find your username
3. Change visibility to "Public"
4. Re-login and try again

### "deprecated schema detected"
Update `$schema` in `server.json` to the current version. Check the [migration checklist](https://github.com/modelcontextprotocol/registry/blob/main/docs/reference/server-json/CHANGELOG.md#migration-checklist-for-publishers).

### "OCI packages must not have 'version' field"
Remove the `version` field from inside the `packages` array. The version should only appear in the `identifier` tag (e.g., `ghcr.io/codealive-ai/codealive-mcp:0.4.7`).

## Version Guidelines

- **Patch** (0.4.6 → 0.4.7): Bug fixes, minor improvements
- **Minor** (0.4.0 → 0.5.0): New features, enhancements
- **Major** (0.x.x → 1.0.0): Breaking changes, major releases

## Related Resources

- [MCP Registry](https://registry.modelcontextprotocol.io/)
- [server.json Schema Changelog](https://github.com/modelcontextprotocol/registry/blob/main/docs/reference/server-json/CHANGELOG.md)
- [MCP Registry GitHub](https://github.com/modelcontextprotocol/registry)
