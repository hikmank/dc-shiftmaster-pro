# DC-ShiftMaster Pro — Production container image
FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies first (layer caching)
COPY requirements-html.txt .
RUN pip install --no-cache-dir -r requirements-html.txt

# Copy application source
COPY dc_shiftmaster/ dc_shiftmaster/
COPY dc_shiftmaster_html/ dc_shiftmaster_html/
COPY gunicorn.conf.py .
COPY pyproject.toml .

# Install the project itself (needed for package imports)
RUN pip install --no-cache-dir -e .

EXPOSE 5000

# Database is mounted as a volume at runtime — not baked into the image
VOLUME ["/data"]
ENV SHIFTMASTER_DB_PATH=/data/teammates.db

ENTRYPOINT ["gunicorn", "-c", "gunicorn.conf.py"]
