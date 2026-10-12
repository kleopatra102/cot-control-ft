#!/usr/bin/env bash
cd /home/ola/dev/cot-control-ft
.venv/bin/python -c "from huggingface_hub import snapshot_download; snapshot_download('google/gemma-4-31B-it-qat-w4a16-ct')" && echo DOWNLOAD_OK
exec scripts/stego/serve_gemma.sh
