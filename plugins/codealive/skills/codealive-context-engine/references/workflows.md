# CodeAlive Workflows

Complete workflows for common code exploration scenarios using CodeAlive.

## Table of Contents
- [Initial Codebase Exploration](#initial-codebase-exploration)
- [Understanding Existing Features](#understanding-existing-features)
- [Planning New Features](#planning-new-features)
- [Dependency Deep-Dive](#dependency-deep-dive)
- [Cross-Project Pattern Discovery](#cross-project-pattern-discovery)
- [Debugging & Investigation](#debugging--investigation)
- [Technology Evaluation](#technology-evaluation)
- [Onboarding to New Codebases](#onboarding-to-new-codebases)

---

## Initial Codebase Exploration

**Goal:** Build a mental model of an unknown codebase

### Step 1: Discover Available Code
```bash
python datasources.py
```

Review output to understand:
- What repositories are indexed
- What workspaces group related repos
- Which data sources to use for exploration

### Step 2: Understand Entry Points
```bash
python search.py "main application entry point, startup initialization" my-backend-repo
```

### Step 3: Explore Key Features
```bash
python search.py "main features, core capabilities, major services" my-backend-repo
```

### Step 4: Get Architectural Overview Only If Needed
```bash
python chat.py "Provide an architectural overview of this codebase. What are the main components, how do they interact, and what's the tech stack?" my-backend-repo
```

### Step 5: Understand Data Models
```bash
python search.py "database models, schemas, entity definitions" my-backend-repo
```

**Progressive Discovery:**
- Start with broad architectural questions
- Narrow to specific components
- Drill into implementation details

---

## Understanding Existing Features

**Goal:** Trace a feature implementation across all layers

### Example: Understanding User Authentication

#### Step 1: Start with Search
```bash
python search.py "user authentication, login flow, session management" my-backend
python grep.py "refresh token" my-backend
```

#### Step 2: Use Chat Only If You Still Need Synthesis
```bash
python chat.py "How is user authentication implemented? Describe the flow from login to session management" my-backend
```

Save conversation_id for follow-up questions.

#### Step 3: Trace Through Layers
```bash
# API Layer
python search.py "login controller, authentication route handler" my-backend

# Service Layer
python search.py "authentication service, user validation logic" my-backend

# Database Layer
python search.py "user model, credentials storage" my-backend
```

#### Step 4: Understand Security Measures
```bash
python chat.py "What security measures are in place for authentication? (hashing, tokens, sessions)" --continue CONV_ID
```

#### Step 5: Find Related Features
```bash
python search.py "password reset, email verification, 2FA" my-backend
```

**Pattern:** API → Service → Repository/Database → Related Features

---

## Planning New Features

**Goal:** Find patterns and integration points before implementing

### Example: Adding Rate Limiting

#### Step 1: Check for Existing Similar Features
```bash
python search.py "rate limiting, request throttling, API quotas" my-backend workspace:all-backend
```

#### Step 2: Understand Middleware Patterns
```bash
python chat.py "What middleware patterns are used in this codebase? How are cross-cutting concerns like logging and authentication handled?" my-backend
```

#### Step 3: Find Integration Points
```bash
python search.py "middleware registration, request pipeline configuration" my-backend
```

#### Step 4: Check Dependencies
```bash
python search.py "express-rate-limit, rate-limiter-flexible, existing rate limiting libraries" workspace:all-backend
```

#### Step 5: Get Implementation Guidance
```bash
python chat.py "Based on existing patterns in the codebase, what's the recommended way to implement rate limiting? What components do I need to modify?" --continue CONV_ID
```

**Output:** Clear implementation plan with file locations and integration points

---

## Dependency Deep-Dive

**Goal:** Understand how a library works and how it's used

### Example: Understanding axios Usage

#### Step 1: Find All Usage
```bash
python search.py "axios import, axios.create, axios usage patterns" my-frontend --include-content
```

#### Step 2: Understand Configuration
```bash
python search.py "axios configuration, base URL, default headers, interceptors" my-frontend
```

#### Step 3: Learn Internal Implementation
```bash
python chat.py "How does axios interceptor mechanism work internally? Show me the implementation details" axios-library
```

Note: Requires axios repository to be indexed

#### Step 4: Find Best Practices
```bash
python chat.py "What are the axios usage patterns in this codebase? Any best practices or common pitfalls?" my-frontend
```

#### Step 5: Compare with Alternatives
```bash
python search.py "fetch API, got, node-fetch, HTTP client libraries" workspace:all-frontend
python chat.py "Compare axios vs fetch usage in our codebase. When is each used and why?" workspace:all-frontend
```

**Use Case:** Replace MCP-based online documentation with real usage examples

---

## Cross-Project Pattern Discovery

**Goal:** Learn patterns from across your organization

### Example: Error Handling Patterns

#### Step 1: Broad Search Across Workspace
```bash
python search.py "error handling patterns, exception middleware, error logging" workspace:backend-team --mode deep
```

#### Step 2: Ask for Pattern Analysis
```bash
python chat.py "Analyze the different error handling patterns found in our microservices. What are the common approaches?" workspace:backend-team
```

#### Step 3: Find Best Examples
```bash
python chat.py "Which service has the best error handling implementation and why? Show me specific examples" --continue CONV_ID
```

#### Step 4: Identify Anti-Patterns
```bash
python chat.py "What error handling anti-patterns exist in our codebase that we should avoid?" --continue CONV_ID
```

**Output:** Pattern comparison, recommendations, and examples to follow

---

## Debugging & Investigation

**Goal:** Trace from symptom to root cause

### Example: Investigating Slow API Responses

#### Step 1: Find Related Code
```bash
python search.py "API performance, slow queries, request handling" my-api-service --include-content
```

#### Step 2: Investigate Database Queries
```bash
python search.py "database queries, ORM operations, N+1 problem" my-api-service
```

#### Step 3: Check for Known Issues
```bash
python chat.py "What could cause slow API responses in this codebase? Check for common performance issues like N+1 queries, missing indexes, or expensive operations" my-api-service
```

#### Step 4: Find Monitoring/Logging
```bash
python search.py "performance logging, request timing, profiling" my-api-service
```

#### Step 5: Get Debugging Strategy
```bash
python chat.py "How should I debug and fix this slow API issue? What should I check first and how can I trace the performance bottleneck?" --continue CONV_ID
```

**Pattern:** Symptom → Related Code → Common Causes → Debugging Strategy

---

## Technology Evaluation

**Goal:** Compare technologies by seeing real usage

### Example: Choosing a State Management Library

#### Step 1: Find Existing Usage
```bash
python search.py "Redux, MobX, Zustand, React Context state management" workspace:all-frontend --mode deep
```

#### Step 2: Analyze Implementation Complexity
```bash
python chat.py "Compare the state management solutions used across our frontend projects. Which ones are simpler to implement and maintain?" workspace:all-frontend
```

#### Step 3: Check Performance Patterns
```bash
python search.py "state management performance, re-render optimization" workspace:all-frontend
```

#### Step 4: Get Recommendation
```bash
python chat.py "Based on our codebase patterns and team's usage, which state management solution should we use for a new project and why?" --continue CONV_ID
```

**Output:** Data-driven technology decision based on real usage

---

## Onboarding to New Codebases

**Goal:** Quickly understand an unfamiliar project

### Day 1: Get Overview

```bash
# What does this do?
python chat.py "What is this project? What problem does it solve and what are its main features?" new-service

# How is it structured?
python chat.py "What's the project structure and organization? What are the main directories and their purposes?" --continue CONV_ID

# What's the tech stack?
python search.py "package.json, requirements.txt, go.mod, dependencies" new-service
```

### Day 2: Understand Core Features

```bash
# Find entry point
python search.py "main application entry point, startup sequence" new-service

# Understand data flow
python chat.py "How does data flow through the application? Trace a typical request from entry to exit" new-service

# Find key components
python search.py "core services, main controllers, important modules" new-service
```

### Day 3: Learn Development Practices

```bash
# Testing patterns
python search.py "test files, testing patterns, test setup" new-service

# Configuration
python search.py "configuration, environment variables, settings" new-service

# Deployment
python search.py "deployment configuration, CI/CD, build process" new-service
```

### Week 1: Deep Dive

```bash
# Feature-by-feature exploration
python search.py "user management" new-service --description-detail full
python search.py "API integration" new-service --description-detail full
python search.py "background jobs" new-service --description-detail full
```

**Progressive Learning:** Overview → Core Features → Development Practices → Deep Dives

---

## Pro Tips

### Conversation Continuity
Always save `conversation_id` for follow-up questions:
```bash
python chat.py "Initial question" my-repo
# Note the conversation_id in output
python chat.py "Follow-up question" --continue CONV_ID
```

### Workspace vs Repository
- **Repository:** Targeted, specific search
- **Workspace:** Broad, cross-project patterns

```bash
# Specific
python search.py "auth logic" my-backend-api

# Broad
python search.py "authentication patterns" workspace:all-backend
```

### Search Mode Strategy
1. Start with `auto` mode (default)
2. Use `deep` only if auto misses results
3. Use `fast` for known terms/names

### Content Inclusion Strategy
- **Current repo:** `include_content=false` (use file read tool after)
- **External/dependencies:** `include_content=true` (no file access)

### Combine with Local Tools
```bash
# CodeAlive for discovery
python search.py "payment processing" my-backend

# file read tool for details
# Read the specific files found

# CodeAlive for understanding
python chat.py "Explain the payment processing implementation" my-backend
```

### `description` is a triage pointer, not the source of truth
`search.py` returns a `description` for every result. Use it ONLY to decide
*which* artifacts deserve a closer look — never as the basis for your
understanding of the code. For each relevant result, immediately load the real
source via `fetch.py <identifier>` (external repos) or your editor's file-read
tool (current working repo). Treat only that real `content` as ground truth.

### Drill into relationships when you need the call graph
Once you've located an artifact via `search.py` or fetched it via `fetch.py`,
use `relationships.py` to expand it:
```bash
# Default: full outgoing + incoming call graph
python relationships.py "my-org/backend::src/auth.py::AuthService.login()"

# Class hierarchy
python relationships.py "my-org/backend::src/models.py::User" --profile inheritanceOnly

# Everything (calls + inheritance), bigger cap
python relationships.py "my-org/backend::src/svc.py::Service" --profile allRelevant --max-count 200
```
The `fetch.py` response shows up to 3 calls per direction as a preview;
`relationships.py` is how you escape that preview cap and switch profiles.

### Iterative Refinement
Start broad → Review results → Refine query → Repeat

```
1. "authentication" → Too many results
2. "JWT authentication implementation" → Better
3. "JWT token validation middleware" → Specific
```
