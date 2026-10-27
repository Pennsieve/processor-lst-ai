"""
processor-lst-ai: white-matter lesion (WMH) segmentation with LST-AI.

For every subject that has both a T1w and a FLAIR volume, runs

    lst --t1 <T1w> --flair <FLAIR> --output <tmp>/out --temp <tmp>/work
        --device cpu --threads THREADS --threshold THRESHOLD
        [--segment_only] [--probability_map]

and keeps, in FLAIR space (LST-AI segments in MNI space and warps the result
back to the FLAIR grid):

  OUTPUT_DIR/lesions/<sub>_desc-wmh_mask.nii.gz            binary lesion mask (uint8)
  OUTPUT_DIR/lesions/<sub>_desc-wmh_probseg.nii.gz         ensemble probability map (PROBABILITY_MAP)
  OUTPUT_DIR/lesions/<sub>_desc-wmhregions_dseg.nii.gz     McDonald-region labels (not SEGMENT_ONLY)
  OUTPUT_DIR/lesion-volumes/<sub>_lesions.csv              subject,lesion_volume_mm3,lesion_count
  OUTPUT_DIR/lesion-volumes/<sub>_lesionregions.csv        LST-AI's per-region stats (not SEGMENT_ONLY)
  OUTPUT_DIR/lesion-volumes/lesions.csv                    all subjects
  OUTPUT_DIR/lesions/provenance.json

This is an optional branch of the workflow: with no FLAIR (or no T1w) at all
the app writes empty outputs and exits 0.
"""
from __future__ import annotations

import csv
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import nibabel as nib
import numpy as np
from scipy.ndimage import label as cc_label

from processor.bids_names import by_subject, derived_name, find_input_files, output_dir_for

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger("processor-lst-ai")

APP = "processor-lst-ai"
TOOL = "LST-AI"
OUTPUTS = ["lesions", "lesion-volumes"]
CSV_HEADER = ["subject", "lesion_volume_mm3", "lesion_count"]

# What `lst` writes (see /usr/local/bin/lst in the image).
LST_MASK = "space-flair_seg-lst.nii.gz"                       # in --output
LST_ANNOTATED = "space-flair_desc-annotated_seg-lst.nii.gz"   # in --output, unless --segment_only
LST_ANNOTATED_STATS = "annotated_lesion_stats.csv"            # in --output, unless --segment_only
LST_PROBMAP = "sub-X_ses-Y_space-FLAIR_seg-lst_prob.nii.gz"   # in --temp, with --probability_map


def env_bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None or v.strip() == "":
        return default
    return v.strip().lower() in ("1", "true", "yes", "y", "on")


def env_num(name: str, default, cast):
    v = os.environ.get(name)
    if v is None or v.strip() == "":
        return default
    try:
        return cast(v)
    except ValueError:
        log.warning("%s=%r is not a %s; using %s", name, v, cast.__name__, default)
        return default


def tool_version() -> str:
    try:
        from importlib.metadata import version
        return version("lst-ai")
    except Exception:  # pragma: no cover
        return "unknown"


def as_nii_gz(src: Path, work: Path, stem: str) -> Path:
    """`lst` insists on *.nii.gz inputs; re-save a plain .nii as gzipped."""
    if src.name.endswith(".nii.gz"):
        return src
    dst = work / f"{stem}.nii.gz"
    nib.save(nib.load(str(src)), str(dst))
    return dst


def lesion_stats(mask_path: Path):
    """(binary uint8 image, volume in mm3, 26-connectivity component count)."""
    img = nib.load(str(mask_path))
    data = np.asarray(img.dataobj)
    binary = (data > 0).astype(np.uint8)
    zooms = img.header.get_zooms()[:3]
    voxel_mm3 = float(np.prod(zooms))
    volume = float(binary.sum()) * voxel_mm3
    _, count = cc_label(binary, structure=np.ones((3, 3, 3), dtype=np.uint8))
    hdr = img.header.copy()
    hdr.set_data_dtype(np.uint8)
    out = nib.Nifti1Image(binary, img.affine, hdr)
    return out, volume, int(count)


def run_subject(sub: str, t1w: Path, flair: Path, lesions_dir: Path, volumes_dir: Path, params: dict) -> dict:
    tmp = Path(tempfile.mkdtemp(prefix=f"lst_{sub}_"))
    try:
        out_dir, work_dir = tmp / "out", tmp / "work"
        work_dir.mkdir()
        t1w_in = as_nii_gz(t1w, tmp, f"{sub}_T1w")
        flair_in = as_nii_gz(flair, tmp, f"{sub}_FLAIR")
        cmd = [
            "lst", "--t1", str(t1w_in), "--flair", str(flair_in),
            "--output", str(out_dir), "--temp", str(work_dir),
            "--device", "cpu", "--threads", str(params["THREADS"]),
            "--threshold", str(params["THRESHOLD"]),
        ]
        if params["SEGMENT_ONLY"]:
            cmd.append("--segment_only")
        if params["PROBABILITY_MAP"]:
            cmd.append("--probability_map")
        env = dict(os.environ)
        env.setdefault("OMP_NUM_THREADS", str(params["THREADS"]))
        log.info("[%s] %s", sub, " ".join(cmd))
        t0 = time.monotonic()
        subprocess.run(cmd, check=True, env=env)

        produced = out_dir / LST_MASK
        if not produced.is_file():
            raise FileNotFoundError(f"lst finished but wrote no {LST_MASK} in {out_dir}")

        outputs = []
        mask_img, volume, count = lesion_stats(produced)
        mask_name = derived_name(t1w, "mask", desc="wmh")
        nib.save(mask_img, str(lesions_dir / mask_name))
        outputs.append(f"lesions/{mask_name}")

        if params["PROBABILITY_MAP"]:
            prob = work_dir / LST_PROBMAP
            if prob.is_file():
                prob_name = derived_name(t1w, "probseg", desc="wmh")
                shutil.copyfile(prob, lesions_dir / prob_name)
                outputs.append(f"lesions/{prob_name}")
            else:
                log.warning("[%s] --probability_map was set but %s is missing", sub, prob)

        if not params["SEGMENT_ONLY"]:
            annotated = out_dir / LST_ANNOTATED
            if annotated.is_file():
                dseg_name = derived_name(t1w, "dseg", desc="wmhregions")
                shutil.copyfile(annotated, lesions_dir / dseg_name)
                outputs.append(f"lesions/{dseg_name}")
            stats = out_dir / LST_ANNOTATED_STATS
            if stats.is_file():
                shutil.copyfile(stats, volumes_dir / f"{sub}_lesionregions.csv")
                outputs.append(f"lesion-volumes/{sub}_lesionregions.csv")

        row = {"subject": sub, "lesion_volume_mm3": f"{volume:.3f}", "lesion_count": count}
        with open(volumes_dir / f"{sub}_lesions.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=CSV_HEADER)
            w.writeheader()
            w.writerow(row)
        outputs.append(f"lesion-volumes/{sub}_lesions.csv")

        seconds = round(time.monotonic() - t0, 1)
        log.info("[%s] done in %ss: %d lesions, %.1f mm3", sub, seconds, count, volume)
        return {"subject": sub, "inputs": [f"t1w/{t1w.name}", f"flair/{flair.name}"], "outputs": outputs,
                "command": cmd, "seconds": seconds, "lesion_volume_mm3": round(volume, 3), "lesion_count": count,
                "row": row}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def write_cohort_csv(volumes_dir: Path, rows: list[dict]) -> None:
    with open(volumes_dir / "lesions.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_HEADER)
        w.writeheader()
        for row in rows:
            w.writerow(row)


def main() -> int:
    input_dir = os.environ.get("INPUT_DIR")
    output_dir = os.environ.get("OUTPUT_DIR")
    if not input_dir or not output_dir:
        log.error("INPUT_DIR and OUTPUT_DIR must be set")
        return 2
    if not os.path.isdir(input_dir):
        log.error("INPUT_DIR %s is not a folder", input_dir)
        return 2

    params = {
        "SEGMENT_ONLY": env_bool("SEGMENT_ONLY", True),
        "PROBABILITY_MAP": env_bool("PROBABILITY_MAP", True),
        "THRESHOLD": env_num("THRESHOLD", 0.5, float),
        "THREADS": max(1, env_num("THREADS", 4, int)),
    }
    started = datetime.now(timezone.utc)
    lesions_dir = output_dir_for(output_dir, OUTPUTS, "lesions")
    volumes_dir = output_dir_for(output_dir, OUTPUTS, "lesion-volumes")
    version = Path(__file__).resolve().parent.parent.joinpath("VERSION").read_text().strip() \
        if Path(__file__).resolve().parent.parent.joinpath("VERSION").is_file() else "0.1.0"
    provenance = {
        "app": APP, "appVersion": version, "tool": TOOL, "toolVersion": tool_version(),
        "startedAt": started.isoformat(), "finishedAt": None, "parameters": params,
        "skipped": False, "subjects": [],
    }

    def finish(code: int) -> int:
        provenance["finishedAt"] = datetime.now(timezone.utc).isoformat()
        with open(lesions_dir / "provenance.json", "w") as f:
            json.dump(provenance, f, indent=2)
        return code

    t1ws = by_subject(find_input_files(input_dir, "t1w", ["T1w"]))
    flairs = by_subject(find_input_files(input_dir, "flair", ["FLAIR"]))
    log.info("found %d T1w and %d FLAIR volumes under %s", len(t1ws), len(flairs), input_dir)

    # Optional branch: nothing to segment is not a failure.
    if not flairs:
        log.info("no FLAIR volumes found; lesion segmentation skipped")
        provenance["skipped"] = True
        write_cohort_csv(volumes_dir, [])
        return finish(0)
    if not t1ws:
        log.info("FLAIR volumes found but no T1w volumes; lesion segmentation skipped")
        provenance["skipped"] = True
        write_cohort_csv(volumes_dir, [])
        return finish(0)

    subjects = sorted(set(t1ws) | set(flairs))
    rows, failures, attempted = [], 0, 0
    for sub in subjects:
        if sub not in t1ws or sub not in flairs:
            log.warning("[%s] skipped: needs both a T1w and a FLAIR (has %s)", sub,
                        "T1w" if sub in t1ws else "FLAIR")
            continue
        attempted += 1
        try:
            result = run_subject(sub, t1ws[sub], flairs[sub], lesions_dir, volumes_dir, params)
        except Exception as exc:  # per-subject failure: log, continue
            failures += 1
            log.error("[%s] failed: %s", sub, exc)
            provenance["subjects"].append({"subject": sub, "inputs": [t1ws[sub].name, flairs[sub].name],
                                           "outputs": [], "error": str(exc)})
            continue
        rows.append(result.pop("row"))
        provenance["subjects"].append(result)

    write_cohort_csv(volumes_dir, rows)
    if attempted == 0:
        log.error("no subject has both a T1w and a FLAIR; T1w: %s; FLAIR: %s",
                  sorted(t1ws) or "none", sorted(flairs) or "none")
        return finish(1)
    if failures == attempted:
        log.error("every subject failed (%d of %d)", failures, attempted)
        return finish(1)
    log.info("segmented %d of %d subjects", attempted - failures, attempted)
    return finish(0)


if __name__ == "__main__":
    sys.exit(main())
