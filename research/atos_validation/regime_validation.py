"""Research-only regime detection, validation, and position sizing.

No execution permissions are exposed here. Fit all preprocessing inside each
training fold. The last three months should be sealed by the caller before
any model/parameter selection.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Iterable, Sequence
import math
import numpy as np

REGIMES = ("RANGE", "TREND", "HIGH_VOL_CHOP", "UNDEFINED")

@dataclass(frozen=True)
class RegimePrediction:
    regime: str
    probabilities: tuple[float, ...]
    confidence: float
    entropy: float
    valid: bool
    reason: str = ""

class RegimeDetector:
    """Gaussian HMM with causal forward filtering and dynamically mapped states."""
    def __init__(self, n_states: int = 3, min_confidence: float = 0.60,
                 max_entropy: float = 0.85, random_state: int = 17,
                 filter_kind: str = "gaussian", alpha: float = 0.05, beta: float = 1.0):
        if n_states != 3: raise ValueError("this mapper requires exactly 3 states")
        if not 0 < min_confidence <= 1 or not 0 < max_entropy <= 1:
            raise ValueError("invalid confidence/entropy thresholds")
        if filter_kind not in {"gaussian", "alpha_beta"}: raise ValueError("invalid filter_kind")
        if not 0 < alpha <= 1/n_states or not 0 < beta <= 2: raise ValueError("alpha must be in (0,1/n_states], beta in (0,2]")
        self.n_states, self.min_confidence, self.max_entropy = n_states, min_confidence, max_entropy
        self.random_state, self.filter_kind, self.alpha, self.beta = random_state, filter_kind, alpha, beta
        self.model = None; self.mean = None; self.scale = None
        self.state_names = None; self.posterior = None

    @staticmethod
    def features(close: Sequence[float], window: int = 14) -> np.ndarray:
        p = np.asarray(close, dtype=float)
        if p.ndim != 1 or len(p) < window + 2 or not np.isfinite(p).all() or (p <= 0).any():
            raise ValueError("close must be finite, positive, 1-D, and long enough")
        ret = np.diff(np.log(p))
        vol = np.full(ret.shape, np.nan)
        for i in range(window - 1, len(ret)):
            vol[i] = np.std(ret[i-window+1:i+1], ddof=1)
        x = np.column_stack((ret, vol))
        return x[np.isfinite(x).all(axis=1)]

    def fit(self, x: Sequence[Sequence[float]]) -> "RegimeDetector":
        try:
            from hmmlearn.hmm import GaussianHMM
        except ImportError as e:
            raise RuntimeError("Install research requirements: hmmlearn, numpy") from e
        a = np.asarray(x, dtype=float)
        if a.ndim != 2 or a.shape[1] != 2 or len(a) < 100 or not np.isfinite(a).all():
            raise ValueError("training data must be finite Nx2 features with N>=100")
        self.mean = a.mean(axis=0); self.scale = a.std(axis=0, ddof=1)
        self.scale[self.scale < 1e-12] = 1.0
        z = (a-self.mean)/self.scale
        model = GaussianHMM(n_components=3, covariance_type="full", n_iter=300,
                            tol=1e-4, random_state=self.random_state,
                            min_covar=1e-6, implementation="log")
        model.fit(z)
        startprob=np.asarray(model.startprob_,dtype=float)
        transmat=np.asarray(model.transmat_,dtype=float)
        means=np.asarray(model.means_,dtype=float)
        covars=np.asarray(model.covars_,dtype=float)
        if (not np.isfinite(startprob).all() or not np.isfinite(transmat).all()
                or not np.isfinite(means).all() or not np.isfinite(covars).all()):
            raise ValueError("HMM produced non-finite parameters")
        if (startprob.shape!=(self.n_states,) or (startprob<0).any()
                or not np.isclose(startprob.sum(),1.0,atol=1e-6)):
            raise ValueError("HMM start probabilities are not a valid simplex")
        if (transmat.shape!=(self.n_states,self.n_states) or (transmat<0).any()
                or not np.allclose(transmat.sum(axis=1),1.0,atol=1e-6)):
            raise ValueError("HMM transition matrix is not row-stochastic")
        if covars.shape!=(self.n_states,2,2):
            raise ValueError("HMM covariance shape does not match full 2-feature model")
        for covariance in covars:
            symmetric=(covariance+covariance.T)*0.5
            if np.linalg.eigvalsh(symmetric).min()<=0:
                raise ValueError("HMM covariance is not positive definite")
        # State identity is remapped from fitted characteristics every fit.
        stats=[]
        for s in range(3):
            mret=float(model.means_[s,0]*self.scale[0]+self.mean[0])
            vvol=float(model.means_[s,1]*self.scale[1]+self.mean[1])
            stats.append((s,mret,vvol))
        vol_order=sorted(stats,key=lambda v:v[2])
        high=vol_order[-1][0]
        remaining=[v for v in stats if v[0]!=high]
        trend=max(remaining,key=lambda v:abs(v[1]))[0]
        range_state=next(v[0] for v in stats if v[0] not in (high,trend))
        self.state_names={range_state:"RANGE",trend:"TREND",high:"HIGH_VOL_CHOP"}
        self.model=model
        self.posterior=None
        return self

    def _gaussian_log_emissions(self, standardized_row: np.ndarray) -> np.ndarray:
        """Compute one-step log emissions from fitted Gaussian parameters.

        This keeps inference causal and avoids hmmlearn's private likelihood API.
        The fit uses covariance_type="full", so covars_ is state x feature x feature.
        """
        means=np.asarray(self.model.means_,dtype=float)
        covars=np.asarray(self.model.covars_,dtype=float)
        row=np.asarray(standardized_row,dtype=float)
        if (means.shape!=(self.n_states,2) or covars.shape!=(self.n_states,2,2)
                or row.shape!=(2,) or not np.isfinite(means).all()
                or not np.isfinite(covars).all() or not np.isfinite(row).all()):
            raise ValueError("invalid fitted Gaussian emission parameters")
        out=np.empty(self.n_states,dtype=float)
        log_2pi=math.log(2.0*math.pi)
        for state in range(self.n_states):
            covariance=(covars[state]+covars[state].T)*0.5
            sign, logdet=np.linalg.slogdet(covariance)
            if sign<=0 or not math.isfinite(float(logdet)):
                raise ValueError("Gaussian covariance is not positive definite")
            delta=row-means[state]
            solved=np.linalg.solve(covariance,delta)
            value=-0.5*(2.0*log_2pi+float(logdet)+float(delta@solved))
            if not math.isfinite(value):
                raise ValueError("non-finite Gaussian log likelihood")
            out[state]=value
        return out

    def update(self, row: Sequence[float]) -> RegimePrediction:
        if self.model is None: raise RuntimeError("fit model before inference")
        x=np.asarray(row,dtype=float)
        if x.shape!=(2,) or not np.isfinite(x).all():
            return RegimePrediction("UNDEFINED",(),0.0,1.0,False,"invalid feature row")
        z=(x-self.mean)/self.scale
        try:
            log_emit=self._gaussian_log_emissions(z)
        except (ValueError, np.linalg.LinAlgError, FloatingPointError):
            return RegimePrediction("UNDEFINED",(),0.0,1.0,False,"invalid emission likelihood")
        emit=np.exp(log_emit-np.max(log_emit))
        if self.posterior is None:
            prior=self.model.startprob_.copy()
        elif self.filter_kind == "alpha_beta":
            # Equal-exit Alpha-Beta prediction: alpha + (1-M*alpha)*previous belief.
            prior=(self.alpha + (1.0-self.n_states*self.alpha)*self.posterior)
        else:
            prior=self.posterior @ self.model.transmat_
        likelihood=np.power(np.maximum(emit,1e-300), self.beta if self.filter_kind=="alpha_beta" else 1.0)
        post=prior*likelihood
        total=post.sum()
        if not math.isfinite(float(total)) or total<=0:
            return RegimePrediction("UNDEFINED",(),0.0,1.0,False,"invalid posterior")
        post=post/total; self.posterior=post
        entropy=float(-np.sum(post*np.log(np.maximum(post,1e-15)))/math.log(3))
        idx=int(np.argmax(post)); conf=float(post[idx])
        if conf < self.min_confidence or entropy > self.max_entropy:
            return RegimePrediction("UNDEFINED",tuple(map(float,post)),conf,entropy,False,"uncertain posterior")
        return RegimePrediction(self.state_names[idx],tuple(map(float,post)),conf,entropy,True,"OK")

@dataclass(frozen=True)
class ExpectancyReport:
    n: int
    expectancy_r: float
    standard_error_r: float
    ci95_low: float
    ci95_high: float
    profit_factor: float
    max_drawdown_r: float
    fold_variance: float
    degradation_pct: float | None
    overfit_flag: bool
    decision: str

def _metrics(r: np.ndarray) -> tuple[float, float, float, float, float, float]:
    if len(r)==0: return (float("nan"),float("nan"),float("nan"),float("nan"),float("nan"))
    exp=float(np.mean(r)); se=float(np.std(r,ddof=1)/math.sqrt(len(r))) if len(r)>1 else float("nan")
    gains=float(r[r>0].sum()); losses=float(-r[r<0].sum())
    pf=gains/losses if losses>0 else (float("inf") if gains>0 else 0.0)
    equity=np.cumsum(r); peak=np.maximum.accumulate(np.r_[0.0,equity])[1:]
    dd=float(np.min(equity-peak))
    return exp,se,exp-1.96*se,exp+1.96*se,pf,dd

def validate_expectancy(in_sample_r: Sequence[float], oos_r: Sequence[float],
                        fold_returns: Sequence[Sequence[float]], degradation_limit: float=0.20,
                        min_oos_trades: int=100) -> ExpectancyReport:
    """Degradation threshold is a warning gate, not a statistical proof of overfit."""
    ins=np.asarray(in_sample_r,dtype=float); oos=np.asarray(oos_r,dtype=float)
    if not 0 < degradation_limit < 1: raise ValueError("degradation_limit must be between 0 and 1")
    if isinstance(min_oos_trades, bool) or not isinstance(min_oos_trades, (int, np.integer)) or min_oos_trades < 2:
        raise ValueError("min_oos_trades must be an integer >= 2")
    if not np.isfinite(ins).all() or not np.isfinite(oos).all(): raise ValueError("R returns must be finite")
    if len(ins)<2 or len(oos)<2: raise ValueError("need >=2 trades in IS and OOS")
    ie,_,_,_,_,_= _metrics(ins); oe,se,lo,hi,pf,dd=_metrics(oos)
    degradation=((ie-oe)/abs(ie)*100) if ie>0 else None
    fold_means_list: list[float] = []
    flattened_fold_returns: list[float] = []
    for fold in fold_returns:
        values = np.asarray(fold, dtype=float)
        if values.ndim != 1:
            raise ValueError("each WFA fold must be a one-dimensional sequence")
        if values.size == 0:
            continue
        if not np.isfinite(values).all():
            raise ValueError("WFA fold returns must be finite")
        fold_means_list.append(float(np.mean(values)))
        flattened_fold_returns.extend(float(value) for value in values)
    if len(flattened_fold_returns) != len(oos) or not np.allclose(
        np.asarray(flattened_fold_returns, dtype=float), oos, rtol=0.0, atol=1e-12
    ):
        raise ValueError("WFA fold returns must exactly partition OOS returns in chronological order")
    fold_means = np.asarray(fold_means_list, dtype=float)
    fv=float(np.var(fold_means,ddof=1)) if len(fold_means)>1 else float("nan")
    # Fewer than two valid held-out folds is insufficient for a WFA stability gate.
    flag=(len(oos)<min_oos_trades or len(fold_means)<2 or
          (degradation is not None and degradation>degradation_limit*100) or hi<=0)
    decision="REJECT_OR_FALLBACK" if flag else "RESEARCH_PASS_PENDING_OTHER_GATES"
    return ExpectancyReport(len(oos),oe,se,lo,hi,pf,dd,fv,degradation,flag,decision)

def atr_position_size(account_equity: float, risk_fraction: float, atr: float,
                      stop_atr_multiple: float, unit_value_per_price: float,
                      max_units: float, min_units: float=0.0) -> float:
    """Units = equity*risk_fraction / (ATR*stop_multiple*unit_value); no order sent."""
    vals=(account_equity,risk_fraction,atr,stop_atr_multiple,unit_value_per_price,max_units,min_units)
    if not all(math.isfinite(float(v)) for v in vals): raise ValueError("all inputs must be finite")
    if account_equity<=0 or not 0<risk_fraction<=0.02 or atr<=0 or stop_atr_multiple<=0 or unit_value_per_price<=0 or max_units<=0 or min_units<0:
        raise ValueError("unsafe or invalid sizing inputs")
    units=min(account_equity*risk_fraction/(atr*stop_atr_multiple*unit_value_per_price),max_units)
    return units if units>=min_units else 0.0

def chronological_partition(timestamps: Sequence, final_oos_months: int=3):
    """Return index slices; final OOS is time-based and must stay sealed."""
    import pandas as pd
    ts=pd.to_datetime(timestamps,utc=True,errors="raise")
    if len(ts)==0 or not ts.is_monotonic_increasing or ts.has_duplicates:
        raise ValueError("timestamps must be sorted and unique")
    cutoff=ts.max()-pd.DateOffset(months=final_oos_months)
    dev=np.flatnonzero(ts<cutoff); sealed=np.flatnonzero(ts>=cutoff)
    if not len(dev) or not len(sealed): raise ValueError("cannot form development/sealed partitions")
    return dev, sealed, cutoff

def rolling_wfa(n: int, train_fraction: float=.70, min_train: int=500,
                test_size: int=100, step_size: int|None=None):
    """Expanding chronological folds inside development data; never includes sealed OOS."""
    if not 0.5<=train_fraction<1 or n<=min_train or min_train<100 or test_size<1:
        raise ValueError("invalid WFA parameters")
    step=test_size if step_size is None else step_size
    if step<test_size: raise ValueError("step_size must be >= test_size")
    initial=max(min_train,int(n*train_fraction))
    folds=[]
    start=initial
    while start<n:
        end=min(n,start+test_size)
        folds.append((0,start,start,end))
        start+=step
    return folds
