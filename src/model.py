import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

class MultiHeadAttention(nn.Module):
    """Multi Head Attention block from Attention is All You Need.

    Given an input of shape (batch_size, d_model), we output a self attention
    tensor of shape (batch_size, d_model).

    Attributes
    ----------
    W_q: list of Linear
        Query matricies Q with shape(d_model, q) for each head.
    W_k: list of Linear
        Keys matricies K with shape(d_model, q) for each head.
    W_v: list of Linear
        Values matricies V with shape(d_model, v) for each head.
    W_o: Linear
        Output matrix W^O with shape(h*v, d_model).
    """
    def __init__(self, d_model, q, v, h):
        """Initialize the Multi Head Block.

        Parameters
        ----------
        d_model: int
            Dimension of the input vector.
        q: int
            Dimension of all query matrix.
        v: int
            Dimension of all value matrix.
        h: int
            Number of heads.
        """
        super().__init__()
        
        self._W_q = [nn.Linear(d_model, q) for _ in range(h)]
        self._W_k = [nn.Linear(d_model, q) for _ in range(h)]
        self._W_v = [nn.Linear(d_model, v) for _ in range(h)]
        
        self._W_o = nn.Linear(h*v, d_model)
        
    def forward(self, xi):
        """Propagate forward the input through the MHB.

        We compute for each head the queries, keys and values matrices,
        followed by the Scaled Dot-Product. The result is concatenated 
        and returned with shape (batch_size, d_model).

        Parameters
        ----------
        xi: Tensor
            Input tensor with shape (batch_size, K, d_model).

        Returns
        -------
        self_attention: Tensor
            Self attention tensor with shape (batch_size, K, d_model).
        """
        attention_heads = []
        for W_q, W_k, W_v in zip(self._W_q, self._W_k, self._W_v):
            queries = W_q(xi)
            keys = W_k(xi)
            values = W_v(xi)

            # Scaled Dot Product
            scores = F.softmax(torch.bmm(queries, keys.transpose(1, 2)) / np.sqrt(queries.shape[1]), dim=-1)
            attention = torch.bmm(scores, values)
            
            attention_heads.append(attention)
        
        # Concatenat the heads
        attention_heads = torch.cat(attention_heads, dim=-1)
        
        # Apply linear transformation W^O
        self_attention = self._W_o(attention_heads)
        
        return self_attention

class PositionwiseFeedForwad(nn.Module):
    """Position-wise Feed Forward Network block from Attention is All You Need.

    Apply two linear transformations to each input, separately but indetically. We
    implement them as 1D convolutions. Input and output have a shape (batch_size, d_model).

    Attributes
    ----------
    linear1: Conv1D
        First linear transformation.
    linear2: Conv1D
        Second linear transformation.
    """
    def __init__(self, d_model, d_ff=2048):
        """Initialize the PFF block.

        Parameters
        ----------
        d_model: int
            Dimension of input tensor.
        d_dd: int, optional
            Dimension of hidden layer, default is 2048.
        """
        super().__init__()
        
        self._linear1 = nn.Conv1d(d_model, d_ff, kernel_size=1)
        self._linear2 = nn.Conv1d(d_ff, d_model, kernel_size=1)
        
    def forward(self, x):
        """Propagate forward the input through the PFF block.

        Apply the first linear transformation, then a relu actvation,
        and the second linear transformation.

        Parameters
        ----------
        x: Tensor
            Input tensor with shape (batch_size, K, d_model).

        Returns
        -------
        x: Tensor
            Output tensor with shape (batch_size, K, d_model).
        """
        # Switch to channel first for torch convolutions compatibility
        x.transpose_(2, 1)
        
        x = self._linear2(F.relu(self._linear1(x)))
        
        # Switch back to orinigal dimensions
        x.transpose_(2, 1)
        return x

class EncoderBlock(nn.Module):
    """Encoder block from Attention is All You Need.

    Apply Multi Head Attention block followed by a Point-wise Feed Forward block.
    Residual sum and normalization are applied at each step.

    Attributes
    ----------
    multiHeadAttention: Module
        Multi Head Attention block.
    positionWiseFeedForward: Module
        Point-wise Feed Forward block.
    layerNorm1: LayerNorm
        First normalization layer from the paper `Layer Normalization`.
    layerNorm2: LayerNorm
        Second normalization layer from the paper `Layer Normalization`.
    """
    def __init__(self, d_model, q, v, h):
        """Initialize the Encoder block

        Parameters
        ----------
        d_model: int
            Dimension of the input vector.
        q: int
            Dimension of all query matrix.
        v: int
            Dimension of all value matrix.
        h: int
            Number of heads.
        """
        super().__init__()
        
        self._multiHeadAttention = MultiHeadAttention(d_model, q, v, h)
        self._positionWiseFeedForward = PositionwiseFeedForwad(d_model)
        
        self._layerNorm1 = nn.LayerNorm(d_model)
        self._layerNorm2 = nn.LayerNorm(d_model)
        
    def forward(self, x):
        """Propagate the input through the Encoder block.

        Apply the Multi Head Attention block, add residual and normalize.
        Apply the Point-wise Feed Forward block, add residual and normalize.

        Parameters
        ----------
        x: Tensor
            Input tensor with shape (batch_size, K, d_model).
        
        Returns
        -------
        x: Tensor
            Output tensor with shape (batch_size, K, d_model).
        """
        residual = x
        x = self._multiHeadAttention(x)
        x.add_(residual)
        x = self._layerNorm1(x)
        
        redisual = x
        x = self._positionWiseFeedForward(x)
        x.add_(residual)
        x = self._layerNorm2(x)
        
        return x