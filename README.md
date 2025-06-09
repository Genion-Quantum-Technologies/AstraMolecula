# dockingVina
# 去掉 build-level 的 pin，只保留包名和主版本
conda env export --no-builds > environment-portable.yml
# 安装conda env
conda env create -f environment-portable.yml
conda activate dockingVina
# 安装
conda install -c conda-forge openmpi mpi4py

git clone https://github.com/durrantlab/gypsum_dl.git
# or
git clone git@github.com:durrantlab/gypsum_dl.git

# 需要修改gypsum_dl/Start.py的源码
# replace 'os.mkdir(params["output_folder"])' with os.makedirs(params["output_folder"], exist_ok=True)

# 下载 and 安装ADFR
wget --content-disposition "https://ccsb.scripps.edu/adfr/download/1028/"
chmod a+x ADFRsuite_Linux-x86_64_1.0_install
./ADFRsuite_Linux-x86_64_1.0_install

# 添加用户执行权限
chmod u+x vinademo.sh

conda install -c conda-forge uvicorn fastapi
conda install -c conda-forge apsw
pip install mmpdb
conda install seaborn

# 在项目根目录下运行：
pip install -e ./my_toolsets

pip uninstall mmpdb -y
pip install mmpdb==2.1
pip uninstall torch
conda install pytorch pytorch-cuda=11.8 -c pytorch -c nvidia
pip install --upgrade pydantic



uvicorn main:app