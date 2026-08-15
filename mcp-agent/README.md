# mcp-agent

Track C1 of the pre-GA customer-journey test plan. A minimal agent whose
`/chat` calls one MCP tool (`search_hotels`) directly through an attached
MCP Proxy — no LLM in the loop at all, so this purely tests whether the MCP
connection itself works, isolated from anything Track B already found
about LLM provider connectivity. Deployed via the buildpack path, Chat
Agent interface (port 8000), MCP Proxy attached through Configure -> Tool
Configurations with env var names `BOOKING_URL` / `BOOKING_API_KEY`.
