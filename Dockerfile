FROM python:3.12.9
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["gunicorn", "app:app", "-b", "0.0.0.0:8080", "-w", "1", "--threads", "4", "--worker-class", "gthread"]

# docker build -t paribus-app .
# docker run --env-file .env paribus-app