"""Optional ResNet-LSTM research model. No capital or broker authority."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class ResNLSConfig:
    input_features:int
    lookback:int=32
    filters:int=64
    kernel_size:int=3
    lstm_hidden:int=32
    dropout:float=0.2
    def validate(self)->None:
        if self.input_features<=0 or self.lookback<2 or self.filters<=0 or self.lstm_hidden<=0: raise ValueError("invalid network dimensions")
        if self.kernel_size!=3: raise ValueError("initial implementation pins kernel_size=3")
        if not 0<=self.dropout<1: raise ValueError("dropout must be in [0,1)")

def build_resnls(config:ResNLSConfig):
    config.validate()
    try:
        import torch
        from torch import nn
    except ImportError as exc:
        raise RuntimeError("Install the optional ML dependency before constructing ResNLS") from exc
    class ResidualBlock(nn.Module):
        def __init__(self):
            super().__init__()
            self.net=nn.Sequential(nn.Conv1d(config.input_features,config.filters,3,padding=1),nn.BatchNorm1d(config.filters),nn.ReLU(),
                                   nn.Conv1d(config.filters,config.filters,3,padding=1),nn.BatchNorm1d(config.filters))
            self.skip=nn.Conv1d(config.input_features,config.filters,1); self.act=nn.ReLU()
        def forward(self,x): return self.act(self.net(x)+self.skip(x))
    class AureliaResNLS(nn.Module):
        def __init__(self):
            super().__init__()
            self.residual=ResidualBlock(); self.dropout=nn.Dropout(config.dropout)
            self.lstm=nn.LSTM(config.filters,config.lstm_hidden,batch_first=True)
            self.p_win=nn.Linear(config.lstm_hidden,1); self.expected_return=nn.Linear(config.lstm_hidden,1)
            self.expected_mae=nn.Linear(config.lstm_hidden,1); self.expected_mfe=nn.Linear(config.lstm_hidden,1)
        def forward(self,x):
            z=self.residual(x.transpose(1,2)).transpose(1,2); z=self.dropout(z); h,_=self.lstm(z); h=h[:,-1,:]
            return {"p_win":torch.sigmoid(self.p_win(h)).squeeze(-1),"expected_return":self.expected_return(h).squeeze(-1),
                    "expected_mae":self.expected_mae(h).squeeze(-1),"expected_mfe":self.expected_mfe(h).squeeze(-1)}
    return AureliaResNLS()
