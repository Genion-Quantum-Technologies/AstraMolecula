FROM continuumio/anaconda3:latest

# Set working directory
WORKDIR /app

# Copy environment definition
COPY environment.yml ./

# Create conda environment from YAML and clean cache
RUN conda env create -f environment.yml

# Ensure the environment is activated for subsequent RUN commands
SHELL ["conda", "run", "-n", "dockingVina", "/bin/bash", "-c"]

# Copy application code
COPY . /app

# Install local editable packages
RUN pip install -e ./my_toolsets

# Default command to run the FastAPI app inside the conda environment
CMD ["conda", "run", "-n", "dockingVina", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
