# LST-AI v2.0.0rc1, CPU flavour: PyTorch inference, greedy, HD-BET and FastSurfer
# with every model weight and the MNI atlas baked in (no network needed at run
# time). Multi-arch (linux/amd64 + linux/arm64); the platform runs amd64.
# NOTE: the tag v2.0.0-cpu does not exist yet; v2.0.0rc1-cpu is the release candidate.
FROM jqmcginnis/lst-ai:v2.0.0rc1-cpu

WORKDIR /processor

COPY processor/ /processor/processor/

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
