"""Review an emulator run: screenshots, app log and system log, against the port's scenario.

  python _PortStudioMain/tools/shot_review.py <run-dir> [--scenario-json FILE]
  python _PortStudioMain/tools/shot_review.py <run-dir> --check     # fails while the visual review is still PENDING

A run directory is what `emulator_test.py run --scenario` writes (<port>/screenshots/runs/<stamp>_<scenario>_<mode>/).
Two layers, both required before a run counts:

1. Automatic (this tool): every expected shot exists; gameplay shots are not blank; the pairs that must move
   differ; required log lines appear; the system log shows no hang or crash; fps lines are summarised.
2. Visual (the agent or person): open every PNG and fill review.md: which screen it is, whether it is really in
   game, and what is wrong. The automatic layer cannot tell a menu from gameplay; the visual layer decides that.
"""

import argparse
import json
import platform
import time
import re
import sys
from pathlib import Path

try:
    from PIL import Image, ImageChops, ImageStat
except ImportError:  # the report still runs; image checks are marked NOT_RUN
    Image = None

BLANK_STDDEV = 6.0        # luminance standard deviation below this: one flat colour (black, white, a clear colour)
MOTION_MIN_DIFF = 1.5     # mean absolute difference (0-255) below this between two shots: the picture did not change
# Small real changes (a counter, a selection marker, idle unit animation) vanish in the mean of a downscaled picture.
# They pass when enough full-resolution pixels change clearly AND the changes spread over the frame; one blinking element
# (a caret, a focus ring) stays inside a small box and does not pass. Measured on RA2 emulator runs (2026-11-25):
# idle skirmish 0.16 % changed over 22 % of the frame, launcher focus ring 0.07 % inside a 0.25 % box.
MOTION_PIXEL_DELTA = 24        # a pixel counts as changed above this luminance difference (0-255)
MOTION_MIN_CHANGED = 0.0004    # changed pixels / all pixels
MOTION_MIN_SPREAD = 0.02       # area of the box around all changed pixels / frame area
# Fractions of the frame (left, top, right, bottom) masked for the pixel rule: the menu bar and the desktop widget column
# (clock hands, calendar, CPU/FPS meters) change with no app activity. A launcher on the desktop counted as motion before.
OS_CHROME = ((0.0, 0.0, 1.0, 0.035), (0.70, 0.035, 1.0, 0.52))
SAMPLE = (320, 180)
PENDING = "PENDING"


def image_metrics(path):
    if Image is None:
        return {"status": "NOT_RUN", "reason": "Pillow not installed"}
    with Image.open(path) as image:
        small = image.convert("L").resize(SAMPLE)
        stat = ImageStat.Stat(small)
        histogram = small.histogram()
    total = SAMPLE[0] * SAMPLE[1]
    dark = sum(histogram[:16]) / total
    return {"status": "OK", "mean": round(stat.mean[0], 1), "stddev": round(stat.stddev[0], 1),
            "darkFraction": round(dark, 3), "blank": stat.stddev[0] < BLANK_STDDEV}


def difference(a, b):
    if Image is None:
        return None
    with Image.open(a) as left, Image.open(b) as right:
        delta = mask_chrome(ImageChops.difference(left.convert("L").resize(SAMPLE), right.convert("L").resize(SAMPLE)))
        return round(ImageStat.Stat(delta).mean[0], 2)


def mask_chrome(delta):
    """Zero the OS chrome areas of a difference image (see OS_CHROME)."""
    width, height = delta.size
    for box in OS_CHROME:
        delta.paste(0, (int(box[0] * width), int(box[1] * height), int(box[2] * width), int(box[3] * height)))
    return delta


def change_spread(a, b):
    """(changed fraction, spread fraction) at full resolution; None without Pillow or when sizes differ."""
    if Image is None:
        return None
    with Image.open(a) as left, Image.open(b) as right:
        if left.size != right.size:
            return None
        # OS chrome changes on its own (menu-bar clock, the clock/calendar/system widgets at the top right): never motion.
        delta = mask_chrome(ImageChops.difference(left.convert("L"), right.convert("L")))
        width, height = delta.size
        total = width * height
        changed = sum(delta.histogram()[MOTION_PIXEL_DELTA + 1:])
        box = delta.point(lambda v: 255 if v > MOTION_PIXEL_DELTA else 0).getbbox()
    spread = ((box[2] - box[0]) * (box[3] - box[1]) / total) if box else 0.0
    return round(changed / total, 5), round(spread, 4)


def motion_result(a, b):
    """(PASS|FAIL|NOT_RUN, detail text)."""
    diff = difference(a, b)
    if diff is None:
        return "NOT_RUN", "Pillow not installed"
    if diff >= MOTION_MIN_DIFF:
        return "PASS", f"mean diff {diff}"
    spread = change_spread(a, b)
    if spread is None:
        return "FAIL", f"mean diff {diff}"
    changed, area = spread
    ok = changed >= MOTION_MIN_CHANGED and area >= MOTION_MIN_SPREAD
    return ("PASS" if ok else "FAIL"), f"mean diff {diff}, changed {changed:.3%} over {area:.1%} of the frame"


def parse_system_log(text, app_id):
    fps = [float(v) for v in re.findall(rf"nxwin\s+{re.escape(app_id)}: ([\d.]+) fps", text)] if app_id else []
    problems = []
    for pattern, label in ((r"is not responding", "not responding"), (r"(?i)crash(ed)? report|quarantin(e|ed) \S+ after", "crash"),
                           (r"(?i)missing symbol", "missing symbol"), (r"(?i)out of memory|NXN_ERR_NO_MEMORY", "out of memory")):
        for line in text.splitlines():
            if re.search(pattern, line) and (not app_id or app_id in line or label != "not responding"):
                problems.append(f"{label}: {line.strip()[:200]}")
                break
    summary = None
    if fps:
        ordered = sorted(fps)
        summary = {"samples": len(fps), "min": ordered[0], "median": ordered[len(ordered) // 2], "max": ordered[-1]}
    return summary, problems


def log_timeline(text, app_id):
    """Seconds since boot of each `autorun shot NAME` line, of the app's close, and the app's peak heap (MB)."""
    shots = {name: float(t) for t, name in re.findall(r"\[\s*([\d.]+)\]\s+autorun\s+shot (\S+)", text)}
    closed = None
    heap = []
    if app_id:
        match = re.search(rf"\[\s*([\d.]+)\]\s+res\s+{re.escape(app_id)} closed", text)
        closed = float(match.group(1)) if match else None
        heap = [float(v) for v in re.findall(rf"nxwin\s+{re.escape(app_id)}: heap [\d.]+ MB reserved in \d+ chunk\(s\), ([\d.]+) MB", text)]
    return shots, closed, (max(heap) if heap else None)


def review(run_dir, scenario, app_id=None):
    run_dir = Path(run_dir)
    shots = {p.stem: p for p in sorted(run_dir.glob("*.png"))}
    expected = scenario.get("shots") or [s.split()[1] for s in scenario.get("steps", []) if s.split()[:1] == ["shot"]]
    gameplay = scenario.get("gameplay", [])
    checks, metrics = [], {}
    for name in expected:
        checks.append({"check": f"shot {name} captured", "result": "PASS" if name in shots else "FAIL"})
    for name, path in shots.items():
        metrics[name] = image_metrics(path)
    for name in gameplay:
        m = metrics.get(name)
        if not m:
            continue
        result = "NOT_RUN" if m["status"] != "OK" else ("FAIL" if m["blank"] else "PASS")
        checks.append({"check": f"{name} is not blank (stddev {m.get('stddev')})", "result": result})
    for a, b in scenario.get("motion", []):
        if a in shots and b in shots:
            result, detail = motion_result(shots[a], shots[b])
            checks.append({"check": f"picture changed {a} -> {b} ({detail})", "result": result})
        else:
            checks.append({"check": f"picture changed {a} -> {b}", "result": "FAIL", "note": "shot missing"})
    app_log = next(iter(run_dir.glob("*.log")), None)
    app_text = ""
    for log in run_dir.glob("*.log"):
        if log.name != "system.log":
            app_text += log.read_text(encoding="utf-8", errors="replace")
    for pattern in scenario.get("expectLog", []):
        checks.append({"check": f"log has /{pattern}/", "result": "PASS" if re.search(pattern, app_text) else "FAIL"})
    system = run_dir / "system.log"
    fps, problems, peak_heap = None, [], None
    if system.is_file():
        system_text = system.read_text(encoding="utf-8", errors="replace")
        fps, problems = parse_system_log(system_text, app_id)
        shot_times, closed, peak_heap = log_timeline(system_text, app_id)
        # A gameplay shot taken after the app closed shows the desktop, however busy the picture looks.
        for name in gameplay:
            if name in shot_times:
                alive = closed is None or shot_times[name] < closed
                checks.append({"check": f"app still open at {name}", "result": "PASS" if alive else "FAIL",
                               "note": "" if alive else f"app closed at {closed:.1f} s, shot at {shot_times[name]:.1f} s"})
    checks.append({"check": "system log free of hang/crash/missing symbol/OOM",
                   "result": "NOT_RUN" if not system.is_file() else ("FAIL" if problems else "PASS"), "note": "; ".join(problems)})
    failed = [c for c in checks if c["result"] == "FAIL"]
    report = {"runDir": str(run_dir), "appId": app_id, "scenario": scenario.get("name"), "mode": scenario.get("mode"),
              "automatic": "FAIL" if failed else "PASS", "checks": checks, "metrics": metrics, "fps": fps, "peakHeapMB": peak_heap,
              "visualReview": PENDING, "evidenceLevel": "emulator", "hadAppLog": bool(app_log)}
    (run_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_review_md(run_dir, report, expected, gameplay, shots)
    write_evidence(run_dir, report, visual=None)
    return report


def result_id(report):
    return f"STUDIO-{(report.get('scenario') or 'run').upper()}-{(report.get('mode') or 'unknown').upper()}"


def write_evidence(run_dir, report, visual):
    """results.jsonl in the OS device-ingest line format (id, status, metrics, markers) and one performance row.

    The status stays NOT_RUN until the visual review is done: an automatic pass alone is never a gameplay pass.
    Every line is marked environment=emulator; a console run writes its own lines on the device."""
    if report["automatic"] == "FAIL" or visual == "FAIL":
        status = "FAIL"
    elif visual == "PASS":
        status = "PASS"
    else:
        status = "NOT_RUN"
    fps = report.get("fps") or {}
    metrics = {k: v for k, v in {"fps_median": fps.get("median"), "fps_min": fps.get("min"), "fps_max": fps.get("max"),
                                 "peak_heap_mb": report.get("peakHeapMB")}.items() if v is not None}
    markers = ["environment=emulator", f"automatic={report['automatic']}", f"visual={visual or PENDING}",
               f"app={report.get('appId')}", f"mode={report.get('mode')}"]
    markers += [f"{c['result']}: {c['check']}" for c in report["checks"] if c["result"] != "PASS"]
    line = {"id": result_id(report), "status": status, "metrics": metrics, "markers": markers}
    (Path(run_dir) / "results.jsonl").write_text(json.dumps(line) + "\n", encoding="utf-8")
    host = f"{platform.system()} {platform.machine()} {platform.processor() or ''}".strip()
    fps_text = f"{fps.get('median')} (min {fps.get('min')}, max {fps.get('max')})" if fps else "n/a"
    row = (f"| {time.strftime('%Y-%m-%d')} | {report.get('appId')} | {report.get('scenario')} | {report.get('mode')} | "
           f"emulator on {host} | {fps_text} fps | {report.get('peakHeapMB') or 'n/a'} MB | {status} |")
    header = "| Date | App | Scenario | Mode | Hardware | FPS median (min, max) | Peak heap | Result |\n|---|---|---|---|---|---|---|---|\n"
    (Path(run_dir) / "performance_row.md").write_text(header + row + "\n", encoding="utf-8")


def write_review_md(run_dir, report, expected, gameplay, shots):
    path = run_dir / "review.md"
    if path.is_file() and f"Visual review: **{PENDING}**" not in path.read_text(encoding="utf-8"):
        return  # never overwrite a finished visual review
    lines = [f"# Run review: {report['scenario']} ({report['mode']})", "",
             f"Evidence level: emulator. Automatic checks: **{report['automatic']}**. Visual review: **{PENDING}**", "",
             "## Automatic checks", "", "| Check | Result | Note |", "| --- | --- | --- |"]
    lines += [f"| {c['check']} | {c['result']} | {c.get('note', '')} |" for c in report["checks"]]
    fps = report["fps"]
    lines += ["", "FPS (system log, emulator): " + (f"median {fps['median']}, min {fps['min']}, max {fps['max']} over {fps['samples']} samples" if fps else "no samples"),
              f"Peak app heap (system log): {report['peakHeapMB'] if report['peakHeapMB'] is not None else 'n/a'} MB", ""]
    lines += ["## Visual review", "",
              "Open every image. Fill each row, then replace PENDING above with PASS or FAIL.",
              "PASS needs the gameplay shots to show the real game world or the main task, not a menu, loader or error.",
              "A built-in or synthetic program, a generated scene, a test pattern or a status screen is never gameplay: FAIL.", "",
              "| Shot | Expected | Metrics | What the image shows | In game? | Problems |", "| --- | --- | --- | --- | --- | --- |"]
    for name in list(dict.fromkeys(expected + sorted(shots))):
        m = report["metrics"].get(name, {})
        info = f"mean {m.get('mean')} sd {m.get('stddev')}" if m.get("status") == "OK" else "missing" if name not in shots else "n/a"
        lines.append(f"| `{name}.png` | {'gameplay' if name in gameplay else 'screen'} | {info} | | | |")
    lines += ["", "Check in each image: correct resolution and aspect for the mode, no stretched or cut UI, readable text,",
              "HUD present in game, no black or garbage regions, touch/pad prompt matches the mode, no error dialog.", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def check_done(run_dir):
    text = (Path(run_dir) / "review.md").read_text(encoding="utf-8")
    report = json.loads((Path(run_dir) / "report.json").read_text(encoding="utf-8"))
    if f"Visual review: **{PENDING}**" in text:
        print(f"Visual review still PENDING: {run_dir}/review.md")
        return 1
    visual = "PASS" if re.search(r"Visual review: \*\*PASS\*\*", text) else "FAIL"
    write_evidence(run_dir, report, visual)
    print(f"automatic {report['automatic']}, visual {visual}")
    return 0 if report["automatic"] == "PASS" and visual == "PASS" else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--scenario-json", type=Path, help="Scenario block (defaults to scenario.json in the run dir).")
    parser.add_argument("--app-id")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if args.check:
        return check_done(args.run_dir)
    source = args.scenario_json or args.run_dir / "scenario.json"
    scenario = json.loads(source.read_text(encoding="utf-8")) if source.is_file() else {}
    report = review(args.run_dir, scenario, args.app_id or scenario.get("appId"))
    print(f"Automatic: {report['automatic']}. Visual review PENDING: open each PNG and fill {args.run_dir / 'review.md'}.")
    for item in report["checks"]:
        print(f"  {item['result']:7} {item['check']}")
    return 0 if report["automatic"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
