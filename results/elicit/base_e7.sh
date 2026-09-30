#!/usr/bin/env bash
# Run E7 for base on the base/Q5 server once base's E6 is done (the main stage keeps that server up while Q5 runs).
cd "$(dirname "$0")/../.."
until [[ -f results/elicit/base/.done_e6 ]]; do sleep 30; done
.venv/bin/python scripts/run_elicit.py eval --label base --model Qwen/Qwen3-8B --strategies E7 2>&1 | grep -vE "HTTP Request|it/s\]|s/it\]" | tail -3
touch results/elicit/base/.done_e7
