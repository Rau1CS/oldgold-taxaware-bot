#!/bin/bash
set -euo pipefail
python -m oldgold.scanner.scan "$@"
