# dockingVina

# 安装conda env
conda env create -f environment.yaml
conda activate dockingVina
# 安装
conda install -c conda-forge openmpi mpi4py

git clone https://github.com/durrantlab/gypsum_dl.git
# or
git clone git@github.com:durrantlab/gypsum_dl.git


# 下载 and 安装ADFR
wget --content-disposition "https://ccsb.scripps.edu/adfr/download/1028/"
chmod a+x ADFRsuite_Linux-x86_64_1.0_install
./ADFRsuite_Linux-x86_64_1.0_install

