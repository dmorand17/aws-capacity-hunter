#!/usr/bin/env bash
set -euo pipefail

# Script: reserve-capacity.sh
# DEPRECATED: superseded by the `capacity-hunter reserve` command in the
#             spot-scores Python CLI (see ../../spot-scores/README.md).
#             Kept for reference only.
# Description: Poll EC2 across multiple AZs to create an On-Demand Capacity
#              Reservation, retrying on a fixed interval until success or deadline.
# Author: domorand
# Date: 2026-06-25

DEPENDENCIES=(aws date)
SCRIPT_NAME=$(basename "$0")

# All logs go to stderr so stdout carries only the reservation ID for capture.
log_info()  { echo "[$(date '+%Y-%m-%d %H:%M:%S')] INFO  $*" >&2; }
log_debug() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] DEBUG $*" >&2; }
log_warn()  { echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARN  $*" >&2; }
log_error() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR $*" >&2; }

function usage() {
    cat <<EOF >&2

Poll EC2 across multiple AZs to create an On-Demand Capacity Reservation,
retrying on a fixed interval until success or deadline.

Usage: ${SCRIPT_NAME} --type <type> [OPTIONS]

Options:
    -t, --type      <type>    Instance type (required, e.g. g6.xlarge)
    -z, --azs       <list>    Space-separated AZs (default: us-east-1a us-east-1b us-east-1c us-east-1d us-east-1f)
    -c, --count     <n>       Instance count (default: 1)
    -i, --interval  <sec>     Seconds between rounds (default: 60)
    -d, --duration  <sec>     Total runtime in seconds, 0 = forever (default: 21600)
    -h, --help                Show this help message

Dependencies: ${DEPENDENCIES[@]}

Examples:
    ${SCRIPT_NAME} --type g6.xlarge
    ${SCRIPT_NAME} -z "us-west-2a us-west-2b" -t g5.xlarge -i 30
    ${SCRIPT_NAME} --type g6.12xlarge --duration 0

EOF
    exit "${1:-1}"
}

function main() {
    [[ $# -eq 0 ]] && usage 1

    local azs="us-east-1a us-east-1b us-east-1c us-east-1d us-east-1f"
    local instance_type=""
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
        -h | --help) usage 0 ;;
        *)
            log_error "Unknown option: $1"
            usage 1
            ;;
        esac
    done

    exit_on_missing_tools "${DEPENDENCIES[@]}"

    [[ -z "$instance_type" ]] && log_error "--type is required" && usage 1

    local -a az_list
    read -ra az_list <<< "$azs"
    [[ ${#az_list[@]} -eq 0 ]] && log_error "--azs must list at least one AZ" && usage 1

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
            local result rc=0
            result=$(create_reservation "$az" "$instance_type" "$instance_count") || rc=$?
            case "$rc" in
            0)
                print_success_summary "$result" "$az" "$instance_type" "$instance_count"
                echo "$result"
                return 0
                ;;
            2)  # Insufficient capacity — expected; try the next AZ.
                log_warn "No capacity in $az"
                ;;
            3)  # Throttling — back off, but keep trying.
                log_warn "Throttled by EC2 in $az (RequestLimitExceeded); consider a longer --interval"
                ;;
            *)  # Anything else (bad type, auth, invalid AZ) is fatal.
                log_error "Aborting in $az: ${result:-unknown error}"
                return 1
                ;;
            esac
        done
        local remaining="forever"
        [[ "$deadline" -gt 0 ]] && remaining="$(( deadline - $(date +%s) ))s left"
        log_info "No capacity this round ($remaining); sleeping ${interval}s..."
        sleep "$interval"
    done

    log_error "Deadline reached after ${duration}s without securing a reservation for $instance_type"
    return 1
}

# Attempts one create-capacity-reservation call against a single AZ.
# On success: prints the CapacityReservationId to stdout, returns 0.
# Otherwise prints the AWS error message to stdout and returns a class code:
#   2 = insufficient capacity, 3 = throttling, 1 = fatal (caller should abort).
function create_reservation() {
    local az="$1" instance_type="$2" instance_count="$3"

    local output rc=0
    output=$(aws ec2 create-capacity-reservation \
        --availability-zone "$az" \
        --instance-type "$instance_type" \
        --instance-platform Linux/UNIX \
        --instance-count "$instance_count" \
        --end-date-type unlimited \
        --query 'CapacityReservation.CapacityReservationId' \
        --output text 2>&1) || rc=$?

    echo "$output"
    [[ "$rc" -eq 0 ]] && return 0
    classify_aws_error "$output"
}

# Maps an AWS error message to a retry class. See create_reservation for codes.
function classify_aws_error() {
    local message="$1"
    case "$message" in
    *InsufficientInstanceCapacity* | *InsufficientCapacity*) return 2 ;;
    *RequestLimitExceeded* | *Throttling*)                   return 3 ;;
    *)                                                       return 1 ;;
    esac
}

function print_success_summary() {
    local cr_id="$1" az="$2" instance_type="$3" instance_count="$4"
    log_info "============================================"
    log_info "  ✅ Capacity reservation created"
    log_info "  --------------------------------------"
    log_info "  Reservation: $cr_id"
    log_info "  AZ:          $az"
    log_info "  Type:        $instance_type"
    log_info "  Count:       $instance_count"
    log_info "  Platform:    Linux/UNIX"
    log_info "  Expiry:      unlimited (bills until cancelled)"
    log_info "  --------------------------------------"
    log_info "  Release with:"
    log_info "    aws ec2 cancel-capacity-reservation --capacity-reservation-id $cr_id"
    log_info "============================================"
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
