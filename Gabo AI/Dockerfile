FROM python:3.11-slim
WORKDIR /app
COPY GaboAI.py .
EXPOSE 8080
ENTRYPOINT ["python3", "GaboAI.py", "--serve", "--host", "0.0.0.0", "--port", "8080"]
