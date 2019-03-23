from torch import nn
import torch.nn.functional as F
import math
from src.module.decoder.decoder import Decoder
from src.module.utils.constants import PAD_INDEX
from src.module.utils.clone import clone
from src.module.layer.conv_glu import ConvGLU
from src.module.layer.conv_relu import ConvReLU
from src.module.layer.feed_forward import FeedForward

class ConvDecoder(Decoder):

    def __init__(self, embedding, positional_embedding, layer, num_layers, dropout):
        super(ConvDecoder, self).__init__()
        self.embedding = embedding
        self.positional_embedding = positional_embedding
        embed_size = embedding.embedding_dim
        hidden_size = layer.hidden_size
        self.input_projection = nn.Linear(embed_size, hidden_size)
        self.layers = clone(layer, num_layers)
        self.output_projection = nn.Linear(hidden_size, embed_size)
        self.dropout = dropout

    def forward(self, src, trg):
        return self.step(src, trg)

    def greedy_decode(self, src, max_len):
        pass

    def beam_decode(self, src, max_len, beam_size):
        pass

    def step(self, src, trg_slice):
        trg_slice_embedding = self.embedding(trg_slice) + self.positional_embedding(trg_slice)
        trg_slice_embedding = F.dropout(trg_slice_embedding, p=self.dropout, training=self.training)
        trg_slice_mask = (trg_slice != PAD_INDEX)
        trg_slice = trg_slice_embedding.transpose(0, 1)
        trg_slice = self.input_projection(trg_slice)
        for layer in self.layers:
            trg_slice = layer(src, (trg_slice, trg_slice_mask))
        trg_slice = self.output_projection(trg_slice)
        trg_slice = trg_slice.transpose(0, 1)
        logits = trg_slice.matmul(self.embedding.weight.t())
        return logits

class ConvDecoderLayer(nn.Module):

    def __init__(self, hidden_size, kernel_size, dropout, activatity='glu'):
        super(ConvDecoderLayer, self).__init__()
        self.layer_norm1 = nn.LayerNorm(hidden_size)
        if activatity == 'glu':
            self.conv = ConvGLU(
                input_size=hidden_size,
                output_size=hidden_size,
                kernel_size=kernel_size,
                encode=True
            )
        else:
            self.conv = ConvReLU(
                input_size=hidden_size,
                output_size=hidden_size,
                kernel_size=kernel_size,
                encode=True
            )
        self.dropout1 = nn.Dropout(dropout)
        self.layer_norm2 = nn.LayerNorm(hidden_size)
        self.feed_forward = FeedForward(
            hidden_size=hidden_size,
            feed_forward_size=2 * hidden_size
        )
        self.dropout2 = nn.Dropout(dropout)

    def forward(self, x):
        x = self.dropout1(self.conv(self.layer_norm1(x)))
        x = self.dropout2(self.feed_forward(self.layer_norm2(x)))
        return x