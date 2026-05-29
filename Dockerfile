FROM python:3.12-slim-bookworm

WORKDIR /app

# Keep Playwright/Chromium and runtime temp profiles outside /tmp so the
# scraper keeps working even if the container/node temporary directory is
# cleaned up or size-limited.
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    TMPDIR=/app/.tmp

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN mkdir -p "$PLAYWRIGHT_BROWSERS_PATH" "$TMPDIR" \
    && playwright install --with-deps chromium \
    && chmod -R 777 "$PLAYWRIGHT_BROWSERS_PATH" "$TMPDIR"

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
