FROM python:3.13-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y git

RUN git clone https://github.com/ortegavidaljl/x-ray.git .

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "x-ray.py"]