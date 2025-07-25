FROM continuumio/anaconda3:latest

WORKDIR /app

COPY env.yml ./
COPY . /app

# 禁用 pip 缓存
ENV PIP_NO_CACHE_DIR=1

# 创建环境并立刻清理所有缓存
RUN conda env create -f env.yml \
    && conda clean --all --yes \
    && rm -rf /root/.cache/pip

# 切换到 dockingVina 环境
SHELL ["conda", "run", "-n", "dockingVina", "/bin/bash", "-c"]

# 安装本地可编辑包
RUN conda install -y pytorch torchvision torchaudio -c pytorch

# 安装本地可编辑包
RUN pip install -e ./my_toolsets

# 启动服务
CMD ["conda", "run", "-n", "dockingVina", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
