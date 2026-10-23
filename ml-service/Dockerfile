# PlaceIQ ML service: trains the model from the database on first start
# (kept in the model volume afterwards) and serves POST /predict to the
# backend only. No port is published for it in docker-compose.yml.
FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ML_HOST=0.0.0.0 \
    ML_PORT=6000 \
    MODEL_PATH=/models/model.joblib
WORKDIR /app

# constraints.txt pins the exact versions the evaluated model was trained
# with, so a model trained here behaves the same.
COPY requirements.txt constraints.txt ./
RUN pip install --no-cache-dir -r requirements.txt -c constraints.txt

COPY app.py train.py ./
RUN useradd --create-home placeiq && mkdir /models && chown placeiq /models
USER placeiq

CMD ["python", "app.py"]
