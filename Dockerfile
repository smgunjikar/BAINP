FROM python:3.11-slim

WORKDIR /app

COPY apps/neuroaccess/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

ENV PYTHONUNBUFFERED=1
ENV BAINP_FRONTEND_HOST=0.0.0.0

EXPOSE 3000

CMD ["python", "deploy/render_start.py"]
