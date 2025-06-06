FROM python:3.11-slim
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir poetry && poetry install --no-root
CMD ["poetry", "run", "uvicorn", "code_generator.main:app", "--host", "0.0.0.0", "--port", "8003"]
