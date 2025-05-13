# dockingVina

# 安装conda env
conda env create -f environment.yaml
conda activate dockingVina
# 安装
conda install -c conda-forge openmpi mpi4py

git clone https://github.com/durrantlab/gypsum_dl.git
# or
git clone git@github.com:durrantlab/gypsum_dl.git
# move gypsum_dl folder under resource

# 需要修改gypsum_dl/Start.py的源码
# replace 'os.mkdir(params["output_folder"])' with os.makedirs(params["output_folder"], exist_ok=True)

# 下载 and 安装ADFR
wget --content-disposition "https://ccsb.scripps.edu/adfr/download/1028/"
chmod a+x ADFRsuite_Linux-x86_64_1.0_install
./ADFRsuite_Linux-x86_64_1.0_install

# 添加用户执行权限
chmod u+x vinademo.sh