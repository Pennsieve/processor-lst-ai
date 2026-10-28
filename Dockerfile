# LST-AI v2.0.0rc1, CUDA flavour: PyTorch (CUDA build), greedy, HD-BET and
# FastSurfer with every model weight and the MNI atlas baked in (no network
# needed at run time). Multi-arch (linux/amd64 + linux/arm64); the platform runs
# amd64. The CUDA torch build also runs on a CPU-only host (DEVICE=auto falls
# back to cpu), so the one image serves both the standard and the gpu runtime.
# About 11 GB; the -cpu tag is the 4 GB alternative if GPU support is dropped.
# NOTE: the tag v2.0.0 does not exist yet; v2.0.0rc1 is the release candidate.
FROM jqmcginnis/lst-ai:v2.0.0rc1

WORKDIR /processor

COPY processor/ /processor/processor/
# provenance.json reports appVersion from this file (main.py reads /processor/VERSION).
COPY VERSION /processor/VERSION

ENV PYTHONPATH="/processor" \
    PYTHONUNBUFFERED=1 \
    # The platform runs the container as uid 1000 without a home directory;
    # torch/matplotlib/FastSurfer may want a writable cache.
    HOME=/tmp \
    MPLCONFIGDIR=/tmp/matplotlib \
    XDG_CACHE_HOME=/tmp/cache

# The base image's ENTRYPOINT is `lst` with CMD `--help`; replace both.
ENTRYPOINT ["python3", "-m", "processor.entry"]
CMD []
