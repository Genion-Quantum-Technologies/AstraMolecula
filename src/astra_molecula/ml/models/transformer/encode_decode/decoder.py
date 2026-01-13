import torch.nn as nn

from astra_molecula.ml.models.transformer.encode_decode.clones import clones
from astra_molecula.ml.models.transformer.encode_decode.layer_norm import LayerNorm


class Decoder(nn.Module):
    "Generic N layer decoder with masking."

    def __init__(self, layer, N):
        super(Decoder, self).__init__()
        self.layers = clones(layer, N)
        self.norm = LayerNorm(layer.size)

    def forward(self, x, memory, src_mask, tgt_mask):


        memory = memory    
                    
        for layer in self.layers:
            x = layer(x, memory, src_mask, tgt_mask)

        return self.norm(x)
