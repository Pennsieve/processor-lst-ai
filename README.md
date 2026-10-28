# processor-lst-ai

White-matter hyperintensity (WMH / MS-type lesion) segmentation for the
**Clinical Brain MRI Volumetrics** workflow, with [LST-AI](https://github.com/CompImg/LST-AI)
2.0.0rc1 (Wiltgen, McGinnis et al. 2024) on CPU. For every subject that has both a
T1w and a FLAIR volume it runs

```
lst --t1 <T1w> --flair <FLAIR> --output <tmp>/out --temp <tmp>/work \
    --device cpu --threads THREADS --threshold THRESHOLD [--segment_only] [--probability_map]
```

and keeps the binary lesion mask, the ensemble probability map and (unless
`SEGMENT_ONLY`) the McDonald-region labels, plus a lesion volume / count table.

LST-AI harmonises the q/s-forms, affinely registers T1w and FLAIR to MNI152 with
greedy, skull-strips the MNI T1w with HD-BET and applies that mask to the FLAIR, runs
its three 3D U-Nets on the 192³ MNI grid, averages them, thresholds, and warps the
result back onto the **FLAIR grid**. All files this app writes are therefore in
**native FLAIR space** (same shape and affine as the input FLAIR), not MNI.

The base image is `jqmcginnis/lst-ai:v2.0.0rc1-cpu` (multi-arch amd64/arm64,
weights and atlas bundled, nothing downloaded at run time). The tag `v2.0.0-cpu` the
LST-AI README mentions does not exist yet. See [THIRD_PARTY.md](THIRD_PARTY.md) for
licences and citations. LST-AI is a research tool, not validated or approved for
clinical use.

## Inputs

Both inputs have `placement: subfolder` and are matched by **subject label** (the
part of the file name before the first `_`, e.g. `sub-010200`).

| Input | Takes | Found in |
|---|---|---|
| `t1w` | `<sub>_T1w.nii.gz` (or `.nii`), **not** skull-stripped: the raw/reoriented T1w from the prep step (`nifti-prep` → `t1w/`) | `INPUT_DIR/t1w/` if that folder exists (recursively), else all of `INPUT_DIR` filtered by the `_T1w` suffix |
| `flair` | `<sub>_FLAIR.nii.gz` (or `.nii`), not skull-stripped (`nifti-prep` → `flair/`) | `INPUT_DIR/flair/` if that folder exists, else all of `INPUT_DIR` filtered by the `_FLAIR` suffix |

A subject that has only one of the two is skipped with a log line. Plain `.nii` inputs
are re-saved as `.nii.gz` in the temp folder first (`lst` insists on gzipped NIfTI).

## Outputs

Two outputs, so each goes to its own folder under `OUTPUT_DIR`. Every file is in the
subject's FLAIR space.

| Output | Files |
|---|---|
| `lesions` | `<sub>_desc-wmh_mask.nii.gz` — binary lesion mask, uint8 0/1 (LST-AI's `space-flair_seg-lst.nii.gz`, re-saved as uint8) |
| | `<sub>_desc-wmh_probseg.nii.gz` — ensemble lesion probability map, float32 in [0,1] (when `PROBABILITY_MAP=true`; LST-AI's `space-FLAIR_seg-lst_prob.nii.gz` from its temp folder) |
| | `<sub>_desc-wmhregions_dseg.nii.gz` — lesion voxels labelled 1 periventricular, 2 juxtacortical, 3 subcortical, 4 infratentorial (only when `SEGMENT_ONLY=false`) |
| | `provenance.json` — app/tool versions, parameters, per-subject inputs, outputs, exact `lst` argv and seconds; `skipped: true` when there was nothing to segment |
| `lesion-volumes` | `<sub>_lesions.csv` — `subject,lesion_volume_mm3,lesion_count` (volume = mask voxels × voxel volume; count = 26-connectivity connected components of the mask, `scipy.ndimage.label` with a 3×3×3 structure) |
| | `lesions.csv` — the same rows for every segmented subject (header only when none) |
| | `<sub>_lesionregions.csv` — LST-AI's own per-region table (`Region,Num_Lesions,Num_Vox,Lesion_Volume`; only when `SEGMENT_ONLY=false`) |

## Parameters

| Parameter | Type | Default | |
|---|---|---|---|
| `SEGMENT_ONLY` | boolean | `true` | Pass `--segment_only`: skip the FastSurfer-based annotation of lesions into McDonald regions. Annotation runs a whole-brain FastSurferVINN segmentation and is much slower on CPU; set to `false` to get `<sub>_desc-wmhregions_dseg.nii.gz` |
| `FAST_MODE` | `true` | One HD-BET model for brain extraction instead of the five-model ensemble (`--fast-mode`); each model is ~10 min on a CPU task |
| `PROBABILITY_MAP` | boolean | `true` | Pass `--probability_map` and keep the ensemble probability map |
| `THRESHOLD` | number | `0.5` | `--threshold`: probability above which a voxel is a lesion |
| `THREADS` | integer | `4` | `--threads` for the greedy registrations; also exported as `OMP_NUM_THREADS` so torch uses the same number |

Not exposed (LST-AI defaults): `--lesion_threshold 0` (no minimum lesion size),
`--clipping 0.5 99.5`, full HD-BET ensemble (no `--fast-mode`), `--device cpu`.

## Optional branch: when there is nothing to segment

This step is an optional branch of the workflow (FLAIR is not always acquired), so an
absent input is not a failure:

- **No FLAIR files at all** (input not bound, or the folder is empty): logs
  `no FLAIR volumes found; lesion segmentation skipped`, creates `lesions/` and
  `lesion-volumes/` (with `lesions.csv` holding only the header and
  `provenance.json` with `"skipped": true`) and **exits 0**.
- **FLAIRs but no T1w at all**: same, with a clear log line, exit 0.
- FLAIRs and T1ws exist but no subject has both: exit 1 with both lists in the log.
- Per-subject failures are logged and the other subjects continue; exit 1 only when
  **every** attempted subject failed.

## Runtime

`computeTypes: [standard]`, 4 vCPU / 16 GiB, `timeoutSeconds: 7200`. Container only
(no Lambda: a run takes far longer than 15 minutes). Runs as uid 1000; the image sets
`HOME=/tmp` so torch/FastSurfer caches have somewhere to go. Each subject's LST-AI
temp folder (about 1 GB with probability maps) is deleted after the subject.

### Measured (one subject, default parameters)

OpenNeuro ds000221 sub-010200 (1 mm MP2RAGE UNI T1w, 1 mm 3D FLAIR), native arm64
Docker Desktop, `THREADS=4`, `--segment_only --probability_map`:

- affine registration to MNI (greedy) + HD-BET (5-fold, accurate mode) on the UNI T1w:
  about 5.5 minutes, no error on the MP2RAGE image; memory 1-3 GiB.
- U-Net ensemble: memory climbs to 6.1 GiB sampled, 6.9 GB RSS; on an 8 GiB Docker
  Desktop VM shared with another container the `lst` process was OOM-killed in model
  3 of 3 about 7 minutes in. Plan on at least 8 GiB free for the container; the
  app.yml asks for 16 GiB on the platform.

## Running it locally

```sh
./sample-input/fetch-sample.sh   # one T1w + FLAIR pair (CC0, OpenNeuro) into data/input/
make run                         # builds the image and runs it as uid 1000 over data/input/
ls data/output/lesions data/output/lesion-volumes
```

`dev.env` holds the environment the container sees (`INPUT_DIR`, `OUTPUT_DIR` and the
four parameters). The base image is multi-arch; `make run` uses your machine's
architecture. To test the exact platform build on Apple silicon, export
`DOCKER_DEFAULT_PLATFORM=linux/amd64` first (slow under emulation). `make test` runs the
processor with the local Python (it needs `lst-ai` installed).

## Citation

Wiltgen T, McGinnis J, Schlaeger S, Kofler F, Voon C, Berthele A, Bischl D, Grundl L,
Will N, Metz M, Schinz D, Sepp D, Prucker P, Schmitz-Koep B, Zimmer C, Menze B,
Rueckert D, Hemmer B, Kirschke J, Mühlau M, Wiestler B. *LST-AI: A deep learning
ensemble for accurate MS lesion segmentation.* NeuroImage: Clinical 42:103611 (2024).
https://doi.org/10.1016/j.nicl.2024.103611

Please also credit greedy and HD-BET and, when `SEGMENT_ONLY=false`, FastSurfer
(references in [THIRD_PARTY.md](THIRD_PARTY.md)).
