FROM python:3.11-sli

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY server/ .

CMD ["python", "main.py"]
