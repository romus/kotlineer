# Use Cases

Practical examples and patterns for using kotlineer in different scenarios.

## CI/CD Pipeline Integration

### GitHub Actions — lint and format check

```yaml
name: Kotlin Lint
on: [push, pull_request]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: 17

      - name: Install kotlin-lsp
        run: |
          curl -L -o kotlin-lsp.tar.gz https://github.com/Kotlin/kotlin-lsp/releases/latest/download/kotlin-lsp-linux-x64.tar.gz
          tar xzf kotlin-lsp.tar.gz
          echo "$PWD/kotlin-lsp/bin" >> $GITHUB_PATH

      - name: Install kotlineer
        run: pip install kotlineer

      - name: Start kotlin-lsp
        run: kotlin-lsp --socket 8200 &

      - name: Check for errors
        run: kotlineer check --errors-only

      - name: Check formatting
        run: kotlineer format --check
```

### Pre-commit hook

```bash
#!/usr/bin/env bash
# .git/hooks/pre-commit

# Assumes kotlin-lsp is running at localhost:8200
STAGED=$(git diff --cached --name-only --diff-filter=ACM | grep '\.kt$')

if [ -n "$STAGED" ]; then
    kotlineer check --errors-only $STAGED
    if [ $? -ne 0 ]; then
        echo "Kotlin errors found. Commit aborted."
        exit 1
    fi

    kotlineer format --check $STAGED
    if [ $? -ne 0 ]; then
        echo "Kotlin files need formatting. Run: kotlineer format $STAGED"
        exit 1
    fi
fi
```

## Editor / IDE Tool Integration

### Building a custom linter output parser

```python
import asyncio
import json
from kotlineer import KotlinLspClient

async def lint_project(workspace: str) -> dict:
    """Run diagnostics and return structured results."""
    client = KotlinLspClient(workspace)
    await client.start()

    # Discover and open all Kotlin files
    from pathlib import Path
    kt_files = sorted(Path(workspace).rglob("*.kt"))

    uris = []
    for f in kt_files:
        if any(p in f.parts for p in ("build", ".gradle", ".idea")):
            continue
        uris.append(await client.open_file(str(f)))

    # Wait for analysis to settle
    await asyncio.sleep(5)

    results = client.diagnostics.get()
    await client.stop()
    return results

results = asyncio.run(lint_project("/path/to/project"))
print(json.dumps(results, indent=2))
```

### Real-time diagnostics watcher

```python
import asyncio
from kotlineer import KotlinLspClient

async def watch_diagnostics(workspace: str):
    """Stream diagnostics as they arrive."""
    client = KotlinLspClient(workspace)
    await client.start()

    def on_update(uri: str, diags: list):
        if diags:
            print(f"\n{uri}:")
            for d in diags:
                severity = {1: "ERROR", 2: "WARN", 3: "INFO", 4: "HINT"}.get(
                    d.get("severity", 1), "?"
                )
                line = d["range"]["start"]["line"] + 1
                print(f"  [{severity}] line {line}: {d.get('message', '')}")

    client.diagnostics.on_update(on_update)

    # Open files
    from pathlib import Path
    for f in Path(workspace).rglob("*.kt"):
        if "build" not in f.parts:
            await client.open_file(str(f))

    # Keep running
    print(f"Watching {workspace} for diagnostics... (Ctrl+C to stop)")
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        await client.stop()

asyncio.run(watch_diagnostics("/path/to/project"))
```

## Code Analysis and Exploration

### Find all usages of a symbol

```python
import asyncio
from kotlineer import KotlinLspClient

async def find_usages(workspace: str, file: str, line: int, col: int):
    client = KotlinLspClient(workspace)
    await client.start()

    uri = await client.open_file(file)
    refs = await client.navigation.references(uri, line, col, include_declaration=False)

    if refs:
        for ref in refs:
            loc_line = ref["range"]["start"]["line"] + 1
            loc_col = ref["range"]["start"]["character"] + 1
            print(f"  {ref['uri']}:{loc_line}:{loc_col}")
    else:
        print("No references found")

    await client.stop()

asyncio.run(find_usages(
    "/path/to/project",
    "src/main/kotlin/com/example/UserRepository.kt",
    line=7,  # 0-based
    col=13,  # 0-based
))
```

### Explore class hierarchy

```python
import asyncio
from kotlineer import KotlinLspClient

async def show_hierarchy(workspace: str, file: str, line: int, col: int):
    client = KotlinLspClient(workspace)
    await client.start()

    uri = await client.open_file(file)

    supers = await client.hierarchy.supertypes(uri, line, col)
    subs = await client.hierarchy.subtypes(uri, line, col)

    print("Supertypes:")
    for s in supers or []:
        print(f"  {s['name']}")

    print("Subtypes:")
    for s in subs or []:
        print(f"  {s['name']}")

    await client.stop()

asyncio.run(show_hierarchy(
    "/path/to/project",
    "src/main/kotlin/com/example/BaseRepository.kt",
    line=4,
    col=6,
))
```

### Map call graph

```python
import asyncio
from kotlineer import KotlinLspClient

async def call_graph(workspace: str, file: str, line: int, col: int, depth: int = 2):
    client = KotlinLspClient(workspace)
    await client.start()

    uri = await client.open_file(file)

    async def print_outgoing(uri, line, col, indent=0):
        if indent >= depth:
            return
        calls = await client.hierarchy.outgoing_calls(uri, line, col)
        for call in calls or []:
            target = call["to"]
            name = target.get("name", "?")
            print(f"{'  ' * indent}-> {name}")

    await print_outgoing(uri, line, col)
    await client.stop()

asyncio.run(call_graph(
    "/path/to/project",
    "src/main/kotlin/com/example/UserService.kt",
    line=13,
    col=8,
))
```

## Batch Refactoring

### Rename a symbol across the project

```python
import asyncio
from pathlib import Path
from kotlineer import KotlinLspClient

async def rename_symbol(workspace: str, file: str, line: int, col: int, new_name: str):
    client = KotlinLspClient(workspace)
    await client.start()

    uri = await client.open_file(file)

    # Check if rename is possible
    prep = await client.refactoring.prepare_rename(uri, line, col)
    if not prep:
        print("Cannot rename at this position")
        await client.stop()
        return

    print(f"Renaming '{prep.get('placeholder', '?')}' to '{new_name}'...")

    edit = await client.refactoring.rename(uri, line, col, new_name)
    if edit and "changes" in edit:
        for file_uri, changes in edit["changes"].items():
            print(f"  {file_uri}: {len(changes)} change(s)")

    await client.stop()

asyncio.run(rename_symbol(
    "/path/to/project",
    "src/main/kotlin/com/example/UserService.kt",
    line=13,
    col=8,
    new_name="findUserById",
))
```

### Auto-format changed files only

```bash
# Format only files changed in the current branch
git diff --name-only main | grep '\.kt$' | xargs kotlineer format
```

## Code Generation Helpers

### Extract function signatures for documentation

```python
import asyncio
from kotlineer import KotlinLspClient

async def extract_api(workspace: str, file: str):
    """Extract all public function signatures from a file."""
    client = KotlinLspClient(workspace)
    await client.start()

    uri = await client.open_file(file)
    symbols = await client.symbols.document_symbols(uri)

    kind_names = {5: "class", 6: "method", 11: "interface", 12: "function"}

    def print_syms(syms, indent=0):
        for sym in syms or []:
            kind = kind_names.get(sym.get("kind"), None)
            if kind:
                line = sym.get("range", {}).get("start", {}).get("line", 0)
                hover = asyncio.get_event_loop().run_until_complete(
                    client.hover.hover(uri, line, 0)
                )
                sig = ""
                if hover:
                    c = hover.get("contents", {})
                    sig = c.get("value", "") if isinstance(c, dict) else str(c)
                print(f"{'  ' * indent}{kind} {sym['name']}: {sig}")
            for child in sym.get("children", []):
                print_syms([child], indent + 1)

    print_syms(symbols)
    await client.stop()

asyncio.run(extract_api(
    "/path/to/project",
    "src/main/kotlin/com/example/UserService.kt",
))
```

## Multi-project Setup

### Shared server, multiple workspaces

When working with a monorepo or multiple related projects, you can run one kotlin-lsp per project but share a single kotlineer workflow:

```bash
# Terminal 1: Start servers for each project
kotlin-lsp --socket 8200  # for project-a (run from project-a dir)
kotlin-lsp --socket 8201  # for project-b (run from project-b dir)

# Terminal 2: Use kotlineer with different connections
kotlineer --connect localhost:8200 -w ~/monorepo/project-a check
kotlineer --connect localhost:8201 -w ~/monorepo/project-b check
```

### Scripted multi-project check

```python
import asyncio
from kotlineer import KotlinLspClient

PROJECTS = [
    {"workspace": "/path/to/project-a", "port": 8200},
    {"workspace": "/path/to/project-b", "port": 8201},
]

async def check_all():
    for proj in PROJECTS:
        client = KotlinLspClient(proj["workspace"], port=proj["port"])
        await client.start()

        from pathlib import Path
        for f in Path(proj["workspace"]).rglob("*.kt"):
            if "build" not in f.parts:
                await client.open_file(str(f))

        await asyncio.sleep(5)
        errors = client.diagnostics.get_errors()
        total = sum(len(d) for d in errors.values())
        print(f"{proj['workspace']}: {total} error(s)")

        await client.stop()

asyncio.run(check_all())
```

## Troubleshooting

### Debug LSP communication

```bash
# Verbose mode shows all LSP messages
kotlineer -v check 2>lsp-debug.log
```

### Server not responding

```bash
# Check if the server is listening
nc -z localhost 8200 && echo "OK" || echo "NOT RUNNING"

# Restart the server
kotlin-lsp --socket 8200
```

### Slow analysis on large projects

```bash
# Increase timeouts
kotlineer --timeout 120 check --settle-time 15
```
