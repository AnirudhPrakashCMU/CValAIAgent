#!/bin/bash
poetry run uvicorn sentiment_miner.main:app --host 0.0.0.0 --port 8004
