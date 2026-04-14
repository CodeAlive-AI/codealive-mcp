# Query Patterns for CodeAlive

This guide provides effective query patterns for different code exploration scenarios.

## Table of Contents
- [Understanding Code](#understanding-code)
- [Finding Implementations](#finding-implementations)
- [Dependency Analysis](#dependency-analysis)
- [Cross-Project Learning](#cross-project-learning)
- [Debugging & Investigation](#debugging--investigation)
- [Architecture Discovery](#architecture-discovery)
- [Query Optimization](#query-optimization)

## Understanding Code

### Authentication & Authorization
```
Good: "How is user authentication implemented?"
Good: "JWT token validation flow"
Good: "Where are API permissions checked?"

Avoid: "auth" (too vague)
Avoid: "login.js" (use file search instead)
```

### Data Flow & Processing
```
Good: "How does user data flow from API to database?"
Good: "Payment processing pipeline"
Good: "Where is input validation performed?"

Avoid: "data" (too broad)
```

### API Endpoints
```
Good: "User registration API endpoint implementation"
Good: "How are GraphQL resolvers structured?"
Good: "REST API error handling patterns"
```

## Finding Implementations

### Features
```
Good: "Rate limiting implementation"
Good: "File upload handling with progress tracking"
Good: "Real-time notification system"
```

### Patterns
```
Good: "Repository pattern implementations"
Good: "Event-driven architecture examples"
Good: "Caching strategies in use"
```

### Algorithms
```
Good: "Search algorithm implementations"
Good: "Sorting logic for user data"
Good: "Pagination implementation patterns"
```

## Dependency Analysis

### Understanding Library Usage
```
Good: "How is axios used for HTTP requests?"
Good: "Lodash utility functions in use"
Good: "React hooks patterns (useState, useEffect)"
```

### Internal Implementation
```
Good: "How does lodash debounce work internally?"
Good: "Axios interceptor implementation details"
Good: "React context provider internals"
```

### Integration Patterns
```
Good: "Database ORM integration patterns"
Good: "How is Redis integrated with Express?"
Good: "Message queue (RabbitMQ) usage patterns"
```

## Cross-Project Learning

### Organizational Patterns
```
Good: "Error handling patterns across microservices"
Good: "Logging strategies in different services"
Good: "Configuration management approaches"

Tip: Use workspace data sources for cross-project queries
```

### Best Practices
```
Good: "Security best practices in authentication"
Good: "Performance optimization patterns"
Good: "Testing strategies across projects"
```

### Technology Comparison
```
Good: "REST vs GraphQL implementations in our codebase"
Good: "MongoDB vs PostgreSQL usage patterns"
Good: "Different state management solutions (Redux, MobX, Context)"
```

## Debugging & Investigation

### Symptoms to Root Cause
```
Good: "Slow database query performance issues"
Good: "Memory leak in background jobs"
Good: "Race conditions in async operations"
```

### Error Tracing
```
Good: "Where are 500 errors handled?"
Good: "Validation error origins"
Good: "Failed transaction rollback logic"
```

### Performance Issues
```
Good: "N+1 query problems in ORM"
Good: "Expensive operations in request handlers"
Good: "Bottlenecks in data processing pipeline"
```

## Architecture Discovery

### System Design
```
Good: "Microservices communication patterns"
Good: "Database schema and relationships"
Good: "Frontend-backend integration architecture"
```

### Component Relationships
```
Good: "How do services interact with each other?"
Good: "Dependency graph between modules"
Good: "Event flow through the system"
```

### Infrastructure
```
Good: "Deployment configuration patterns"
Good: "CI/CD pipeline implementation"
Good: "Monitoring and observability setup"
```

## Query Optimization

### Progressive Narrowing
Start broad, then narrow based on results:

```
1. Broad: "Authentication implementation"
   → Review results → Identify JWT approach

2. Narrow: "JWT token generation and validation"
   → Review results → Find middleware pattern

3. Specific: "JWT validation middleware error handling"
```

### Search Mode Selection

**Auto Mode** (default) - Use for most queries:
- Balanced speed and depth
- Intelligent semantic understanding
- Good for 80% of use cases

**Fast Mode** - Use for obvious/simple queries:
- Known function/class names
- Exact technical terms
- Quick lookups

**Deep Mode** - Use sparingly for complex queries:
- Cross-cutting concerns
- Abstract architectural questions
- When auto mode misses results
- Resource-intensive - use only when needed

### Include Content Decision

**include_content=false** (default for current repo):
```
Use when:
- Searching your current working repository
- Results are file paths for further investigation
- You'll use file read tool to examine files
- Want concise results
```

**include_content=true** (for external repos):
```
Use when:
- Searching external dependencies/libraries
- No file system access to the repository
- Need immediate code visibility
- Analyzing patterns across repos
```

### Combining Tools

**Search → Read → Ask Pattern:**
1. `search.py` to find relevant files
2. Use file read tool to examine specific files
3. `chat.py` to ask questions about what you found

**Ask → Search → Ask Pattern:**
1. `chat.py` for architectural overview
2. `search.py` to find specific implementations
3. `chat.py` again with more context

## Anti-Patterns (Avoid These)

### Too Vague
```
❌ "How does this work?"
✅ "How does user authentication work?"

❌ "Find functions"
✅ "Find password hashing functions"
```

### Too Specific (Use file search instead)
```
❌ "auth.controller.ts line 42"
✅ Use local search tools for exact locations

❌ "class UserService"
✅ Use local file search for specific class definitions
```

### Wrong Tool
```
❌ Using CodeAlive for uncommitted local changes
✅ Use grep/find for local file search

❌ Using CodeAlive for simple keyword search
✅ Use CodeAlive for semantic understanding
```

### Missing Context
```
❌ "error handling"
✅ "error handling in API controllers"

❌ "database"
✅ "database connection pooling configuration"
```

## Language-Specific Patterns

### JavaScript/TypeScript
```
"React component lifecycle patterns"
"async/await error handling"
"Express middleware implementation"
"TypeScript generic types usage"
```

### Python
```
"Decorators usage patterns"
"Context managers implementation"
"Async Python patterns with asyncio"
"Pydantic model validation"
```

### C#/.NET
```
"LINQ query patterns"
"Dependency injection configuration"
"async/await patterns in ASP.NET"
"Entity Framework relationships"
```

### Go
```
"Goroutine patterns and concurrency"
"Interface implementation examples"
"Error handling patterns"
"HTTP handler middleware"
```

## Pro Tips

1. **Use natural language** - CodeAlive understands intent, not just keywords
2. **Be specific about context** - Include domain/layer info (API, database, frontend)
3. **Leverage workspaces** - Search across multiple repos for patterns
4. **Start with search** - Use semantic search first, then grep when the literal pattern matters; only use chat after you have evidence and still need synthesis
5. **Iterate** - Use follow-up questions to drill deeper
6. **Combine with local tools** - CodeAlive for discovery, Read for details
7. **Think like a librarian** - Focus on "what" and "why", not "where"
