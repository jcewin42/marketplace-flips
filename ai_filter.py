"""Stage 1 / Stage 2 AI classification interface.

This is the one seam meant to change when the Jetson API is ready -
monitor.py calls these two functions unconditionally and never talks to
the Jetson directly. Today they're pass-through stubs so every listing
is treated as UNCERTAIN (shown to you), which matches the "be
conservative" philosophy by default until real filtering exists.

When the Jetson is ready, replace the bodies with HTTP calls, e.g.:

    def filter_stage1(listing: dict) -> dict:
        response = requests.post(
            f"http://{JETSON_HOST}:8000/filter",
            json=listing, timeout=5,
        )
        return response.json()

Categories: RELEVANT, UNCERTAIN, OUT_OF_RANGE, IRRELEVANT.
"""


def filter_stage1(listing: dict) -> dict:
    return {
        "category": "UNCERTAIN",
        "confidence": None,
        "reason": "Stage 1 AI filtering not yet enabled - showing everything",
    }


def filter_stage2(listing: dict, description: str) -> dict:
    return {
        "category": "UNCERTAIN",
        "confidence": None,
        "reason": "Stage 2 AI filtering not yet enabled",
    }
