# Contributing

## Branch Naming

Use descriptive branch names with a type prefix and short description:

| Prefix | Use Case | Example |
|--------|----------|---------|
| `feat/` | New features | `feat/threat-intel-dashboard` |
| `fix/` | Bug fixes | `fix/kafka-offset-reset` |
| `refactor/` | Code refactoring | `refactor/ml-service-pipeline` |
| `docs/` | Documentation | `docs/api-reference` |
| `test/` | Test additions | `test/embedding-service` |
| `chore/` | Maintenance | `chore/update-dependencies` |
| `ops/` | DevOps/CI | `ops/docker-compose-production` |

Branches should be short (use abbreviations), lowercase, with hyphens separating words.

## Pull Request Workflow

1. **Create a branch** from `develop`:
   ```bash
   git checkout develop
   git pull origin develop
   git checkout -b feat/my-feature
   ```

2. **Make changes** following code style guidelines

3. **Commit often** with clear messages:
   ```bash
   git commit -m "feat: add threat scoring to ML service"
   ```
   Use conventional commits format: `type: description`

4. **Keep your branch updated**:
   ```bash
   git fetch origin
   git rebase origin/develop
   ```

5. **Run checks locally** before pushing:
   ```bash
   ruff check .
   ruff format --check .
   python -m pytest tests/ -v --timeout=30
   ```

6. **Push and create PR**:
   ```bash
   git push origin feat/my-feature
   ```
   Then open a PR on GitHub from `feat/my-feature` → `develop`.

7. **PR requirements**:
   - Descriptive title and body explaining what and why
   - Reference related issues (e.g., "Closes #42")
   - Ensure CI passes (lint, test, build)
   - At least one reviewer approval
   - No merge conflicts

8. **Merge** using squash merge into `develop`.

## Code Style

### Python

- **Target version:** Python 3.11+
- **Line length:** 120 characters
- **Formatter:** `ruff format` (docstring-code-format enabled)
- **Linter:** `ruff check` with rulesets: `E`, `F`, `I`, `N`, `W`, `UP`, `B`, `SIM`, `ARG`, `C4`, `T10`
- **Type hints:** Required for all function signatures
- **Imports:** Grouped as: standard library → third-party → local, separated by blank lines
- **Logging:** Use `structlog` — never `print()` or `logging.basicConfig()`
- **Docstrings:** Google-style or plain descriptive docstrings
- **Async:** Use `async def` for I/O-bound functions; use `asynccontextmanager` for lifespan
- **FastAPI lifespan:** Use `@asynccontextmanager` pattern, not `@app.on_event` decorators
- **Database:** Use raw asyncpg queries (no SQLAlchemy ORM)
- **Enums:** Use PostgreSQL ENUM types via raw SQL, not Python enums

```python
# Good
from backend.shared.logging_config import get_logger

logger = get_logger(__name__)

async def process_article(article_id: int) -> dict | None:
    """Process a single article and return enriched data."""
    logger.info("processing_article", article_id=article_id)
    ...
```

### TypeScript / React

- **Formatter:** Prettier (default config)
- **Linter:** ESLint with TypeScript rules
- **Types:** Prefer `interface` over `type` for object shapes
- **Components:** Functional components with hooks
- **Naming:** `PascalCase` for components, `camelCase` for functions/variables
- **API calls:** Use `@tanstack/react-query` with the API client in `src/lib/api.ts`
- **Forms:** Use `react-hook-form` + Zod validation
- **Styling:** Tailwind CSS utility classes via shadcn/ui components

### General

- No commented-out code — delete it
- No debug breakpoints (`pdb`, `ipdb`, `debugger`) in commits
- No large files (>500KB) committed to git
- No trailing whitespace
- Files must end with a newline
- No secrets or credentials in code — use `.env`

## Testing Requirements

### Python Tests

- Unit tests live in `tests/unit/`
- Integration tests live in `tests/integration/`
- Test files must be named `test_*.py`
- Use `pytest` as the test runner
- All tests must pass before merging
- New features should include unit tests
- Bug fixes should include a regression test

```python
# Example test
async def test_process_article():
    result = await process_article(article_id=1)
    assert result is not None
    assert "sentiment" in result
```

### Frontend Tests

- Use Vitest for unit tests
- Component tests with Testing Library
- Test files co-located with components: `Component.test.tsx`

## Documentation Requirements

- Every new service needs a section in `docs/SERVICE_GUIDE.md`
- New schema tables need entries in `docs/DATABASE_GUIDE.md`
- New Kafka topics need entries in `docs/KAFKA_GUIDE.md`
- API changes should update relevant docs
- Keep `CLAUDE.md` up-to-date with architecture changes
- Use ASCII diagrams where helpful to explain data flow

## AI Collaboration

This project uses a multi-model approach:
- **Claude** for code generation, refactoring, and documentation
- **Gemini 1.5/2.0** for high-context analysis across the architecture

Useful Gemini commands:
```bash
gemini analyze ./services
gemini "Explain the data flow from ingest-service to Elasticsearch"
```

## Getting Help

- Check existing documentation in `docs/`
- Review `CLAUDE.md` for project conventions
- Use `scripts/dev/status.ps1` to check service health
- Check service logs in `logs/` directory
- Open an issue on GitHub for problems

## Review Checklist

Before requesting review:
- [ ] Code follows style guidelines (ruff passes)
- [ ] Tests pass locally
- [ ] New code has tests
- [ ] Documentation updated (if applicable)
- [ ] No secrets/credentials committed
- [ ] Branch is up-to-date with `develop`
- [ ] Commits are clean and descriptive
- [ ] No merge conflicts
