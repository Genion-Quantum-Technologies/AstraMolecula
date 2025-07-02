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
conda install -c conda-forge rdkit=2024.3.5
pip install mmpdb
<!-- conda install seaborn -->

# 在项目根目录下运行：
pip install -e ./my_toolsets

pip uninstall torch
<!-- conda install pytorch pytorch-cuda=11.8 -c pytorch -c nvidia
 -->
 conda install pytorch torchvision torchaudio -c pytorch

pip install --upgrade pydantic
pip install "meeko>=0.3.0"
python -m pip install mmpdb==2.1
pip install seaborn
sudo apt-get install -y openmpi-bin
conda install -c conda-forge mpi4py
conda install numpy=1.23

uvicorn main:app
# 开放给其它后台服务时，可以设置环境变量 SERVICE_API_KEYS
# 以逗号分隔多组 key，并让服务在请求时携带 `X-API-Key` 头部
export SERVICE_API_KEYS="service-key-1,service-key-2"
# 后台任务
# 应用启动时会自动在后台线程运行 `task_worker.main_loop` 以处理 pending 任务，
# 也可以单独执行 `python task_worker.py` 以独立进程方式运行。

pip install python-jose[cryptography]
sudo brew install mysql-server
pip install mysql-connector-python bcrypt
