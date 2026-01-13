"""
PyTorch related util functions
"""
import torch
import os 
def allocate_gpu(id=None):
    '''
    choose the free gpu in the node
    '''
    v = torch.empty(1)
    if id is not None:
        return torch.device("cuda:{}".format(str(id)))
    else:
        for i in range(8):
            try:
                dev_name = "cuda:{}".format(str(i))
                v = v.to(dev_name)
                print("Allocating cuda:{}.".format(i))

                return v.device
            except Exception as e:
                pass
        print("CUDA error: all CUDA-capable devices are busy or unavailable")
        return v.device

def allocate_gpu_multi(id=None):

    os.environ['CUDA_VISIBLE_DEVICES']='1'
    device=torch.device("cuda:1" if torch.cuda.is_available() else 'cpu')
    os.environ['CUDA_VISIBLE_DEVICES']='0'
    device=torch.device("cuda:1" if torch.cuda.is_available() else 'cpu')
    return device
