"""Read-only startup-metadata benchmark; does not launch or attach to RTW3."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import platform
import statistics
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/"CampaignOverhaul"))
import modern_research as modern
import weekly_runtime as rt


def measure(call, count):
    samples = []
    for _ in range(count):
        began = time.perf_counter()
        value = call()
        samples.append((time.perf_counter()-began)*1000)
    return {"median_ms": statistics.median(samples), "samples_ms": samples}, value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=10)
    args = parser.parse_args()
    if not 3 <= args.samples <= 100:
        parser.error("Use 3 to 100 samples.")
    image = rt.GAME/"RTW3.exe"
    # This is the pre-cache operation, including the disk read and full parse.
    uncached, old = measure(lambda: modern._parse_relocations(image.read_bytes()), args.samples)
    modern._cached_relocations.cache_clear()
    cold, first = measure(modern.text_relocations, 1)
    warm, cached = measure(modern.text_relocations, args.samples)
    if old != first or old != cached:
        raise ValueError("Cached relocation metadata differs from a fresh parse.")
    result = {"ok": True, "measured_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
              "scope": "Repeated PE relocation metadata reads in one Python process, not FPS or full startup time.",
              "python": platform.python_version(), "exe_sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
              "relocations": len(first), "uncached": uncached, "cold_cache": cold, "warm_cache": warm,
              "metadata_equal": True, "game_launched": False}
    (HERE/"framework-benchmark.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
