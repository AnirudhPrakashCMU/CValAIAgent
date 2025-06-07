#!/bin/bash
poetry run uvicorn code_generator.main:app --host 0.0.0.0 --port 8003
