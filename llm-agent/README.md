# llm-agent

Track B1 of the pre-GA customer-journey test plan. A minimal agent whose
`/chat` calls its attached LLM Provider using exactly the Python snippet
shown in the LLM Configuration panel's own integration guide — no manual
`Host` header overrides, no ConfigMap patches, nothing a real customer
couldn't also do. Deployed as a Chat Agent (port 8000) via the buildpack
path, then an LLM Provider attached through Configure -> LLM Configuration.
