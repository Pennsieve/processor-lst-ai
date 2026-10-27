# Third-party software

This app is a thin wrapper; the work is done by the tools baked into the base image
`jqmcginnis/lst-ai:v2.0.0rc1-cpu` (Ubuntu 22.04, Python 3.10, PyTorch 2.13 CPU), which is
built from the LST-AI repository's `docker/` folder. Nothing is downloaded at run time: the
LST-AI model bundle and MNI atlas, the HD-BET parameters and the FastSurfer checkpoints are
all in the image.

| Component | Version in image | Licence | What it does here | Link |
|---|---|---|---|---|
| LST-AI (`lst-ai`) | 2.0.0rc1 | MIT (Copyright (c) 2023 Julian McGinnis) | The lesion segmentation pipeline: harmonises affines, registers T1w and FLAIR to MNI152, skull-strips, runs a 3-model 3D U-Net ensemble, warps the mask back to FLAIR space, annotates lesions | https://github.com/CompImg/LST-AI |
| LST-AI model weights (`UNet3D_MS_final_mdl{A,B,C}.pt`) and MNI atlas (`atlas/sub-mni152_*`) | bundled with 2.0.0rc1 | No separate licence stated in the LST-AI repository; distributed with the MIT-licensed package. The README calls LST-AI a research-only tool, not validated or approved for clinical use | Ensemble inference; registration target | https://github.com/CompImg/LST-AI |
| HD-BET (`brainles_hd_bet`) | 0.0.11 | Apache-2.0 (the LICENSE file shipped in the wheel and the upstream repositories MIC-DKFZ/HD-BET and BrainLesion/HD-BET; note the wheel's METADATA field says "AGPL-3.0", which contradicts its own LICENSE file) | Skull stripping of the MNI-registered T1w (5-fold ensemble, "accurate" mode) | https://github.com/MIC-DKFZ/HD-BET, https://github.com/BrainLesion/HD-BET |
| HD-BET parameters (`model_weights/{0..4}.model`) | from Zenodo record 2540695 | Distributed with HD-BET; no separate licence stated in the package | Skull-stripping network weights | https://zenodo.org/record/2540695 |
| greedy (`picsl_greedy`) | 1.4.0.1 | Apache-2.0 (LICENSE in the wheel; GitHub reports Apache-2.0 for pyushkevich/greedy) | Affine registration to MNI and the inverse warps back to FLAIR space | https://github.com/pyushkevich/greedy |
| FastSurfer | v2.5.4 (at `/usr/share/lst-ai/FastSurfer-v2.5.4`), checkpoints `aparc_vinn_{axial,coronal,sagittal}_v2.0.0.pkl` | Apache-2.0 (repository LICENSE; the checkpoints ship under the same repository) | Whole-brain segmentation (`--seg_only`, FastSurferVINN) used to label lesions as periventricular / juxtacortical / subcortical / infratentorial. Only runs when `SEGMENT_ONLY=false`. No FreeSurfer licence is needed for `--seg_only` | https://github.com/Deep-MI/FastSurfer |
| PyTorch, torchio, torch-interpol, nibabel, NumPy, SciPy, pandas | 2.13.0+cpu, 1.2.1, 0.3.0, 5.4.2, 2.2.6, 1.15.3, 2.3.3 | BSD-3-Clause / Apache-2.0 / MIT / MIT / BSD-3-Clause / BSD-3-Clause / BSD-3-Clause | Runtime libraries; nibabel/NumPy/SciPy are also used by this app's `main.py` for the binary mask, lesion volume and 26-connectivity lesion count | |

## Citations

LST-AI:

> Wiltgen T, McGinnis J, Schlaeger S, Kofler F, Voon C, Berthele A, Bischl D, Grundl L, Will N,
> Metz M, Schinz D, Sepp D, Prucker P, Schmitz-Koep B, Zimmer C, Menze B, Rueckert D, Hemmer B,
> Kirschke J, Mühlau M, Wiestler B. LST-AI: A deep learning ensemble for accurate MS lesion
> segmentation. NeuroImage: Clinical 42:103611 (2024). https://doi.org/10.1016/j.nicl.2024.103611

HD-BET:

> Isensee F, Schell M, Pflueger I, et al. Automated brain extraction of multisequence MRI using
> artificial neural networks. Human Brain Mapping 40(17):4952-4964 (2019).

greedy:

> Yushkevich PA, Pluta J, Wang H, Wisse LEM, Das S, Wolk D. IC-P-174: Fast automatic segmentation
> of hippocampal subfields and medial temporal lobe subregions in 3 Tesla and 7 Tesla T2-weighted
> MRI. Alzheimer's & Dementia 12:P126-P127 (2016).

FastSurfer (only when `SEGMENT_ONLY=false`):

> Henschel L, Conjeti S, Estrada S, Diers K, Fischl B, Reuter M. FastSurfer - A fast and accurate
> deep learning based neuroimaging pipeline. NeuroImage 219:117012 (2020).
> Henschel L, Kügler D, Reuter M. FastSurferVINN: Building resolution-independence into deep
> learning segmentation methods - A solution for HighRes brain MRI. NeuroImage 251:118933 (2022).
