# Use the official Python image as the base image
FROM python:3.10

# Install necessary dependencies for Chrome and ChromeDriver
RUN apt-get update && apt-get install -y wget gnupg
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
RUN echo "deb http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list
RUN apt-get update && apt-get install -y google-chrome-stable

# Create a new non-root user with a home directory
RUN useradd -m -s /bin/bash spellsbot

# Set the working directory to /app
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install project dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . /app

# Change the ownership of the /app directory to the newly created user
RUN chown -R spellsbot:spellsbot /app
# Set the user for subsequent commands
USER spellsbot

ENV CHROME_HEADLESS=1
ENV PYTHONPATH=/app

# Run the run.py script
CMD ["python", "spells_bot/run.py"]
