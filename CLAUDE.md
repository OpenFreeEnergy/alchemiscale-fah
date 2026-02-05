# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

alchemiscale-fah is a Python service that integrates Folding@Home (FAH) as a distributed compute backend for alchemiscale, enabling planetary-scale alchemical free energy calculations. It provides an asynchronous compute service that claims tasks from alchemiscale, submits molecular dynamics simulation jobs to FAH work servers, polls for completion, and returns results.

## Common Commands

### Environment Setup
```bash
# Create conda environment (requires micromamba/mamba)
micromamba create -f devtools/conda-envs/test.yml
micromamba activate alchemiscale-fah-test
pip install --no-deps -e .
```

### Testing
```bash
# Run all tests with coverage
pytest -v --cov=alchemiscale_fah --cov-report=xml alchemiscale_fah/tests

# Run a single test file
pytest -v alchemiscale_fah/tests/unit/test_utils.py

# Run a single test
pytest -v alchemiscale_fah/tests/unit/test_utils.py::test_function_name
```

### Formatting
```bash
# Check formatting (enforced in CI)
black --check --diff alchemiscale_fah

# Auto-format
black alchemiscale_fah
```

### CLI
```bash
alchemiscale-fah --help
alchemiscale-fah compute fah-asynchronous --config-file config.yml
```

## Architecture

### Core Data Flow
```
alchemiscale server → Task claimed by FahAsynchronousComputeService
→ ProtocolDAG deserialized → FahSimulationUnits execute asynchronously
→ Jobs submitted to FAH work server → Service polls for completion
→ Results retrieved → ProtocolDAGResult assembled → Returned to alchemiscale
```

### Key Components

**`compute/service.py` — FahAsynchronousComputeService**: Main orchestrator. Extends alchemiscale's `SynchronousComputeService`. Claims tasks, manages the full lifecycle of ProtocolDAG execution through FAH, and handles async polling for job completion.

**`compute/client.py` — FahAdaptiveSamplingClient**: HTTP/TLS client for FAH assignment and work servers. Handles RSA key generation, CSR creation, certificate renewal, job submission, and result retrieval.

**`compute/index.py` — FahComputeServiceIndex**: LevelDB-backed persistent state store. Tracks active tasks, FAH project/run/clone mappings, and job states. Thread-safe.

**`compute/models.py`**: Pydantic models for FAH data structures (ProjectData, JobData, JobResults, FahProject, FahRun, FahClone, JobStateEnum).

**`compute/settings.py` — FahAsynchronousComputeServiceSettings**: Pydantic-based configuration schema for the compute service.

**`protocols/protocolunit.py` — FahSimulationUnit, FahContext**: Base class for FAH-aware protocol units. `FahContext` is a kw_only dataclass extending GUFE's `Context` that injects FAH-specific dependencies (client, projects, index, poll interval) into unit execution.

**`protocols/feflow/nonequilibrium_cycling.py`**: FAH-optimized implementation of nonequilibrium cycling protocol using OpenMM via feflow.

**`settings/`**: Protocol-level settings schemas — `FahOpenMMCoreSettings` for execution parameters, FAH WS API settings.

**`utils.py`**: Utility functions for effort calculation and credit assignment, including `NonbondedSettings` enum and `NONBONDED_EFFORT` mapping.

### Key Design Patterns

- **Async execution**: `FahSimulationUnit.execute()` is async; the service uses asyncio for non-blocking FAH polling
- **Context injection**: `FahContext` dataclass provides all FAH dependencies to protocol units during execution
- **State persistence**: LevelDB index tracks job state across service restarts
- **Effort-based routing**: Projects are selected based on simulation effort (PME vs NoCutoff nonbonded methods)

### Dependencies

Core ecosystem: `gufe` (protocol framework), `openfe` (chemistry), `feflow` (OpenMM protocols), `alchemiscale` (task orchestration). Python 3.11+. Uses `pytest-asyncio` with `asyncio_mode = "auto"` for testing.
