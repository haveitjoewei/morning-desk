FROM python:3.12-slim
WORKDIR /app
COPY requirements-web.txt .
RUN pip install --no-cache-dir -r requirements-web.txt
COPY core ./core
COPY ai ./ai
COPY connectors ./connectors
COPY wardrobe ./wardrobe
COPY webapp ./webapp
COPY profiles/evangeline ./profiles/evangeline
ENV WARDROBE_PROFILE=evangeline
CMD uvicorn webapp.app:app --host 0.0.0.0 --port ${PORT:-8000}
