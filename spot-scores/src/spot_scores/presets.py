"""Named instance-family presets for Spot Placement Score requests.

Preset instance-type lists are explicit and pinned; "current generation"
cannot be reliably auto-discovered. Update these lists as new families ship.
"""

PRESETS: dict[str, dict] = {
    "general": {
        "instance_types": [
            "m6i.2xlarge", "m6a.2xlarge", "m7i.2xlarge", "m7a.2xlarge",
        ],
    },
    "compute": {
        "instance_types": [
            "c6i.2xlarge", "c6a.2xlarge", "c7i.2xlarge", "c7a.2xlarge",
        ],
    },
    "memory": {
        "instance_types": [
            "r6i.2xlarge", "r6a.2xlarge", "r7i.2xlarge", "r7a.2xlarge",
        ],
    },
    "gpu": {
        "instance_types": [
            "g5.2xlarge", "g6.2xlarge", "p4d.24xlarge", "p5.48xlarge",
        ],
    },
    "flexible": {
        "instance_requirements": {
            "ArchitectureTypes": ["x86_64"],
            "InstanceRequirements": {
                "VCpuCount": {"Min": 4, "Max": 16},
                "MemoryMiB": {"Min": 8192, "Max": 65536},
            },
        },
    },
}


def list_presets() -> list[str]:
    """Return preset names in sorted order."""
    return sorted(PRESETS)


def resolve_preset(name: str) -> dict:
    """Return the body of a named preset, or raise KeyError if unknown."""
    if name not in PRESETS:
        valid = ", ".join(list_presets())
        raise KeyError(f"Unknown preset '{name}'. Valid presets: {valid}")
    return PRESETS[name]
