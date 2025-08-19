#!/bin/bash
set -euo pipefail
ruff check . --fix || true
