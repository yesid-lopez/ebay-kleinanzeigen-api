FROM python:3.12-slim

WORKDIR /app
COPY server.py .
RUN pip install --no-cache-dir "mcp[cli]" httpx
EXPOSE 8080

CMD ["python", "server.py"]
