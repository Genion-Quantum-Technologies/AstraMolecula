conda env create -f env.yml
conda activate dock1
conda install conda-forge::python-jose
pip install mmpdb==2.1
pip install -e ./my_toolsets