#!/usr/bin/env bash
# Overnight chain on the two RTX 4080s; run the same file on both, nothing else needs to stay connected.
#   skynet2: overnight.sh sampler      skynet1: overnight.sh trainer
# 1. RL on DeepSeek-R1-Distill-Llama-8B: base and v1 arm B (word bans held out), seeds 0-2, interleaved.
# 2. skynet2 only: DeepSeek-R1-Distill-Qwen-7B controllability chain (results/r1qwen7/stage.sh: base evals, arm Bnc
#    data, training, evals), then it publishes the adapter on the LAN for skynet1.
# 3. RL on DeepSeek-R1-Distill-Qwen-7B: base and Bnc, seeds 0-2, interleaved.
set -u
ROLE=$1; D=~/dev/cot-control-ft/results; RL=$D/rl_local; PY=~/dev/ext/ilinca-stego-rl/.venv-rl/bin/python
log() { echo "$(date '+%m-%d %H:%M') $(hostname) $*" | tee -a $RL/overnight_$(hostname).log; }
cd $RL
log "1. RL on R1-Distill-Llama-8B"
OUT=$RL/r1llama CK=$D/r1llama/ckpts BASE=unsloth/deepseek-r1-distill-llama-8b-unsloth-bnb-4bit NOCOPY=1 MB=${MB_LLAMA:-1} \
  ./rlsplit.sh $ROLE base:0 B:0 base:1 B:1 base:2 B:2
CK7=$D/r1qwen7/ckpts; PUB=$D/r1qwen7/pub; TAR=http://192.168.1.202:8766/Bnc.tar
if [[ $ROLE == sampler ]]; then
  log "2. controllability chain on R1-Distill-Qwen-7B"
  $D/r1qwen7/stage.sh > $D/r1qwen7/stage.out 2>&1 || log "stage.sh exited $? (see results/r1qwen7/stage.log)"
  [[ -f $CK7/Bnc/step-final/adapter_config.json ]] || { log "no Bnc adapter: stopping before the Qwen-7B RL"; exit 1; }
  mkdir -p $PUB && tar cf $PUB/Bnc.tar.part -C $CK7/Bnc step-final && mv $PUB/Bnc.tar.part $PUB/Bnc.tar
  nohup setsid python3 -m http.server 8766 --bind 192.168.1.202 --directory $PUB > $PUB/http.log 2>&1 < /dev/null &
else
  log "2. waiting for skynet2 to publish the Bnc adapter"
  until curl -sfI -m 5 $TAR > /dev/null; do sleep 60; done
  mkdir -p $CK7/Bnc && curl -sf $TAR | tar xf - -C $CK7/Bnc || { log "could not fetch the adapter"; exit 1; }
fi
BASE7=$($PY -c "import json;print(json.load(open('$CK7/Bnc/step-final/adapter_config.json'))['base_model_name_or_path'])")
HF_HUB_DISABLE_TELEMETRY=1 $PY -c "from huggingface_hub import snapshot_download; snapshot_download('$BASE7')" > /dev/null 2>&1 \
  || { log "could not get $BASE7"; exit 1; }
log "3. RL on R1-Distill-Qwen-7B (base $BASE7)"
OUT=$RL/r1qwen7 CK=$CK7 BASE=$BASE7 NOCOPY=1 STRUCT=Bnc MB=1 ./rlsplit.sh $ROLE base:0 Bnc:0 base:1 Bnc:1 base:2 Bnc:2
log "overnight chain finished"
