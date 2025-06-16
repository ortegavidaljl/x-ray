FROM debian:bookworm-slim

WORKDIR /app

COPY . .

RUN chmod +x setup.sh entrypoint.sh x-ray.py cli.py

ENTRYPOINT ["/app/entrypoint.sh"]