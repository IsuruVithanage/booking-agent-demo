# docker-agent

Minimal, non-adversarial Docker-based agent — Track A (deploy path) of the
pre-GA customer-journey test plan. Plain `python:3.11-slim` FastAPI service
exposing `POST /chat`. No `USER` directive yet, deliberately — first deploy
attempt checks whether the platform's non-root gate gives a clear, fixable
error for a first-time customer.
