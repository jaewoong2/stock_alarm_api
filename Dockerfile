FROM python:3.11.5

WORKDIR /app

COPY ./requirements.txt /app/requirements.txt

# RUN apt-get update && apt-get install -y gcc libpq-dev build-essential && rm -rf /var/lib/apt/lists/*

RUN pip install -r /app/requirements.txt

COPY ./myapi /app/myapi

EXPOSE 8000

CMD ["uvicorn", "myapi.main:app", "--host", "0.0.0.0", "--port", "8000"]
