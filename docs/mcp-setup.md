# Running tuck-it and connecting your agent (MCP)

## 1. First-time setup
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py bootstrap   # prints a one-time API token — copy it
```

## 2. Run the server (ASGI — required for MCP)
`manage.py runserver` is WSGI and does NOT serve the MCP endpoint. Use uvicorn:
```bash
uvicorn tuckit.asgi:app --port 8000
```
- Web dashboard: http://localhost:8000/
- MCP endpoint: http://localhost:8000/mcp

## 3. Register with Claude Code
```bash
claude mcp add --transport http tuck-it http://localhost:8000/mcp \
  --header "Authorization: Bearer <YOUR_TOKEN>"
```

Then in a session: ask the agent to call `get_project_state` — it returns the live
shipped / building / roadmap / ideas / someday breakdown instead of scanning markdown.
