# buildpack-agent

A2 of the pre-GA customer-journey test plan (Track A: deploy path). Same
minimal Chat Agent contract as `docker-agent` (port 8000, `/chat`, `/health`,
`{response: string}`), but deployed via the Python buildpack path instead of
a Dockerfile — no `Dockerfile` here on purpose, so the platform's own
Python-buildpack auto-detection is what's under test.
