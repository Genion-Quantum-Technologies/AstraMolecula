FROM ubuntu:22.04

# 安装基础依赖
RUN apt-get update && apt-get install -y wget bzip2 \
    && rm -rf /var/lib/apt/lists/*

# 下载并安装 Miniconda
RUN wget --quiet https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh \
    && bash Miniconda3-latest-Linux-x86_64.sh -b -p /opt/conda \
    && rm Miniconda3-latest-Linux-x86_64.sh

ENV PATH=/opt/conda/bin:$PATH

WORKDIR /app

COPY environment.yml ./
COPY . /app

# 禁用 pip 缓存
ENV PIP_NO_CACHE_DIR=1

# 创建环境并立刻清理所有缓存
RUN conda env create -f environment.yml \
    && conda clean --all --yes \
    && rm -rf /root/.cache/pip

# 切换到 dockingVina 环境
SHELL ["conda", "run", "-n", "dockingVina", "/bin/bash", "-c"]

# 安装本地可编辑包
RUN pip install -e ./my_toolsets

# 启动服务
CMD ["conda", "run", "-n", "dockingVina", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
