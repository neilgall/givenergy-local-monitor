FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir \
    givenergy-modbus==0.10.1 \
    "fastapi>=0.111.0" \
    "uvicorn[standard]>=0.29.0"

COPY givenergy_control.py ./

ENV INVERTER_PORT=8899
ENV API_PORT=8000
ENV LOG_LEVEL=INFO

EXPOSE 8000

CMD ["python", "givenergy_control.py"]
