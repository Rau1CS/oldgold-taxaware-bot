# OldGold Tax-Aware Bot – Project Postmortem

This document summarizes the state of the repository at deprecation time. It highlights functional components, known limitations, and elements that may be reused in future projects.

## Functional Overview

### CLI and Configuration
- **`oldgold/cli.py`** – Dispatches to subcommands for scanning, probing, simulation and execution planning. Works with modules in the `oldgold` package and expects a configured `.env` file with RPC endpoints and optional private key.
- **`oldgold/config.py`** – Loads chain and environment configuration via `dotenv` and exposes typed `Chain` dataclass instances.
- **`oldgold/logging_conf.py`** – Provides structured logging with optional `rich` integration.

### Core Utilities
- **`oldgold/utils.py`** – JSON helpers, retry utilities, checksum conversion and basic time helpers. All functions are pure and reusable.

### Simulation
- **`oldgold/sim/v2_math.py`** – Constant product AMM math with buy/sell tax awareness.
- **`oldgold/sim/simulate.py`** – CLI and helper used to sweep trade sizes and record simulated profit/loss. Outputs JSON artifacts under `out/`.

### Scanner
- **`oldgold/scanner/scan.py`** – Pulls candidate pools from a GraphQL subgraph, filters by liquidity and volume, ranks by a heuristic score and writes results to `out/`.
- **`oldgold/scanner/pairs.py`** – Utility to locate pair addresses and reserves on chain, plus helper to discover the deepest "active" pool via subgraph.
- **`oldgold/scanner/subgraph_client.py`** – Minimal client with retry logic for GraphQL requests.

### Tax Probing
- **`oldgold/tax/probe.py`** – Performs live dust swaps against a router to estimate token buy and sell taxes. Requires a funded private key. Results are cached via **`oldgold/tax/cache.py`** to avoid repeat probes.

### Execution / Planning
- **`oldgold/exec/run_one.py`** – End-to-end routine: discovers pools, probes taxes (unless dry-run), simulates tax-aware arbitrage and writes decision payloads.
- **`oldgold/exec/discover.py`** – Reads token lists and ranks opportunities by edge and expected no-tax PnL.
- **`oldgold/exec/gen_candidates.py`** – Generates token candidate lists by querying subgraphs for low-volume, high-liquidity pools.
- **`oldgold/exec/batch_probe.py`** – Batch wrapper that probes multiple tokens and ranks by expected profitability.
- **`oldgold/exec/wrap.py`** – Helper to wrap native base assets into their ERC‑20 equivalents (e.g., BNB → WBNB).
- **`oldgold/exec/plan.py`** – Lightweight planner computing final decision and PnL for a single trade size.
- **Scripts** in `scripts/` and Make targets orchestrate common flows (`scan`, `probe`, `simulate`, `discover`, `batch-probe`, etc.).

### Data Assets
- Static token/address mappings in **`oldgold/data/tokens.py`** and deny lists in **`oldgold/data/denylists.json`**.

### Tests
- `pytest` suite covers mathematical helpers (`amount_out_v2`, `buy_cost_on_active_pool`) and basic monotonicity/pnl behaviour.

## Non-Functional / Stubbed Areas
- **Execution planning** beyond simple profit checks is not implemented (`oldgold/exec/plan.py` and `oldgold/exec/__init__.py` are marked as stubs).
- No integration tests exist for on-chain interactions; most network calls are untested and rely on live RPCs.
- The repository lacks comprehensive error handling around subgraph downtime and transaction failures, though basic retries are in place.

## Achievements
- Demonstrated end-to-end pipeline: subgraph scanning → tax probing via live dust swaps → tax-aware simulation and ranking.
- Implemented reusable AMM math with tax support and bisection-based cost calculation.
- Provided CLI tooling and Makefile recipes for repeatable workflows and local experimentation.

## Reusable Components
- Standalone utilities (`oldgold/utils.py`, `oldgold/logging_conf.py`) and the AMM math in `oldgold/sim/v2_math.py` are self-contained and easily portable.
- GraphQL client and scanning logic (`oldgold/scanner/*`) can be adapted for other pool discovery tasks.
- Tax probe logic (`oldgold/tax/probe.py`) may serve as a template for fee-on-transfer token analysis.

## Real vs. Mocked Functionality
- Core modules interact with real networks (HTTP RPCs, subgraph endpoints, live transactions). There are no mocks in the implementation; dry-run modes simply skip transaction submission and return zeroed results.
- Unit tests focus on pure mathematical functions and therefore do not mock or interact with external services.

## Test Results
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q` → all 5 tests pass, validating AMM math and simulation helpers.

## Final Notes
- The project is functional for manual experimentation but lacks production hardening and extensive coverage.
- Sensitive operations (live swaps) assume the environment variables `RPC_*` and `PK` are set; ensure keys used are dust-only.

