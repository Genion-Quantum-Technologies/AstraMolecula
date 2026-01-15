# ============================================================
# AstraMolecula Docker Image
# 使用 Mamba 进行环境管理
# ============================================================

FROM condaforge/mambaforge:latest AS base

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ============================================================
# 依赖安装阶段 - 利用 Docker 缓存
# ============================================================
FROM base AS dependencies

# 复制环境配置文件
COPY environment.yml ./

# 使用 mamba 创建环境
RUN mamba env create -f environment.yml \
    && mamba clean --all --yes

# ============================================================
# 最终镜像
# ============================================================
FROM dependencies AS final

# 复制项目文件
COPY . /app/

# 激活环境并安装本地包
SHELL ["mamba", "run", "-n", "AstraMolecula", "/bin/bash", "-c"]

# 安装本地 my_toolsets 包
RUN pip install -e ./my_toolsets --no-deps

# 安装主项目包
RUN pip install -e . --no-deps

# 创建必要的目录
RUN mkdir -p /app/logs /tmp/astramolecula

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 启动命令
ENTRYPOINT ["mamba", "run", "--no-capture-output", "-n", "AstraMolecula"]
CMD ["uvicorn", "astra_molecula.app:app", "--host", "0.0.0.0", "--port", "8000"]
