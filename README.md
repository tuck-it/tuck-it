# tuck-it

A single source of truth for a product's state, roadmap, and deferred work —
read and written equally by you (web dashboard) and your AI agent (MCP).

**License:** PolyForm Noncommercial 1.0.0 (source-available, non-commercial).
Commercial hosting rights reserved by the author.

## Run

tuck-it serves both the web dashboard and the agent MCP endpoint from one ASGI app:

```bash
uvicorn tuckit.asgi:app --port 8000
```

See [docs/mcp-setup.md](docs/mcp-setup.md) to connect your agent (MCP over HTTP).

## Web dashboard

```bash
python manage.py migrate
python manage.py bootstrap   # first run only — creates the local workspace
uvicorn tuckit.asgi:app --port 8000   # or: python manage.py runserver
```

Open http://localhost:8000/ — home, inbox, areas (list/board), slice detail, and
settings (workspace name, API tokens, MCP snippet) all live there.

Your agent reads and writes the same workspace over MCP (see
[docs/mcp-setup.md](docs/mcp-setup.md)); you read and write it over the web. One
database, no sync step — whichever one you look at is current.
