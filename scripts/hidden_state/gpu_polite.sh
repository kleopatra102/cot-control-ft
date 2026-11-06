# Sourced by the hidden-state queue scripts: use skynet4's shared GPU only when nobody else needs it.
#   wait_free        block until the GPU is free (under 1.5 GB in use, FREE_CHECKS checks 5 min apart, default 3) and
#                    nobody has asked for it;
#                    then record which other users' GPU processes are there (e.g. an idle server under 1.5 GB)
#   run_watched CMD  run CMD in its own process group; every 15 s, stop it (and return 75) if another user starts a GPU
#                    process, another user's GPU memory grows by more than 300 MB, or the request file exists
#   kill_group PID   stop a process group started with setsid
# Anyone can ask for the GPU with `touch /tmp/gpu_please`: the queue stops within 15 s and does not restart while the
# file exists (for at most 12 h after it was last touched, so a forgotten file cannot block it forever); delete the
# file when done.
REQUEST=/tmp/gpu_please; REQUEST_MAX_S=$((12 * 3600))
log() { echo "[$(date '+%m-%d %H:%M')] $*"; }

requested() {  # the request file exists and is under 12 h old
  [[ -e $REQUEST ]] && (( $(date +%s) - $(stat -c %Y "$REQUEST") < REQUEST_MAX_S ))
}

others() {  # "pid:MiB" for every GPU process not owned by this user
  nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader,nounits 2>/dev/null | while IFS=', ' read -r pid mem; do
    [[ -n $pid && $(ps -o user= -p "$pid" 2>/dev/null) != "$USER" ]] && echo "$pid:$mem"
  done
}

wait_free() {
  local free=0 used
  while (( free < ${FREE_CHECKS:-3} )); do
    used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -1)
    if (( used < 1500 )) && ! requested; then free=$((free+1)); else free=0; fi
    log "GPU used ${used} MiB$(requested && echo ', requested by someone (/tmp/gpu_please)'), free checks: $free"
    (( free < ${FREE_CHECKS:-3} )) && sleep 300
  done
  BASE_OTHERS=$(others | sort)
  BASE_OTHER_MIB=$(echo "$BASE_OTHERS" | awk -F: '{s+=$2} END {print s+0}')
}

someone_else() {  # prints the reason and succeeds if the GPU should be given back
  if requested; then echo "request file $REQUEST"; return 0; fi
  local now new mib
  now=$(others | sort)
  new=$(comm -13 <(echo "$BASE_OTHERS" | cut -d: -f1 | sort) <(echo "$now" | cut -d: -f1 | sort) | grep -v '^$' | head -1)
  if [[ -n $new ]]; then echo "new GPU process $new of user $(ps -o user= -p "$new" 2>/dev/null)"; return 0; fi
  mib=$(echo "$now" | awk -F: '{s+=$2} END {print s+0}')
  if (( mib > BASE_OTHER_MIB + 300 )); then echo "other users' GPU memory ${BASE_OTHER_MIB} -> ${mib} MiB"; return 0; fi
  return 1
}

kill_group() {
  kill -TERM -- "-$1" 2>/dev/null; for _ in $(seq 30); do kill -0 -- "-$1" 2>/dev/null || return 0; sleep 1; done
  kill -KILL -- "-$1" 2>/dev/null
}

run_watched() {
  setsid "$@" & local pid=$! why
  while kill -0 "$pid" 2>/dev/null; do
    if why=$(someone_else); then log "giving the GPU back: $why"; kill_group "$pid"; wait "$pid" 2>/dev/null; return 75; fi
    sleep 15
  done
  wait "$pid"
}
