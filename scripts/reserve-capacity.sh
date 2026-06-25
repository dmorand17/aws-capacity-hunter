#!/usr/bin/env bash
set -euo pipefail

# Script: reserve-capacity.sh
# Description: Poll EC2 across multiple AZs to create an On-Demand Capacity
#              Reservation, retrying on a fixed interval until success or deadline.
# Author: domorand
# Date: 2026-06-25

DEPENDENCIES=(aws date)
SCRIPT_NAME=$(basename "$0")

log_info()  { echo "[$(date '+%Y-%m-%d %H:%M:%S')] INFO  $*"; }
log_debug() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] DEBUG $*"; }
log_warn()  { echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARN  $*"; }
log_error() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR $*" >&2; }

function usage() {
    cat <<EOF

Poll EC2 across multiple AZs to create an On-Demand Capacity Reservation,
retrying on a fixed interval until success or deadline.

Usage: ${SCRIPT_NAME} [OPTIONS]

Options:
    -z, --azs       <list>    Space-separated AZs (default: us-east-1a us-east-1b us-east-1c us-east-1d us-east-1f)
    -t, --type      <type>    Instance type (default: g6.xlarge)
    -c, --count     <n>       Instance count (default: 1)
    -i, --interval  <sec>     Seconds between rounds (default: 60)
    -d, --duration  <sec>     Total runtime in seconds, 0 = forever (default: 21600)
    -h, --help                Show this help message

Dependencies: ${DEPENDENCIES[@]}

Examples:
    ${SCRIPT_NAME} -z "us-west-2a us-west-2b" -t g5.xlarge -i 30
    ${SCRIPT_NAME} --type g6.12xlarge --duration 0

EOF
    exit 0
}

function main() {
    local azs="us-east-1a us-east-1b us-east-1c us-east-1d us-east-1f"
    local instance_type="g6.xlarge"
    local instance_count="1"
    local interval="60"
    local duration="21600"

    while [[ $# -gt 0 ]]; do
        case "$1" in
        -z | --azs)      azs="$2";            shift 2 ;;
        -t | --type)     instance_type="$2";  shift 2 ;;
        -c | --count)    instance_count="$2"; shift 2 ;;
        -i | --interval) interval="$2";       shift 2 ;;
        -d | --duration) duration="$2";       shift 2 ;;
        -h | --help) usage ;;
        *)
            log_error "Unknown option: $1"
            usage
            ;;
        esac
    done

    exit_on_missing_tools "${DEPENDENCIES[@]}"

    local -a az_list
    read -ra az_list <<< "$azs"
    [[ ${#az_list[@]} -eq 0 ]] && log_error "--azs must list at least one AZ" && usage

    log_info "============================================"
    log_info "${SCRIPT_NAME}"
    log_info "============================================"
    log_info "  AZs:      ${az_list[*]}"
    log_info "  Type:     $instance_type"
    log_info "  Count:    $instance_count"
    log_info "  Interval: ${interval}s"
    log_info "  Duration: $( [[ "$duration" -eq 0 ]] && echo "forever" || echo "${duration}s" )"
    log_info "============================================"

    reserve_capacity "$instance_type" "$instance_count" "$interval" "$duration" "${az_list[@]}"
}

function reserve_capacity() {
    local instance_type="$1"
    local instance_count="$2"
    local interval="$3"
    local duration="$4"
    shift 4
    local -a az_list=("$@")

    local deadline=0
    [[ "$duration" -gt 0 ]] && deadline=$(( $(date +%s) + duration ))

    while (( deadline == 0 || $(date +%s) < deadline )); do
        local az
        for az in "${az_list[@]}"; do
            log_info "Trying $az..."
            local cr_id
            if cr_id=$(aws ec2 create-capacity-reservation \
                --availability-zone "$az" \
                --instance-type "$instance_type" \
                --instance-platform Linux/UNIX \
                --instance-count "$instance_count" \
                --end-date-type unlimited \
                --query 'CapacityReservation.CapacityReservationId' \
                --output text); then
                log_info "Success in $az — CapacityReservationId: $cr_id"
                echo "$cr_id"
                return 0
            fi
            log_warn "No capacity in $az"
        done
        log_info "No capacity this round; sleeping ${interval}s..."
        sleep "$interval"
    done

    log_error "Deadline reached without a reservation"
    return 1
}

function exit_on_missing_tools() {
    for cmd in "$@"; do
        if ! command -v "$cmd" &>/dev/null; then
            log_error "Required tool '$cmd' is not installed or not in PATH"
            exit 1
        fi
    done
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
    exit 0
fi
