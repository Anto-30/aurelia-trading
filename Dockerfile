FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV AURELIA_STATE_DIR=/var/lib/aurelia
ENV AURELIA_HEALTH_HOST=0.0.0.0
WORKDIR /app
COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --system --uid 10001 --create-home aurelia \
    && mkdir -p /var/lib/aurelia \
    && chown aurelia:aurelia /var/lib/aurelia
COPY runtime ./runtime
# The runtime readiness evaluator imports these two shared evidence validators.
# Copy only their production dependencies, not the full assurance test suite.
COPY assurance/certification_evidence.py assurance/evidence_writer.py ./assurance/
COPY config ./config
EXPOSE 8080
USER aurelia
CMD ["python", "-m", "runtime.main"]
