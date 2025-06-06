#!/bin/bash
poetry run uvicorn demographic_classifier.main:app --host 0.0.0.0 --port 8005
