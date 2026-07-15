# dockingVina
conda create -n dockingVina python=3.10.14
<!-- # 去掉 build-level 的 pin，只保留包名和主版本
conda env export --no-builds > environment-portable.yml
# 安装conda env
conda env create -f environment-portable.yml -->
conda activate dockingVina
# 安装
conda install -c conda-forge openmpi mpi4py

git clone https://github.com/durrantlab/gypsum_dl.git
# or
git clone git@github.com:durrantlab/gypsum_dl.git
git clone https://github.com/SongyouZhong/gypsum_dl.git

<!-- # 需要修改gypsum_dl/Start.py的源码
# replace 'os.mkdir(params["output_folder"])' with os.makedirs(params["output_folder"], exist_ok=True) -->

# 下载 and 安装ADFR
wget --content-disposition "https://ccsb.scripps.edu/adfr/download/1028/"
chmod a+x ADFRsuite_Linux-x86_64_1.0_install
./ADFRsuite_Linux-x86_64_1.0_install

# 添加用户执行权限
chmod u+x vinademo.sh

conda install -c conda-forge uvicorn fastapi
conda install -c conda-forge apsw
pip install mmpdb
<!-- conda install seaborn -->

# 在项目根目录下运行：
pip install -e ./my_toolsets

pip uninstall mmpdb -y
pip install mmpdb==2.1
pip uninstall torch
<!-- conda install pytorch pytorch-cuda=11.8 -c pytorch -c nvidia
 -->
 conda install pytorch torchvision torchaudio -c pytorch

pip install --upgrade pydantic
pip install "meeko>=0.3.0"
python -m pip install mmpdb
pip install seaborn
sudo apt-get install -y openmpi-bin
conda install -c conda-forge mpi4py
conda install numpy=1.23

uvicorn main:app
# 开放给其它后台服务时，可以设置环境变量 SERVICE_API_KEYS
# 以逗号分隔多组 key，并让服务在请求时携带 `X-API-Key` 头部
export SERVICE_API_KEYS="service-key-1,service-key-2"
# 后台任务
# ⚠️ 过时（2026-07-14，ADR 0012）：没有 `task_worker.py`，`main_loop` 是死代码。
#   自 ADR 0012 P3 起，`generate` 也不再在 API 进程内跑 —— 后端只 INSERT 一行 pending，
#   由 compute-foundry operator 提交为 Argo Workflow。本后端不运行任何计算。

pip install python-jose[cryptography]
sudo brew install mysql-server
pip install mysql-connector-python bcrypt


micromamba activate AstraMolecula && micromamba install rdkit=2024.03.5 -c conda-forge