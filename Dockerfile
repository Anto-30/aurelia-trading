FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
# Advisory provider adapters must never run as the root control-plane process.
# UIDs/GIDs are pinned by config/agent_runtime_provider_matrix.json. Fail the
# build if a dedicated UID is already claimed instead of silently mapping a
# model process onto an unexpected identity.
RUN set -eu; \
    for entry in \
      claudecode:10011 \
      kimik3:10012 \
      grokbot:10013 \
      googleagentskills:10014 \
      glm:10015 \
      playwrightcli:10016 \
      jev:10017 \
      deepseekharness:10018 \
      hermesagent:10019; do \
        name="${entry%%:*}"; uid="${entry##*:}"; account="aurelia-agent-${name}"; \
        if getent passwd "$uid" >/dev/null 2>&1 || getent group "$uid" >/dev/null 2>&1; then \
          echo "BUILD_BLOCKED=AGENT_SANDBOX_UID_ALREADY_ASSIGNED:$uid"; exit 2; \
        fi; \
        useradd --system --uid "$uid" --user-group --no-create-home \
          --home-dir /nonexistent --shell /usr/sbin/nologin "$account"; \
    done
COPY runtime ./runtime
# The runtime readiness evaluator imports these two shared evidence validators.
# Copy only their production dependencies, not the full assurance test suite.
COPY assurance/certification_evidence.py assurance/evidence_writer.py ./assurance/
COPY config ./config
EXPOSE 8080
CMD ["python", "-m", "runtime.main"]
