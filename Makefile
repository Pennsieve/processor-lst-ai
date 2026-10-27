.PHONY: help test run clean

SERVICE_NAME ?= processor-lst-ai
# The base image is multi-arch (amd64 + arm64); the platform runs amd64. Leave
# DOCKER_DEFAULT_PLATFORM unset to run natively, or set it to linux/amd64 to
# test the exact platform build (slow under emulation on Apple silicon).
# export DOCKER_DEFAULT_PLATFORM=linux/amd64

.DEFAULT: help

help:
	@echo "Make Help for $(SERVICE_NAME)"
	@echo ""
	@echo "make test   - run the processor over data/input/ with the local Python (needs lst-ai installed)"
	@echo "make run    - build the image and run it over data/input/, writing to data/output/"
	@echo "make clean  - remove data/output/"

test: clean
	INPUT_DIR=data/input OUTPUT_DIR=data/output SEGMENT_ONLY=true PROBABILITY_MAP=true THRESHOLD=0.5 THREADS=4 python3 -m processor.main
	@cat data/output/lesion_volumes/lesions.csv

run: clean
	mkdir -p data/output
	docker compose -f docker-compose.yml down --remove-orphans
	docker compose -f docker-compose.yml build
	docker compose -f docker-compose.yml up --exit-code-from processor

clean:
	rm -rf data/output
