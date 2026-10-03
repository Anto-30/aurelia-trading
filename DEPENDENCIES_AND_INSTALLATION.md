# AURELIA Trading Platform: Complete Dependencies & Installation Guide

**Last Updated:** 2026-10-03  
**Status:** CRITICAL FOR OPERATIONAL READINESS  
**Scope:** All required dependencies, installations, syncs, and configurations for robust AURELIA operation

---

## 1. System Requirements & Prerequisites

### 1.1 Python Environment
- **Required Version:** Python 3.11+  (3.13 recommended as per Dockerfile)
- **Virtual Environment:** REQUIRED (use `venv` or `conda`)
- **Package Manager:** pip 24+ or equivalent

```bash
# Verify Python
python3 --version  # Must be 3.11+

# Create virtual environment
python3 -m venv aurelia_venv
source aurelia_venv/bin/activate  # Linux/macOS
# OR
aurelia_venv\Scripts\activate  # Windows
```

### 1.2 System Dependencies
- Git 2.40+
- Docker 24+ (for containerized deployment)
- PostgreSQL 15+ (future relational data, optional now)
- Redis 7+ (for caching/sessions, optional for initial deployment)

---

## 2. Core Python Dependencies

### 2.1 Primary Dependencies (from `requirements.txt` and `pyproject.toml`)

| Dependency | Version | Purpose | Critical |
|---|---|---|---|
| `websockets` | `>=17.1,<18` | Deriv Options WebSocket API connection | **CRITICAL** |
| `setuptools` | `>=75` | Build system | REQUIRED |
| `wheel` | Latest | Package distribution | REQUIRED |

```bash
# Install from requirements.txt
pip install --no-cache-dir -r requirements.txt

# Install build tools
pip install setuptools>=75 wheel
```

### 2.2 Development Dependencies (RECOMMENDED for robustness)

These are NOT in base requirements but essential for testing, debugging, and operational hardening:

```bash
pip install --upgrade pip setuptools wheel

# Testing and quality assurance
pip install pytest>=7.4.0          # Unit testing framework
pip install pytest-asyncio>=0.21   # Async test support
pip install coverage>=7.3          # Code coverage analysis
pip install pytest-cov             # Coverage plugin

# Code quality
pip install black>=23.0            # Code formatter
pip install flake8>=6.0            # Linter
pip install pylint>=2.17           # Advanced linter
pip install mypy>=1.5              # Static type checker
pip install isort>=5.12            # Import sorting

# Operational tools
pip install python-dotenv>=1.0     # Environment variable management
pip install pyyaml>=6.0            # YAML config parsing
pip install jsonschema>=4.20       # JSON validation
pip install cryptography>=41.0     # Secure credential handling

# Async/concurrency utilities
pip install aiohttp>=3.9           # Async HTTP (future broker APIs)
pip install asyncio-contextmanager # Enhanced async context management

# Monitoring and observability
pip install prometheus-client>=0.18 # Metrics export
pip install python-json-logger>=2.0 # Structured logging
```

### 2.3 Optional but Recommended Dependencies

```bash
# Documentation
pip install sphinx>=7.0            # Documentation generation
pip install sphinx-rtd-theme       # Read-the-Docs theme

# Database (for future scalability)
pip install sqlalchemy>=2.0        # ORM
pip install psycopg2-binary>=2.9   # PostgreSQL adapter
pip install redis>=5.0             # Redis client

# Data validation
pip install pydantic>=2.0          # Data validation library
pip install marshmallow>=3.20      # Serialization library

# Distributed tracing (future)
pip install jaeger-client>=4.8     # OpenTelemetry tracing
pip install opentelemetry-api>=1.20 # Telemetry standards
```

---

## 3. Installation Steps (Complete)

### 3.1 Clone and Setup

```bash
# Clone repository
git clone https://github.com/Anto-30/aurelia-trading.git
cd aurelia-trading

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip setuptools wheel

# Install core dependencies
pip install -r requirements.txt
pip install -e .

# Install development dependencies
pip install -r requirements-assurance.txt
pip install pytest pytest-asyncio coverage pytest-cov
```

### 3.2 Verify Installation

```bash
# Check Python packages
pip list

# Verify websockets installation
python3 -c "import websockets; print(f'websockets: {websockets.__version__}')"

# Test runtime import
python3 -c "import runtime; print('✓ runtime module OK')"

# Test core modules
python3 -c "from runtime.adapters.session_manager import DerivSessionManager; print('✓ session_manager OK')"
python3 -c "from runtime.core.release_gate import read_live_release; print('✓ release_gate OK')"
```

---

## 4. Required Configuration & Environment Setup

### 4.1 Environment Variables (for live Deriv connectivity)

Create `.env` file in repository root:

```bash
# Deriv API Credentials (REQUIRED for live trading)
DERIV_AUTH_TOKEN=<your_deriv_api_token>          # PAT or OAuth token
DERIV_APP_ID=<your_deriv_app_id>                 # For PAT auth mode
DERIV_EXPECTED_LOGINID=<your_deriv_login_id>    # Real account ID (CR#####)
DERIV_EXPECTED_CURRENCY=USD                       # Account currency
DERIV_ENVIRONMENT=real                            # real or demo
DERIV_AUTH_MODE=pat                               # pat or oauth

# Runtime Configuration
AURELIA_JOURNAL_PATH=/tmp/aurelia/aurelia-events.ndjson
PORT=8080
PYTHONDONTWRITEBYTECODE=1
PYTHONUNBUFFERED=1

# Verification Flags (set to 'true' when ready to verify)
AURELIA_VERIFY_DERIV_PUBLIC=true
AURELIA_VERIFY_DERIV_AUTH=false  # Set to 'true' only with valid credentials
AURELIA_RUN_ONCE=false

# Readiness Gates (leave as false unless explicitly tested)
AURELIA_STRATEGY_LIVE_ELIGIBLE=false
AURELIA_PROSPECTIVE_OOS_PASS=false
AURELIA_CALIBRATION_PASS=false
AURELIA_ECONOMICS_PASS=false
AURELIA_SOAK_3600S_PASS=false
```

Load environment variables (Python):

```python
import os
from dotenv import load_dotenv

load_dotenv()
auth_token = os.getenv('DERIV_AUTH_TOKEN')
```

### 4.2 Config Files

Ensure these files exist and are correctly configured:

```bash
# Live release control (CRITICAL)
config/LIVE_LOCK.yaml

# Runtime configuration (if exists)
config/runtime.yaml

# Example config/LIVE_LOCK.yaml structure:
cat > config/LIVE_LOCK.yaml << 'EOF'
schema: aurelia.live_lock.v1
live_trading_enabled: false
FINAL_EXECUTION_AUTHORIZATION: false
LIVE_EXECUTION: BLOCKED
capital_plane_mode: VERIFY_ONLY
research_capital_authority: false
external_repositories_capital_forbidden: true
blind_resubmission: false
kill_switch_independent: true
EOF
```

---

## 5. Module Dependencies (Intra-System)

### 5.1 Runtime Module Dependencies Tree

```
runtime/
├── main.py                          # Entry point
│   ├── adapters/session_manager     # Deriv session bootstrap
│   ├── adapters/deriv_adapter       # WebSocket transport
│   ├── core/health                  # Health monitoring
│   ├── core/journal                 # Event journaling
│   ├── core/state                   # State machine
│   ├── core/supervisor              # Watchdog/kill-switch
│   └── core/release_gate            # Live-lock control
│
├── adapters/                        # Broker integration
│   ├── deriv_session.py             # Session validation (FIXED)
│   ├── session_manager.py           # Session bootstrap (FIXED)
│   ├── deriv_adapter.py             # WebSocket adapter
│   ├── deriv_ws.py                  # Transport layer
│   └── deriv_lifecycle.py           # Connection lifecycle
│
├── core/                            # Invariants & controls
│   ├── authority.py                 # Authorization gates
│   ├── capabilities.py              # Capability boundaries
│   ├── exposure.py                  # Exposure controls
│   ├── idempotency.py               # Exactly-once semantics
│   ├── fencing.py                   # Atomic access control
│   ├── reconcile.py                 # Reconciliation logic
│   ├── recovery.py                  # Failure recovery
│   ├── release_gate.py              # Live-lock (FIXED)
│   ├── health.py                    # Health monitoring
│   ├── supervisor.py                # Watchdog daemon
│   ├── models.py                    # Data models
│   ├── events.py                    # Event envelope
│   ├── journal.py                   # Event journal
│   ├── limits.py                    # Execution limits (FIXED)
│   ├── ledger.py                    # Test ledger contract
│   └── state.py                     # State machine
│
├── broker/                          # Capital execution boundary
│   ├── executor.py                  # Single capital executor
│   └── factory.py                   # Executor factory
│
├── strategy/                        # Strategy governance
│   └── governance.py                # Strategy controls
│
├── validation/                      # Research validation
│   ├── walk_forward.py              # OOS validation
│   ├── probability.py               # Calibration & drift
│   └── decision_replay.py           # Replay verification
│
├── security/                        # Secret & credential handling
│   └── secrets.py                   # Secure credential manager
│
└── ops/                             # Operational utilities
    └── readiness_orchestrator.py    # Readiness report engine
```

### 5.2 Capital Module Dependencies

```
capital/
└── capital_plane.py                 # Capital authorization boundary
    └── Depends on:
        ├── runtime/core/authority
        ├── runtime/core/limits
        └── runtime/core/models
```

### 5.3 Execution Module Dependencies

```
execution/
└── deriv.py                         # Deriv execution facade
    └── Depends on:
        ├── runtime/adapters/deriv_adapter
        ├── capital/capital_plane
        └── runtime/core/invariants
```

### 5.4 Assurance Module Dependencies

```
assurance/
├── aurelia_hardening.py             # Hardening predicates (FIXED)
├── aurelia_invariants.py            # Invariant checks
├── certification_gate.py            # Certification logic
├── evidence_writer.py               # Evidence serialization
└── test_*.py                        # Assurance test suite
    └── All depend on:
        ├── runtime/core/*
        ├── capital/capital_plane
        ├── execution/deriv
        └── assurance/*
```

---

## 6. Database & Persistence Setup (For Future Scalability)

### 6.1 PostgreSQL (Optional, for audit trail)

```bash
# Install PostgreSQL (macOS)
brew install postgresql@15

# Install PostgreSQL (Linux)
sudo apt-get install postgresql-15 postgresql-contrib-15

# Initialize database
createdb aurelia_ledger
psql aurelia_ledger < schema.sql  # (future schema file)

# Environment variable
export DATABASE_URL=postgresql://user:password@localhost:5432/aurelia_ledger
```

### 6.2 Redis (Optional, for session caching)

```bash
# Install Redis (macOS)
brew install redis

# Install Redis (Linux)
sudo apt-get install redis-server

# Start Redis
redis-server

# Environment variable
export REDIS_URL=redis://localhost:6379/0
```

---

## 7. Docker Setup (For Containerized Deployment)

### 7.1 Build Image

```bash
# Build Docker image
docker build -t aurelia-runtime:latest .

# Verify image
docker images | grep aurelia
```

### 7.2 Run Container

```bash
# Run container (verification mode)
docker run \
  -e AURELIA_VERIFY_DERIV_PUBLIC=true \
  -e AURELIA_RUN_ONCE=true \
  -p 8080:8080 \
  aurelia-runtime:latest

# Run container (live mode - requires credentials)
docker run \
  -e DERIV_AUTH_TOKEN=<token> \
  -e DERIV_APP_ID=<app_id> \
  -e DERIV_EXPECTED_LOGINID=<login> \
  -e DERIV_ENVIRONMENT=real \
  -e AURELIA_VERIFY_DERIV_AUTH=true \
  -p 8080:8080 \
  aurelia-runtime:latest
```

---

## 8. Testing & Validation

### 8.1 Run All Tests

```bash
# Run runtime tests
python -m pytest tests/ -v --cov=runtime

# Run assurance tests
python -m pytest assurance/ -v --cov=assurance

# Run specific test
python -m pytest tests/test_deriv_session_manager.py -v
```

### 8.2 Manual Verification

```bash
# Verify public Deriv connectivity
AURELIA_VERIFY_DERIV_PUBLIC=true \
AURELIA_RUN_ONCE=true \
python -m runtime.main

# Verify authenticated session (requires credentials)
DERIV_AUTH_TOKEN=<token> \
DERIV_APP_ID=<app_id> \
DERIV_EXPECTED_LOGINID=<login> \
DERIV_ENVIRONMENT=real \
AURELIA_VERIFY_DERIV_AUTH=true \
python scripts/verify_deriv_session.py
```

### 8.3 Readiness Report

```bash
# Generate readiness report
python -m runtime.ops.readiness_orchestrator

# Output: data/runtime/AURELIA_READINESS.json
```

---

## 9. Monitoring & Observability

### 9.1 Health Endpoints

```bash
# Health check
curl http://localhost:8080/health

# Readiness check
curl http://localhost:8080/ready
```

### 9.2 Journal & Logs

```bash
# View event journal
tail -f /tmp/aurelia/aurelia-events.ndjson | jq .

# Parse events
python -c "
import json
with open('/tmp/aurelia/aurelia-events.ndjson') as f:
    for line in f:
        event = json.loads(line)
        print(f\"{event['event_type']}: {event['payload']}\")
"
```

---

## 10. Troubleshooting & Validation Checklist

### 10.1 Installation Verification

- [ ] Python 3.11+ installed
- [ ] Virtual environment activated
- [ ] `websockets>=17.1` installed (`pip show websockets`)
- [ ] All runtime modules importable
- [ ] `config/LIVE_LOCK.yaml` exists and readable
- [ ] `.env` file configured (if using Deriv credentials)

### 10.2 Runtime Verification

- [ ] `python -m runtime.main` starts without errors
- [ ] Health endpoint responds at `http://localhost:8080/health`
- [ ] Event journal created at configured path
- [ ] No import errors in test suite
- [ ] All 73+ unit tests pass

### 10.3 Deriv Connectivity Verification

- [ ] Public WebSocket connection successful (public symbols loaded)
- [ ] Authenticated session verifiable (with valid credentials)
- [ ] Balance snapshot captured correctly
- [ ] Account binding matches expected login ID
- [ ] No secrets logged or committed

### 10.4 Safety & Control Verification

- [ ] `LIVE_LOCK.yaml` has `FINAL_EXECUTION_AUTHORIZATION: false`
- [ ] `LIVE_LOCK.yaml` has `LIVE_EXECUTION: BLOCKED`
- [ ] `capital_plane_mode: VERIFY_ONLY`
- [ ] No live order submission path enabled
- [ ] Kill-switch is armed and tested

---

## 11. Deployment Readiness Checklist

### Required Before Any Live Deployment

- [ ] All tests passing (100% coverage for critical paths)
- [ ] Docker image builds and runs successfully
- [ ] Environment variables configured securely (no hardcoding)
- [ ] Credential rotation policy documented
- [ ] Monitoring/alerting configured
- [ ] Backup/recovery procedures documented
- [ ] 3600+ second soak test completed
- [ ] Calibration evidence captured
- [ ] OOS/walk-forward validation passed
- [ ] Economic analysis completed
- [ ] Explicit release-gate approval given
- [ ] `config/LIVE_LOCK.yaml` updated ONLY after all gates pass

---

## 12. Quick Start

### Minimal Setup (Local Development)

```bash
# 1. Clone and setup
git clone https://github.com/Anto-30/aurelia-trading.git
cd aurelia-trading
python3 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
pip install -r requirements-assurance.txt
pip install pytest pytest-asyncio

# 3. Run tests
python -m pytest tests/ assurance/ -v

# 4. Verify public Deriv
AURELIA_VERIFY_DERIV_PUBLIC=true AURELIA_RUN_ONCE=true python -m runtime.main

# 5. Generate readiness report
python -m runtime.ops.readiness_orchestrator
```

### Full Setup (With Credentials & Verification)

```bash
# 1-4. Same as above, then:

# 5. Configure environment
export DERIV_AUTH_TOKEN="your_token_here"
export DERIV_APP_ID="your_app_id"
export DERIV_EXPECTED_LOGINID="CR#####"
export DERIV_ENVIRONMENT="real"

# 6. Verify authenticated session
python scripts/verify_deriv_session.py

# 7. Start runtime (monitoring mode)
python -m runtime.main
```

---

## Summary: Dependencies by Category

| Category | Dependencies | Status |
|---|---|---|
| **Core Runtime** | websockets>=17.1 | ✓ INSTALLED |
| **Build System** | setuptools>=75, wheel | ✓ INSTALLED |
| **Testing** | pytest, pytest-asyncio, coverage | ✓ OPTIONAL (RECOMMENDED) |
| **Code Quality** | black, flake8, mypy, pylint | ○ OPTIONAL |
| **Config** | pyyaml, jsonschema, python-dotenv | ○ OPTIONAL (RECOMMENDED) |
| **Observability** | prometheus-client, python-json-logger | ○ FUTURE |
| **Data Validation** | pydantic, marshmallow | ○ FUTURE |
| **Database** | sqlalchemy, psycopg2, redis | ○ FUTURE |
| **Security** | cryptography | ○ OPTIONAL (RECOMMENDED) |

**Status Key:**
- ✓ INSTALLED: Included in base requirements
- ○ OPTIONAL: Not required but recommended
- ○ FUTURE: For planned features

---

## Support & Troubleshooting

For import errors, dependency conflicts, or installation issues:

```bash
# Clear pip cache and reinstall
pip cache purge
pip install --force-reinstall --no-cache-dir -r requirements.txt

# Check for conflicting versions
pip check

# Create fresh environment
deactivate
rm -rf venv/
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

**Last Verified:** 2026-10-03  
**Maintainer:** Anto-30 (AURELIA Platform)
