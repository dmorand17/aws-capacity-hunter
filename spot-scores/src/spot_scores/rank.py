"""Group, sort, and top-N ranking of score records (the jq pipeline)."""

from itertools import groupby

from spot_scores.scoring import ScoreRecord


def rank_scores(
    records: list[ScoreRecord],
    top_n: int = 3,
    az_filter: list[str] | None = None,
) -> list[ScoreRecord]:
    """Filter, group by (region, AZ), take top-N by score, sort flat."""
    if az_filter:
        wanted = set(az_filter)
        records = [
            r for r in records if r.availability_zone_id in wanted
        ]

    def group_key(record: ScoreRecord) -> tuple[str, str]:
        return (record.region, record.availability_zone_id)

    ranked: list[ScoreRecord] = []
    for _, group in groupby(sorted(records, key=group_key), key=group_key):
        members = sorted(group, key=lambda r: -r.score)
        ranked.extend(members[:top_n])

    ranked.sort(
        key=lambda r: (r.region, r.availability_zone_id, -r.score)
    )
    return ranked
