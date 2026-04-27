FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir \
    givenergy-modbus==0.10.1 \
    "pydantic>=1.9,<2" \
    "fastapi>=0.95.0,<0.100" \
    "uvicorn[standard]>=0.21.0"

COPY givenergy_control.py ./

ENV INVERTER_PORT=8899
ENV API_PORT=8000
ENV LOG_LEVEL=INFO

EXPOSE 8000

CMD ["python", "givenergy_control.py"]
