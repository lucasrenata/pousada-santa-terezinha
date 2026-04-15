FROM python:3.11-slim

WORKDIR /app

# Dependências do sistema necessárias para PyMuPDF e psycopg2
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    libmupdf-dev \
    mupdf-tools \
    && rm -rf /var/lib/apt/lists/*

# Copia e instala dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código da aplicação
COPY . .

# Cria os diretórios necessários em runtime
RUN mkdir -p /app/reports /app/static /app/logs

EXPOSE 8000

# Inicia com o script de automação de banco
ENTRYPOINT ["/app/entrypoint.sh"]
