FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY runtime ./runtime
# The runtime readiness evaluator imports these two shared evidence validators.
# Copy only their production dependencies, not the full assurance test suite.
COPY assurance/certification_evidence.py assurance/evidence_writer.py ./assurance/
COPY config ./config
# The runtime writes only to its dedicated state mount; it must not run as root.
RUN mkdir -p /tmp/aurelia && chown -R 10001:10001 /tmp/aurelia
ENV HOME=/tmp/aurelia
ENV TMPDIR=/tmp/aurelia
USER 10001:10001
EXPOSE 8080
CMD ["python", "-m", "runtime.main"]
