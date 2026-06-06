FROM python:3.12-slim

WORKDIR /app

# Install Nebius CLI
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
    && curl -sSL https://storage.eu-north1.nebius.cloud/nebius-cli/install.sh | bash \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.nebius/bin:${PATH}"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Streamlit config
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

EXPOSE 8501

CMD ["streamlit", "run", "app/Home.py"]
