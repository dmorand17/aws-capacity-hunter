#!/usr/bin/env bash
#
# get-spot-scores.sh
#
# DEPRECATED: superseded by the `spot-scores` Python CLI (see ../README.md).
#
# Queries the EC2 Spot Placement Score API using a cli-input-yaml config file.
# Works with both instance-type-based and attribute-based configs.
#
# Usage:
#   ./get-spot-scores.sh <config.yaml> [-n TOP] [-a AZ,...]
#
# Arguments:
#   config.yaml              Path to cli-input-yaml config file (required)
#   -n, --top NUM            Top N results per AZ (default: 3)
#   -a, --az AZ,...          Comma-separated AZ IDs to filter output
#   -h, --help               Show this help message
#
# Requirements:
#   - AWS CLI v2
#   - jq
#   - Permissions: ec2:GetSpotPlacementScores
#

set -euo pipefail

TOP_N=3
AZ_FILTER=""
CONFIG_FILE=""

usage() {
  grep '^#' "$0" | grep -v '^#!/' | sed 's/^# \{0,1\}//'
  exit 0
}

log() { echo "[$(date '+%H:%M:%S')] $*" >&2; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    -n|--top)  TOP_N="$2";     shift 2 ;;
    -a|--az)   AZ_FILTER="$2"; shift 2 ;;
    -h|--help) usage ;;
    -*) echo "Unknown option: $1" >&2; usage ;;
    *)  CONFIG_FILE="$1";      shift ;;
  esac
done

if [[ -z "$CONFIG_FILE" ]]; then
  echo "Error: config file is required." >&2
  echo "Usage: $0 <config.yaml> [-n TOP] [-a AZ,...]" >&2
  exit 1
fi

if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "Error: config file not found: $CONFIG_FILE" >&2
  exit 1
fi

log "Config: $CONFIG_FILE"
log "Querying Spot Placement Scores..."

RESPONSE=$(aws ec2 get-spot-placement-scores \
  --cli-input-yaml "file://$CONFIG_FILE" \
  --output json)

# Build AZ filter for jq
if [[ -n "$AZ_FILTER" ]]; then
  AZ_JQ_FILTER=$(echo "$AZ_FILTER" | jq -R 'split(",")')
else
  AZ_JQ_FILTER="null"
fi

echo ""
echo "Request Parameters ($CONFIG_FILE):"
echo "-------------------------------------------------------------"
cat "$CONFIG_FILE"
echo ""
echo "Top ${TOP_N} per AZ (by score):"
echo "-------------------------------------------------------------"
echo "$RESPONSE" | jq -r --argjson n "$TOP_N" --argjson azf "$AZ_JQ_FILTER" '
  .SpotPlacementScores
  | (if $azf then map(select(.AvailabilityZoneId as $az | $azf | index($az))) else . end)
  | group_by(.Region, .AvailabilityZoneId)
  | map(sort_by(-.Score) | .[:$n])
  | flatten
  | sort_by(.Region, .AvailabilityZoneId, -.Score)
  | .[]
  | [
      ("Score: " + (.Score | tostring)),
      ("Region: " + .Region),
      (if .AvailabilityZoneId != "" then "AZ: " + .AvailabilityZoneId else "" end)
    ]
  | map(select(. != ""))
  | join("  |  ")
'

OUTPUT_FILE="spot-scores-result.json"
echo "$RESPONSE" > "$OUTPUT_FILE"
echo ""
echo "Raw JSON saved to: $OUTPUT_FILE"
