# 1. BASE IMAGE: Use a slim Python 3.11 image to minimize RAM usage
FROM python:3.11-slim

# 2. LOGGING: Prevent Python from buffering stdout/stderr
# This ensures real-time feedback in your Google Cloud Operations Suite logs
ENV PYTHONUNBUFFERED=1

# 3. SYSTEM DEPS: Install curl/tar for GoTTY and clean up to keep image small
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tar \
    && rm -rf /var/lib/apt/lists/*

# 4. WORKSPACE: Establish the /app directory (Docker creates this automatically)
WORKDIR /app

# 5. PYTHON DEPS: Install verified libraries from requirements.txt
# This ignores requirements-dev.txt to save space
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. GOTTY WRAPPER: Install the web-terminal binary (v1.6.0)
# Note: This is the linux_amd64 version for your target GCP VM
ENV GOTTY_VERSION=v1.6.0
RUN curl -L https://github.com/sorenisanerd/gotty/releases/download/${GOTTY_VERSION}/gotty_${GOTTY_VERSION}_linux_amd64.tar.gz \
    | tar -xzC /usr/local/bin/

# 7. MVC CODE & DATA: Copy only the specific game logic and dataset
# This mirrors your src/HPtrivia_game structure for clean imports
COPY src/HPtrivia_game/ ./src/HPtrivia_game/
# RUN chmod -R 755 /app/src/HPtrivia_game

# 8. ENVIRONMENT: Point Python to the 'src' directory so it finds your modules
ENV PYTHONPATH="/app:/app/src"

# 9. NETWORKING: Expose the port used by GoTTY
EXPOSE 8080

# 10. ENTRYPOINT: Launch GoTTY to serve the trivia game over a web terminal
CMD ["gotty", "-w", "--address", "0.0.0.0", "--port", "8080", \
     "python", "src/HPtrivia_game/main.py"]