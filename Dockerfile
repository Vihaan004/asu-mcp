# Plain Docker on purpose: the same image runs on Railway, Render, Fly, Koyeb
# or your own box. Nothing here is tied to a single host.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.8 /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN uv pip install --system --no-cache .

# Hosted deployments serve HTTP; the local install path overrides this to stdio.
ENV ASU_MCP_TRANSPORT=streamable-http \
    PORT=8000 \
    PYTHONUNBUFFERED=1

RUN useradd --create-home --uid 10001 asu
USER asu

EXPOSE 8000

CMD ["asu-mcp"]
