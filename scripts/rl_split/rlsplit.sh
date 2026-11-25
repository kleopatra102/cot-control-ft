#!/usr/bin/env bash
# Split GRPO for Qwen3-8B across two RTX 4080s: this script runs on both machines with the SAME job list.
#   skynet2:  rlsplit.sh sampler base:0 B:0 N:0 ...     one vLLM sampler per job, exits each when the trainer says so
#   skynet1:  rlsplit.sh trainer base:0 B:0 N:0 ...     waits for the matching sampler, trains, then releases it
# Recipe as rlq.sh: coinflip, no notice, no SFT, 3/6/10-step problems, linear penalty 0.06 per banned string, T 1.1,
# 8 prompts x 8 samples, 2048 tokens, 60 steps. Arms: base (fresh LoRA), B (v2 within-family), N (no-ban split).
# STEPS=<n> shortens a run (smoke tests); TAG=<suffix> names its directory.
# Reward calibration: when $OUT/CALIBRATE exists (it holds SHAPE=sqrt|linear and Q=<quantile>), a 2-step base run
# "calib:0" goes first; calibrate.py reads its completions' banned-string counts and writes $OUT/reward.env
# (PENALTY, PER_MENTION = 1 / the Q quantile of the counts), which every later run of this model uses. Without
# reward.env the penalty is linear, 0.06 per banned string.
# Length gate: when $OUT/LENGTH_GATE exists (it holds GATE_REF=<control arm>, GATE_LO=<ratio>, GATE_HI=<ratio> and
# GATE_SEEDS="<seeds>", all four required), a 2-step run "gate-<arm>:<seed>" of the control arm and of every treated arm
# in the job list goes first. length_gate.py then compares the step-0 completions (sampled before any update): median
# reasoning words, treated / control, must lie in GATE_LO..GATE_HI or every remaining job is skipped. The result is
# in $OUT/length_gate_<arm>.json. Set the band before the runs; the file must be the same on both machines.
set -u
ROLE=$1; shift
# Model: OUT, CK (adapters at $CK/<arm>/step-final) and BASE default to Qwen3-8B; set all three for another model, plus
# NOCOPY=1 when the adapters' configs already name BASE.
OUT=${OUT:-~/dev/cot-control-ft/results/rl_local/q8}; mkdir -p $OUT
REPO=${REPO:-~/dev/ext/ilinca-strict}; PY=~/dev/ext/ilinca-stego-rl/.venv-rl/bin/python; CK=${CK:-~/dev/cot-control-ft/results/v2_qwen3_8b/ckpts}
SAMPLER_HOST=${SAMPLER_HOST:-192.168.1.202}; PORT=8765; URL=http://$SAMPLER_HOST:$PORT
# 16 GB: score the 64 completions in 32 chunks (Unsloth's mini-batch value is a chunk count), without the all-at-once
# packed / prefix-grouped scoring attempts
export GRPO_MINI_BATCH=${GRPO_MINI_BATCH:-32} UNSLOTH_GRPO_PREFIX_GROUPER=0 UNSLOTH_GRPO_SEQ_PACKING=0
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 VLLM_NO_USAGE_STATS=1 DO_NOT_TRACK=1
log() { echo "$(date '+%m-%d %H:%M') $(hostname) $*" | tee -a $OUT/split_$(hostname).log; }
# RFMT (reasoning format: think | gemma4) and TEXTONLY=1 (Gemma 4: load the text decoder only) select the model family.
RFMT=${RFMT:-think}; TO=(); [[ -n ${TEXTONLY:-} ]] && TO=(--text-only)
BASE=${BASE:-unsloth/Qwen3-8B-unsloth-bnb-4bit}; SFX=${SFX:-${NOCOPY:+step-final}}; SFX=${SFX:-step-final-rl}; MAXSEQ=${MAXSEQ:-2560}; TAG=${TAG:-}
cd $REPO
rlcopy() {  # a copy of the adapter whose config names the 4-bit base the trainer loads (same weights)
  local src=$CK/$1/step-final dst=$CK/$1/step-final-rl
  [[ -f $dst/adapter_config.json ]] || { cp -r $src $dst && sed -i 's|"base_model_name_or_path": "[^"]*"|"base_model_name_or_path": "'$BASE'"|' $dst/adapter_config.json; }
}
armargs() {
  local st=${STRUCT:-B}   # the treated arm whose LoRA target modules the base arm's fresh LoRA copies
  [[ -n ${NOCOPY:-} ]] || { rlcopy $st; [[ $1 == base ]] || rlcopy $1; }
  case $1 in
    base) A=(--target-modules-from $CK/$st/$SFX);;
    *)    A=(--adapter $CK/$1/$SFX);;
  esac
}
HERE=/home/ola/dev/cot-control-ft/results/rl_local
GJOBS=(); GARMS=()
if [[ -f $OUT/LENGTH_GATE ]]; then
  unset GATE_REF GATE_LO GATE_HI GATE_SEEDS; source $OUT/LENGTH_GATE
  [[ -n ${GATE_REF:-} && -n ${GATE_LO:-} && -n ${GATE_HI:-} && -n ${GATE_SEEDS:-} ]] \
    || { log "LENGTH_GATE must set GATE_REF, GATE_LO, GATE_HI and GATE_SEEDS"; exit 2; }
  for job in "$@"; do   # the treated arms: every arm in the job list that is neither base nor the control arm
    arm=${job%%:*}; [[ $arm == base || $arm == $GATE_REF || " ${GARMS[*]} " == *" $arm "* ]] || GARMS+=($arm)
  done
  [[ ${#GARMS[@]} -gt 0 ]] || { log "LENGTH_GATE: no treated arm in the job list"; exit 2; }
  for arm in $GATE_REF "${GARMS[@]}"; do for seed in $GATE_SEEDS; do GJOBS+=(gate-$arm:$seed); done; done
fi
JOBS=("${GJOBS[@]}" "$@"); [[ -f $OUT/CALIBRATE ]] && JOBS=(calib:0 "${JOBS[@]}")
gatecheck() {  # once, before the first run that is neither a calibration nor a gate run
  GATED=1; local arm seed t c
  for arm in "${GARMS[@]}"; do
    t=(); c=()
    for seed in $GATE_SEEDS; do
      t+=($OUT/split${TAG}_gate-${arm}_s$seed/train_samples.jsonl); c+=($OUT/split${TAG}_gate-${GATE_REF}_s$seed/train_samples.jsonl)
    done
    python3 $HERE/length_gate.py --treated "${t[@]}" --control "${c[@]}" --lo $GATE_LO --hi $GATE_HI \
        --out $OUT/length_gate${TAG}_$arm.json 2>&1 | tee -a $OUT/split_$(hostname).log
    [[ ${PIPESTATUS[0]} == 0 ]] || ABORT="length gate not passed for $arm"
  done
}
for job in "${JOBS[@]}"; do
  arm=${job%%:*}; seed=${job##*:}; dir=$OUT/split${TAG}_${arm}_s$seed
  JSTEPS=${STEPS:-}; [[ $arm == calib ]] && { arm=base; JSTEPS=2; }
  [[ $arm == gate-* ]] && { arm=${arm#gate-}; JSTEPS=2; }
  armargs $arm
  LBL="$(basename $OUT):$job$TAG"   # names the model too, so a trainer never pairs with another model's sampler
  if [[ $ROLE == sampler ]]; then
    log "sampler up for $job$TAG"
    $PY scripts/hf_rl_sampler.py "${A[@]}" --base-model $BASE --max-seq $MAXSEQ --gpu-mem ${GPUMEM:-0.85} --seed $seed \
        --host $SAMPLER_HOST --port $PORT --job "$LBL" "${TO[@]}" > $OUT/sampler${TAG}_${arm}_s$seed.out 2>&1
    log "sampler for $job$TAG exited ($?)"; sleep 5
  else
    [[ ${#GJOBS[@]} -eq 0 || -n ${GATED:-} || $job == calib:* || $job == gate-* ]] || gatecheck
    if [[ -f $dir/.done ]]; then
      log "skip $job: done"
      if [[ $job == gate-* ]]; then   # both machines add the gate runs themselves, so its sampler is up: release it
        until [[ "$(curl -s -m 5 $URL/job)" == "{\"job\": \"$LBL\"}" ]]; do sleep 15; done
        curl -s -m 20 -X POST $URL/quit > /dev/null; sleep 20
      fi
      continue
    fi
    log "waiting for the sampler for $job$TAG"
    until [[ "$(curl -s -m 5 $URL/job)" == "{\"job\": \"$LBL\"}" ]]; do sleep 15; done
    if [[ -n ${ABORT:-} ]]; then log "skip $job: $ABORT"; curl -s -m 20 -X POST $URL/quit > /dev/null; sleep 20; continue; fi
    PENALTY=linear; PER_MENTION=0.06
    if [[ -f $OUT/CALIBRATE && $job != calib:* ]]; then
      if [[ -f $OUT/reward.env ]]; then source $OUT/reward.env; else log "NO CALIBRATION for $job: linear 0.06"; fi
    fi
    rm -rf $dir; log "start $job$TAG (penalty $PENALTY, per mention $PER_MENTION)"
    [[ $arm == base ]] && ARM=(--arm base) || ARM=(--arm treated)
    RL_REMOTE_SAMPLER=$URL $PY scripts/hf_rl_train.py "${ARM[@]}" "${A[@]}" --task coinflip --notice none --answer-format strict \
        --monitor banned:coinflip.t2_v2 --monitor-reply --n-steps 3,6,10 --penalty $PENALTY --per-mention $PER_MENTION --temperature 1.1 \
        --no-sft --base-model $BASE --max-tokens 2048 --max-seq $MAXSEQ --micro-batch ${MB:-1} --gpu-mem 0.5 --groups 8 \
        --group-size 8 --reasoning-format $RFMT "${TO[@]}" ${JSTEPS:+--steps $JSTEPS} --seed $seed --log-dir $dir > $dir.out 2>&1 \
      && touch $dir/.done && log "done $job$TAG: $(tail -1 $dir/metrics.jsonl | cut -c1-200)" \
      || log "FAILED $job$TAG: $(grep -E 'Error|Killed|SystemExit|sampler' $dir.out | tail -1 | cut -c1-300)"
    if [[ $job == calib:* ]]; then
      [[ -f $dir/.done || -z ${STOP_ON_CALIB_FAIL:-} ]] || ABORT="calibration run failed"
      (source $OUT/CALIBRATE; python3 $HERE/calibrate.py $dir/train_samples.jsonl $SHAPE $Q $OUT/reward.env) 2>&1 | tee -a $OUT/split_$(hostname).log
    fi
    curl -s -m 20 -X POST $URL/quit > /dev/null; sleep 20
  fi
done
log "$ROLE queue finished: $*"
