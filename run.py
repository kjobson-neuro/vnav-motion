#!/usr/bin/env python3
"""Flywheel Gear: vnav-motion.

This gear:
1. Reads gear inputs and config via GearContext.
2. Unzips the vNav input if it is a DICOM zip.
3. Runs parse_vNav_Motion.py and writes its motion scores to a CSV.
"""

import csv
import logging
import re
import zipfile
from pathlib import Path

from fw_gear.context import GearContext
from fw_gear.utils.wrapper import exec_command

log = logging.getLogger(__name__)

SCRIPT = "/flywheel/v0/parse_vNav_Motion.py"


def get_subject_id(context: GearContext) -> str | None:
    """Flywheel subject label of the destination container."""
    try:
        dest = context.config.get_destination_container()
        return context.client.get_subject(dest.parents.subject).label
    except Exception as exc:  # metadata lookup is best-effort
        log.warning(f"Could not get subject label from Flywheel: {exc}")
        return None


def prepare_input(input_path: Path, work_dir: Path) -> Path:
    """Extract a DICOM zip into work_dir; a single DICOM's folder is used as-is."""
    if not zipfile.is_zipfile(input_path):
        return input_path.parent
    extract_dir = work_dir / "vnav_dicom"
    with zipfile.ZipFile(input_path) as zf:
        zf.extractall(extract_dir)
    log.info(f"Extracted {input_path.name} to {extract_dir}")
    # Flywheel DICOM zips hold the DICOMs inside a single top-level folder
    subdirs = [p for p in extract_dir.iterdir() if p.is_dir()]
    if len(subdirs) == 1:
        return subdirs[0]
    return extract_dir


def build_command(context: GearContext, vnav_dir: Path) -> list[str]:
    """Build the parse_vNav_Motion.py command from gear config."""
    config = context.config.opts
    cmd = [
        "python3",
        SCRIPT,
        "--tr",
        str(config["tr"]),
        "--input-dir",
        str(vnav_dir),
        "--rms",
        "--max",
    ]
    if config.get("radius") is not None:
        cmd.extend(["--radius", str(config["radius"])])
    return cmd


def parse_output(stdout: str) -> dict:
    """Pull the mean scores and any vNav failure from the script's output."""
    rms = re.search(r"MeanMotionScoreRMSPerMin:\s*(\S+)", stdout)
    mx = re.search(r"MeanMotionScoreMaxPerMin:\s*(\S+)", stdout)
    failed = re.search(r"failure detected instance=(\S+), acquisition=(\S+)", stdout)
    return {
        "MeanMotionScoreRMSPerMin": rms.group(1),
        "MeanMotionScoreMaxPerMin": mx.group(1),
        "FailedInstance": failed.group(1) if failed else "",
        "FailedAcquisition": failed.group(2) if failed else "",
    }


def main(context: GearContext) -> None:
    """Execute main gear workflow."""
    input_path = Path(context.config.get_input_path("vnav"))
    vnav_dir = prepare_input(input_path, Path(context.work_dir))
    subject_id = get_subject_id(context)

    cmd = build_command(context, vnav_dir)
    log.info(f"Running vNav motion: {cmd}")
    stdout, _, _ = exec_command(cmd, stream=True)  # raises RuntimeError on non-zero exit

    row = {"subject_id": subject_id or "", **parse_output(stdout)}
    name = f"{subject_id}_vnav_motion.csv" if subject_id else "vnav_motion.csv"
    out_file = Path(context.output_dir) / name
    with open(out_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
    log.info(f"Wrote {out_file}")


if __name__ == "__main__":
    with GearContext() as context:
        context.init_logging()
        context.log_config()
        main(context)
