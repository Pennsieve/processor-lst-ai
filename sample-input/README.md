# Sample input

No NIfTI files are committed. Fetch the CC0 OpenNeuro pair used for local testing
(ds000221, LEMON; sub-010200 has an MP2RAGE UNI T1w and a 3D FLAIR) with:

```sh
./sample-input/fetch-sample.sh      # writes data/input/t1w/ and data/input/flair/
make run
```

`data/` is gitignored. The layout mirrors what a workflow with linked inputs gives
the app (`INPUT_DIR/t1w/`, `INPUT_DIR/flair/`); the app also finds the files at the
root of `INPUT_DIR` by their BIDS suffix (`_T1w`, `_FLAIR`).
