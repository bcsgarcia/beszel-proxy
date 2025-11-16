FROM python:3.11-slim

WORKDIR /app

# Instala dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código da aplicação
COPY app.py .

# Expõe a porta
EXPOSE 8091

# Comando para rodar a aplicação
CMD ["gunicorn", "--bind", "0.0.0.0:8091", "--workers", "2", "--timeout", "30", "app:app"]
