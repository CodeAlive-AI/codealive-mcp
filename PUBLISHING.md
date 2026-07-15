# CodeAlive MCP publishing guide

Releases are created manually through the `Release` GitHub Actions workflow. The
workflow tests the exact locked graph, publishes multi-architecture Docker images,
publishes `server.json` to the MCP Registry, packages the Claude Desktop MCPB
extension, and attaches it to the GitHub release.

## Release policy

- A versioned dependency, runtime, build tool, or GitHub Action must have been
  released more than seven days before it is adopted.
- Python resolution enforces this with `tool.uv.exclude-newer = "7 days"`.
- Direct dependencies, CI runtimes, MCPB, MCP Publisher, and Actions are pinned.
  Action pins use full commit SHAs; the MCP Publisher archive has an exact SHA-256.
- Official container images may receive security rebuilds without changing the
  Python release. The Dockerfile therefore pins the Python patch release and Debian
  suite while accepting upstream security rebuilds of that tag.

## Prepare a release

1. Select the latest eligible versions and confirm their publication dates.
2. Update the exact pins in `pyproject.toml` and the workflow `env` blocks.
3. Regenerate and check the lock with the repository's pinned uv version:

   ```bash
   uvx --from uv==0.11.28 uv lock --upgrade
   uvx --from uv==0.11.28 uv lock --check
   ```

4. Set the next release in all committed fallback/package metadata:

   - `pyproject.toml` → `tool.setuptools_scm.fallback_version`
   - `manifest.json` → `version`
   - `server.json` → `version`

5. Run the release-equivalent checks:

   ```bash
   uvx --from uv==0.11.28 uv sync --locked --extra test
   uvx --from uv==0.11.28 uv run python -m pytest src/tests/ -v --cov=src
   uvx --from uv==0.11.28 uv audit --locked
   make smoke-test
   npx -y @anthropic-ai/mcpb@2.1.2 validate manifest.json
   npx -y @anthropic-ai/mcpb@2.1.2 pack . dist/codealive-mcp.mcpb
   python scripts/verify_mcpb.py dist/codealive-mcp.mcpb
   docker build --build-arg VERSION=3.0.2 -t codealive-mcp:release-check .
   ```

6. Commit and push the verified changes to `main`. Wait for CI and CodeQL to pass.

## Publish

Run `Release` from GitHub Actions with the exact version, for example `3.0.2`.
The protected `release` environment may require approval. Do not create the tag by
hand: the workflow creates it only after the Docker push succeeds.

The workflow publishes:

- `ghcr.io/codealive-ai/codealive-mcp:<version>`, `v<version>`, `latest`, and a
  commit-SHA tag for `linux/amd64` and `linux/arm64`;
- `io.github.CodeAlive-AI/codealive-mcp` in the MCP Registry;
- Git tag and GitHub release `v<version>`;
- `codealive-mcp.mcpb`, ready to install in Claude Desktop.

## Post-release verification

Confirm that the GitHub release contains the MCPB asset, both container platforms
resolve, the MCP Registry reports the new version as latest, and a clean MCPB
installation starts successfully. Existing Claude Desktop users should install the
new MCPB and restart Claude Desktop.

Remote clients continue to use `https://mcp.codealive.ai/api` with an
`Authorization: Bearer <key>` header.
