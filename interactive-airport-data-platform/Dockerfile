# Reproducible runtime: Python 3.12 plus the native Pango libraries WeasyPrint needs
# for tagged (accessible) PDF export. Identical behaviour on Windows, macOS and Linux hosts.
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libharfbuzz-subset0 \
        fontconfig \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 10001 app
WORKDIR /app

# specs/ is read at runtime (plan schema and coverage contracts), so the source tree is kept
# in place with an editable install.
COPY pyproject.toml ./
COPY src ./src
COPY specs ./specs
RUN pip install -e .

COPY app.py ./
COPY source_data ./source_data
RUN mkdir -p var reports && chown -R app:app var reports

USER app
# Fail the image build, not a user's download, when tagged PDF rendering is unavailable.
RUN python -c "from airport_analytics.reports.pdf_runtime import require_pdf_runtime; require_pdf_runtime()"

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=4)"
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]

# Test image: the same native runtime, so tagged-PDF tests always run instead of skipping.
FROM runtime AS test
USER root
RUN pip install -e ".[dev]"
COPY tests ./tests
RUN chown -R app:app /app
USER app
CMD ["python", "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider"]
