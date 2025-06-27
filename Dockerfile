FROM mambaorg/micromamba:latest

WORKDIR /app

COPY environment.yml .
COPY . /app

RUN micromamba env create -f environment.yml --override-channels -c conda-forge -c defaults


SHELL ["micromamba", "run", "-n", "dockingVina", "/bin/bash", "-c"]
RUN pip install -e ./my_toolsets

CMD ["micromamba", "run", "-n", "dockingVina", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]