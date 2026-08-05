# MCP CI Workflow Rules

- Pin every external action to a full commit SHA and keep the release tag in a comment.
- Do not use floating Python or Docker setup actions in CI/release workflows.
- When updating dependency-related workflow steps, prefer reproducible installs over convenience aliases.
