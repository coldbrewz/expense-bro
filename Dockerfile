FROM python:3.11-slim

# Set work directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install requirements
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY bot.py db.py parser.py pdf_parser.py dashboard.py /app/


# Create directory for SQLite database storage
RUN mkdir -p /app/data

# Run the bot
CMD ["python", "bot.py"]
