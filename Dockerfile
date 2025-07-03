FROM python:3.13-slim-bookworm

RUN apt-get update && apt-get install -y \
    mecab \
    mecab-ipadic-utf8 \
    libmecab-dev \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN python3 -m unidic download

COPY . .

RUN echo "PORT=8888" > config.py && \
    echo "DEBUG=False" >> config.py && \
    echo "MECAB_DICDIR='/usr/local/lib/python3.13/site-packages/unidic/dicdir'" >> config.py && \
    echo "MECAB_RC='/etc/mecabrc'" >> config.py

VOLUME ["/app/markov.db"]

EXPOSE 8888

RUN chmod +x docker-entrypoint.py

CMD ["python3", "docker-entrypoint.py"]
