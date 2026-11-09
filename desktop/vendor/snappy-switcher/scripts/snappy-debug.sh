#!/usr/bin/env bash
# ============================================================================
# snappy-debug.sh — Unified Debugger & Profiler for Snappy Switcher
#
# Modes:
#   --memcheck   Launch daemon under Valgrind (leak-check=full)
#   --trace      Launch daemon under strace (network/file/poll)
#   --hammer     Stress test: 500 rapid IPC commands + CPU/RSS profiling
#
# Usage: ./scripts/snappy-debug.sh <--memcheck|--trace|--hammer> [options]
# ============================================================================
set -euo pipefail

# --- Constants ---
readonly SCRIPT_NAME="$(basename "$0")"
readonly PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
readonly BINARY="${PROJECT_ROOT}/snappy-switcher"
readonly LOG_DIR="${PROJECT_ROOT}/logs"
readonly TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

# --- Helpers ---
info() { printf "${CYAN}[INFO]${NC}  %s\n" "$*"; }
ok() { printf "${GREEN}[OK]${NC}    %s\n" "$*"; }
warn() { printf "${YELLOW}[WARN]${NC}  %s\n" "$*"; }
err() { printf "${RED}[ERR]${NC}   %s\n" "$*" >&2; }
die() {
  err "$*"
  exit 1
}

# --- Preflight ---
preflight() {
  [[ -x "${BINARY}" ]] || die "Binary not found at ${BINARY}. Run 'make' first."
  mkdir -p "${LOG_DIR}"
}

# --- Help ---
print_help() {
  cat <<EOF
${BOLD}Snappy Switcher — Unified Debugger & Profiler${NC}

${BOLD}Usage:${NC}
  ${SCRIPT_NAME} <mode> [options]

${BOLD}Modes:${NC}
  ${GREEN}--memcheck${NC}          Launch daemon under Valgrind with full leak checking.
                      Output: ${DIM}logs/valgrind-<timestamp>.log${NC}

  ${GREEN}--trace${NC}             Launch daemon under strace to monitor Wayland/IPC
                      socket activity (network, file, poll syscalls).
                      Output: ${DIM}logs/strace-<timestamp>.log${NC}

  ${GREEN}--hammer${NC}            Stress test: starts the daemon, then fires 500 rapid
                      'next --silent --linear' IPC commands while sampling
                      CPU% and RSS memory every 200ms.
                      Output: ${DIM}logs/snappy-profile-<timestamp>.csv${NC}

${BOLD}Options:${NC}
  ${GREEN}--config, -c PATH${NC}   Pass a custom config file to the daemon.
  ${GREEN}--count N${NC}           Override hammer command count (default: 500).
  ${GREEN}--help, -h${NC}          Show this help message.

${BOLD}Examples:${NC}
  ${DIM}# Full leak check${NC}
  ./scripts/snappy-debug.sh --memcheck

  ${DIM}# Trace Wayland IPC with custom config${NC}
  ./scripts/snappy-debug.sh --trace -c ./my-config.ini

  ${DIM}# Hammer test with 1000 commands${NC}
  ./scripts/snappy-debug.sh --hammer --count 1000

EOF
}

# ============================================================================
# MODE: --memcheck
# ============================================================================
run_memcheck() {
  local config_args=("$@")
  local logfile="${LOG_DIR}/valgrind-${TIMESTAMP}.log"

  command -v valgrind &>/dev/null || die "valgrind not found. Install: sudo pacman -S valgrind"

  info "Starting daemon under Valgrind..."
  info "Log: ${logfile}"
  echo ""

  # Kill any existing daemon first
  "${BINARY}" quit 2>/dev/null || true
  sleep 0.3

  valgrind \
    --leak-check=full \
    --show-leak-kinds=all \
    --track-origins=yes \
    --track-fds=yes \
    --log-file="${logfile}" \
    "${BINARY}" --daemon "${config_args[@]}" &

  local vpid=$!
  ok "Valgrind PID: ${vpid}"
  info "Daemon is running. Use it normally, then send 'quit' to stop."
  info "  ${DIM}snappy-switcher quit${NC}"
  echo ""

  # Wait for valgrind to finish
  wait "${vpid}" 2>/dev/null || true

  echo ""
  ok "Valgrind session complete."
  info "Report: ${logfile}"

  # Print summary
  if [[ -f "${logfile}" ]]; then
    echo ""
    printf "${BOLD}--- Leak Summary ---${NC}\n"
    grep -A5 "LEAK SUMMARY" "${logfile}" 2>/dev/null || info "(no leak summary found)"
    echo ""
    printf "${BOLD}--- Error Summary ---${NC}\n"
    grep -A3 "ERROR SUMMARY" "${logfile}" 2>/dev/null || info "(no error summary found)"
  fi
}

# ============================================================================
# MODE: --trace
# ============================================================================
run_trace() {
  local config_args=("$@")
  local logfile="${LOG_DIR}/strace-${TIMESTAMP}.log"

  command -v strace &>/dev/null || die "strace not found. Install: sudo pacman -S strace"

  info "Starting daemon under strace..."
  info "Log: ${logfile}"
  echo ""

  # Kill any existing daemon first
  "${BINARY}" quit 2>/dev/null || true
  sleep 0.3

  strace \
    -f \
    -e trace=network,file,poll \
    -o "${logfile}" \
    "${BINARY}" --daemon "${config_args[@]}" &

  local spid=$!
  ok "strace PID: ${spid}"
  info "Daemon is running under strace. Use it normally, then send 'quit' to stop."
  info "  ${DIM}snappy-switcher quit${NC}"
  echo ""

  # Wait for strace to finish
  wait "${spid}" 2>/dev/null || true

  echo ""
  ok "strace session complete."
  info "Full trace: ${logfile}"

  # Print stats
  if [[ -f "${logfile}" ]]; then
    local lines
    lines=$(wc -l <"${logfile}")
    info "Total syscalls captured: ${lines}"
  fi
}

# ============================================================================
# MODE: --hammer
# ============================================================================
run_hammer() {
  local config_args=()
  local cmd_count=500

  # Parse hammer-specific args
  while [[ $# -gt 0 ]]; do
    case "$1" in
    --count)
      cmd_count="${2:?--count requires a number}"
      shift 2
      ;;
    -c | --config)
      config_args+=("$1" "${2:?--config requires a path}")
      shift 2
      ;;
    *)
      config_args+=("$1")
      shift
      ;;
    esac
  done

  local csvfile="${LOG_DIR}/snappy-profile-${TIMESTAMP}.csv"
  local daemon_log="${LOG_DIR}/hammer-daemon-${TIMESTAMP}.log"

  info "=== Snappy Switcher Hammer Test ==="
  info "Commands to fire: ${cmd_count}"
  info "Profile CSV:      ${csvfile}"
  info "Daemon log:       ${daemon_log}"
  echo ""

  # --- Phase 1: Start the daemon ---
  info "Phase 1: Starting daemon..."

  # Kill any existing daemon
  "${BINARY}" quit 2>/dev/null || true
  sleep 0.5

  "${BINARY}" --daemon "${config_args[@]}" &>"${daemon_log}" &
  local daemon_pid=$!

  # Wait for daemon to be ready
  local retries=0
  while ! "${BINARY}" hide 2>/dev/null && [[ $retries -lt 30 ]]; do
    sleep 0.2
    retries=$((retries + 1))
  done

  if ! kill -0 "${daemon_pid}" 2>/dev/null; then
    die "Daemon failed to start. Check ${daemon_log}"
  fi
  ok "Daemon started (PID: ${daemon_pid})"

  # --- Phase 2: Start profiler ---
  info "Phase 2: Starting CPU/RSS profiler (sampling every 200ms)..."
  echo "timestamp_ms,cpu_percent,rss_kb" >"${csvfile}"

  # Background profiler: samples ps every 200ms
  (
    while kill -0 "${daemon_pid}" 2>/dev/null; do
      # ps output: %CPU and RSS (in KB)
      local stats
      stats=$(ps -p "${daemon_pid}" -o %cpu=,rss= 2>/dev/null) || break
      local cpu rss
      cpu=$(echo "${stats}" | awk '{print $1}')
      rss=$(echo "${stats}" | awk '{print $2}')
      local ts
      ts=$(date +%s%3N 2>/dev/null || python3 -c "import time; print(int(time.time()*1000))")
      echo "${ts},${cpu},${rss}" >>"${csvfile}"
      sleep 0.2
    done
  ) &
  local profiler_pid=$!

  # --- Phase 3: Fire commands ---
  info "Phase 3: Firing ${cmd_count} commands..."
  echo ""

  local start_time
  start_time=$(date +%s%N)

  local i=0
  local errors=0
  local progress_interval=$((cmd_count / 20)) # update every 5%
  [[ ${progress_interval} -lt 1 ]] && progress_interval=1

  while [[ $i -lt $cmd_count ]]; do
    if ! "${BINARY}" next --silent --linear 2>/dev/null; then
      errors=$((errors + 1))
    fi
    i=$((i + 1))

    # Progress bar
    if ((i % progress_interval == 0 || i == cmd_count)); then
      local pct=$((i * 100 / cmd_count))
      local filled=$((pct / 5))
      local empty=$((20 - filled))
      printf "\r  ${CYAN}[${NC}"
      printf "%0.s█" $(seq 1 $filled 2>/dev/null) || true
      printf "%0.s░" $(seq 1 $empty 2>/dev/null) || true
      printf "${CYAN}]${NC} %3d%% (%d/%d)" "${pct}" "${i}" "${cmd_count}"
    fi
  done

  local end_time
  end_time=$(date +%s%N)
  echo ""
  echo ""

  # --- Phase 4: Cleanup ---
  info "Phase 4: Stopping daemon and profiler..."

  "${BINARY}" quit 2>/dev/null || true
  sleep 0.5

  # Stop profiler
  kill "${profiler_pid}" 2>/dev/null || true
  wait "${profiler_pid}" 2>/dev/null || true

  # Wait for daemon
  wait "${daemon_pid}" 2>/dev/null || true

  # --- Results ---
  local elapsed_ns=$((end_time - start_time))
  local elapsed_ms=$((elapsed_ns / 1000000))
  local rate=0
  if [[ ${elapsed_ms} -gt 0 ]]; then
    rate=$((cmd_count * 1000 / elapsed_ms))
  fi

  local sample_count=0
  local peak_cpu="0"
  local peak_rss="0"
  local avg_rss="0"

  if [[ -f "${csvfile}" ]]; then
    sample_count=$(($(wc -l <"${csvfile}") - 1)) # minus header
    if [[ ${sample_count} -gt 0 ]]; then
      peak_cpu=$(awk -F',' 'NR>1 {if($2+0 > max) max=$2+0} END {printf "%.1f", max}' "${csvfile}")
      peak_rss=$(awk -F',' 'NR>1 {if($3+0 > max) max=$3+0} END {print int(max)}' "${csvfile}")
      avg_rss=$(awk -F',' 'NR>1 {sum+=$3; n++} END {print int(sum/n)}' "${csvfile}")
    fi
  fi

  echo ""
  printf "${BOLD}╔══════════════════════════════════════════════════╗${NC}\n"
  printf "${BOLD}║         HAMMER TEST RESULTS                      ║${NC}\n"
  printf "${BOLD}╠══════════════════════════════════════════════════╣${NC}\n"
  printf "${BOLD}║${NC}  Commands sent:     %-28s${BOLD}║${NC}\n" "${cmd_count}"
  printf "${BOLD}║${NC}  Errors:            %-28s${BOLD}║${NC}\n" "${errors}"
  printf "${BOLD}║${NC}  Total time:        %-28s${BOLD}║${NC}\n" "${elapsed_ms} ms"
  printf "${BOLD}║${NC}  Throughput:        %-28s${BOLD}║${NC}\n" "${rate} cmd/s"
  printf "${BOLD}║${NC}  Profiler samples:  %-28s${BOLD}║${NC}\n" "${sample_count}"
  printf "${BOLD}║${NC}  Peak CPU:          %-28s${BOLD}║${NC}\n" "${peak_cpu}%"
  printf "${BOLD}║${NC}  Peak RSS:          %-28s${BOLD}║${NC}\n" "${peak_rss} KB"
  printf "${BOLD}║${NC}  Avg RSS:           %-28s${BOLD}║${NC}\n" "${avg_rss} KB"
  printf "${BOLD}╠══════════════════════════════════════════════════╣${NC}\n"
  printf "${BOLD}║${NC}  CSV: %-43s${BOLD}║${NC}\n" "logs/$(basename "${csvfile}")"
  printf "${BOLD}║${NC}  Log: %-43s${BOLD}║${NC}\n" "logs/$(basename "${daemon_log}")"
  printf "${BOLD}╚══════════════════════════════════════════════════╝${NC}\n"
  echo ""

  if [[ ${errors} -eq 0 ]]; then
    ok "All ${cmd_count} commands completed successfully."
  else
    warn "${errors}/${cmd_count} commands failed."
  fi
}

# ============================================================================
# Main
# ============================================================================
main() {
  local mode=""
  local extra_args=()

  if [[ $# -eq 0 ]]; then
    print_help
    exit 0
  fi

  # Parse first argument as mode
  case "$1" in
  --memcheck)
    mode="memcheck"
    shift
    ;;
  --trace)
    mode="trace"
    shift
    ;;
  --hammer)
    mode="hammer"
    shift
    ;;
  --help | -h)
    print_help
    exit 0
    ;;
  *) die "Unknown mode: $1. Use --help for usage." ;;
  esac

  # Collect remaining args
  extra_args=("$@")

  preflight

  case "${mode}" in
  memcheck) run_memcheck "${extra_args[@]}" ;;
  trace) run_trace "${extra_args[@]}" ;;
  hammer) run_hammer "${extra_args[@]}" ;;
  esac
}

main "$@"
