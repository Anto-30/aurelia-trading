"""Research-only causal Gaussian-HMM and alpha/beta-HMM filtering primitives."""
from __future__ import annotations
from dataclasses import dataclass
from math import exp, isfinite, log, pi, sqrt
from typing import Any, Sequence

RESEARCH_ONLY = True
CAPITAL_AUTHORITY = False
LIVE_EXECUTION = False
RANGE, TREND_UP, TREND_DOWN, HIGH_VOL, UNDEFINED = "RANGE", "TREND_UP", "TREND_DOWN", "HIGH_VOL", "UNDEFINED"
REGIME_RANGE, REGIME_TREND_UP, REGIME_TREND_DOWN, REGIME_HIGH_VOL, REGIME_UNDEFINED = RANGE, TREND_UP, TREND_DOWN, HIGH_VOL, UNDEFINED
_ALLOWED = {RANGE, TREND_UP, TREND_DOWN, HIGH_VOL}


def _vec(values: Sequence[float], name: str) -> tuple[float, ...]:
    try:
        out = tuple(float(v) for v in values)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not out or not all(isfinite(v) for v in out):
        raise ValueError(f"{name} must be non-empty and finite")
    return out


def _dist(values: Sequence[float], name: str) -> tuple[float, ...]:
    out = _vec(values, name)
    if any(v < 0 for v in out) or abs(sum(out) - 1.0) > 1e-6:
        raise ValueError(f"{name} must be non-negative and sum to 1")
    total = sum(out)
    return tuple(v / total for v in out)


def _mat(values: Sequence[Sequence[float]], name: str) -> tuple[tuple[float, ...], ...]:
    rows = tuple(_vec(row, name) for row in values)
    if not rows or any(len(row) != len(rows[0]) for row in rows):
        raise ValueError(f"{name} must be a rectangular matrix")
    return rows


def _posterior(prior: Sequence[float], log_likelihoods: Sequence[float]) -> tuple[float, ...]:
    p = _dist(prior, "prior")
    ll = tuple(float(v) for v in log_likelihoods)
    if len(p) != len(ll) or any((not isfinite(v)) and v != float("-inf") for v in ll):
        raise ValueError("invalid emission log-likelihood vector")
    weights_log = [log(a) + b if a > 0 and b != float("-inf") else float("-inf") for a, b in zip(p, ll)]
    top = max(weights_log)
    if top == float("-inf"):
        raise ValueError("all posterior state weights are zero")
    weights = [exp(v - top) if v != float("-inf") else 0.0 for v in weights_log]
    return tuple(v / sum(weights) for v in weights)


def causal_belief_update(previous: Sequence[float], transition: Sequence[Sequence[float]],
                         log_likelihoods: Sequence[float]) -> tuple[float, ...]:
    """One forward-only belief update; transition[i][j] means P(S_t=j|S_(t-1)=i)."""
    p = _dist(previous, "previous belief")
    t = _mat(transition, "transition matrix")
    n = len(p)
    if len(t) != n or any(len(row) != n for row in t) or len(log_likelihoods) != n:
        raise ValueError("state dimensions do not match")
    t = tuple(_dist(row, f"transition row {i}") for i, row in enumerate(t))
    prior = tuple(sum(p[i] * t[i][j] for i in range(n)) for j in range(n))
    return _posterior(_dist(prior, "predictive prior"), log_likelihoods)


def alpha_beta_belief_update(previous: Sequence[float], log_likelihoods: Sequence[float], *,
                            alpha: float, beta: float) -> tuple[float, ...]:
    """Paper-style equal-exit prediction plus tempered likelihood update.

    predicted[m] = ((1 - M*alpha) * previous[m] + alpha),
    followed by posterior proportional to predicted[m] * L(x|m)**beta.
    """
    p = _dist(previous, "previous belief")
    n = len(p)
    ll = tuple(float(v) for v in log_likelihoods)
    if len(ll) != n or any((not isfinite(v)) and v != float("-inf") for v in ll):
        raise ValueError("invalid emission log-likelihood vector")
    if not isfinite(alpha) or not 0 <= alpha <= 1.0 / (n - 1):
        raise ValueError("alpha must be in [0, 1/(n_states-1)]")
    if not isfinite(beta) or beta <= 0:
        raise ValueError("beta must be finite and > 0")
    predicted = [alpha + (1.0 - n * alpha) * value for value in p]
    if any(value < -1e-12 for value in predicted):
        raise ValueError("alpha produced an invalid predictive belief")
    prior = _dist([max(0.0, value) for value in predicted], "alpha-beta predictive prior")
    return _posterior(prior, tuple(beta * value for value in ll))


def gaussian_log_likelihood(x: Sequence[float], mean: Sequence[float], cov: Sequence[Sequence[float]]) -> float:
    """Multivariate Gaussian log-density, with positive-definite covariance validation."""
    x, mu, c = _vec(x, "observation"), _vec(mean, "mean"), _mat(cov, "covariance")
    n = len(x)
    if len(mu) != n or len(c) != n or any(len(row) != n for row in c):
        raise ValueError("Gaussian dimensions do not match")
    if any(abs(c[i][j] - c[j][i]) > 1e-8 for i in range(n) for j in range(n)):
        raise ValueError("covariance must be symmetric")
    l = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            v = c[i][j] - sum(l[i][k] * l[j][k] for k in range(j))
            if i == j:
                if not isfinite(v) or v <= 1e-12:
                    raise ValueError("covariance must be positive definite")
                l[i][j] = sqrt(v)
            else:
                l[i][j] = v / l[j][j]
    solved = []
    delta = [x[i] - mu[i] for i in range(n)]
    for i in range(n):
        solved.append((delta[i] - sum(l[i][j] * solved[j] for j in range(i))) / l[i][i])
    logdet = 2 * sum(log(l[i][i]) for i in range(n))
    return -0.5 * (n * log(2 * pi) + logdet + sum(v * v for v in solved))


def _plain(value: Any) -> Any:
    if hasattr(value, "tolist"):
        return _plain(value.tolist())
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("model parameter must be numeric") from exc


def _params(model: Any):
    if getattr(model, "covariance_type", "full") != "full":
        raise ValueError("only full-covariance GaussianHMM is supported")
    start, transition, means, covars = map(_plain, (model.startprob_, model.transmat_, model.means_, model.covars_))
    n = len(start)
    if n < 2 or len(transition) != n or len(means) != n or len(covars) != n:
        raise ValueError("invalid model state dimensions")
    start = _dist(start, "model initial probabilities")
    transition = tuple(_dist(row, f"transition row {i}") for i, row in enumerate(_mat(transition, "transition matrix")))
    width = len(means[0])
    if width < 1 or any(len(row) != width for row in means) or any(len(c) != width or any(len(row) != width for row in c) for c in covars):
        raise ValueError("invalid model feature dimensions")
    if not all(isfinite(v) for row in means for v in row):
        raise ValueError("model means must be finite")
    return start, tuple(tuple(row) for row in means), tuple(tuple(tuple(row) for row in c) for c in covars), transition


def map_model_states(model: Any, *, high_vol_z: float = 1.0, trend_z: float = 1.0) -> tuple[str, ...]:
    """Parameter-based label heuristic; recalculate on every fit due to label switching."""
    _, means, covars, _ = _params(model)
    if len(means[0]) != 2 or high_vol_z < 0 or trend_z < 0:
        raise ValueError("expects two features and non-negative mapping thresholds")
    labels = [RANGE] * len(means)
    hi = max(range(len(means)), key=lambda i: means[i][1])
    if means[hi][1] >= high_vol_z:
        labels[hi] = HIGH_VOL
    candidates = [i for i, label in enumerate(labels) if label != HIGH_VOL]
    if candidates:
        def drift(i):
            variance = covars[i][0][0]
            return abs(means[i][0]) / sqrt(variance) if isfinite(variance) and variance > 1e-12 else 0.0
        best = max(candidates, key=drift)
        if drift(best) >= trend_z:
            labels[best] = TREND_UP if means[best][0] >= 0 else TREND_DOWN
    return tuple(labels)


@dataclass(frozen=True)
class RegimeSignal:
    state_index: int
    regime: str
    posterior: tuple[float, ...]
    confidence: float
    normalized_entropy: float
    usable: bool
    reason: str


def _signal(posterior, labels, min_confidence, max_entropy):
    p, labels = _dist(posterior, "posterior"), tuple(str(v) for v in labels)
    if len(p) != len(labels) or not labels or not 0 < min_confidence <= 1 or not 0 <= max_entropy <= 1:
        raise ValueError("invalid labels or uncertainty thresholds")
    state = max(range(len(p)), key=lambda i: p[i])
    entropy = -sum(v * log(v) for v in p if v > 0)
    entropy = entropy / log(len(p)) if len(p) > 1 else 0.0
    regime, reason, usable = labels[state], "OK", True
    if p[state] < min_confidence:
        regime, reason, usable = UNDEFINED, "LOW_CONFIDENCE", False
    elif entropy > max_entropy:
        regime, reason, usable = UNDEFINED, "HIGH_ENTROPY", False
    elif regime not in _ALLOWED:
        regime, reason, usable = UNDEFINED, "UNRECOGNIZED_STATE_LABEL", False
    return RegimeSignal(state, regime, p, p[state], entropy, usable, reason)


class CausalHMMFilter:
    """Persistent forward filter. Call update once per completed bar, in time order."""
    def __init__(self, model: Any, labels: Sequence[str] | None = None, *, scaler=None,
                 min_confidence: float = 0.60, max_entropy: float = 0.85):
        start, means, covars, transition = _params(model)
        self._start, self._means, self._covars, self._transition = start, means, covars, transition
        self._labels = tuple(labels) if labels is not None else map_model_states(model)
        if len(self._labels) != len(start):
            raise ValueError("label count does not match model state count")
        _signal(start, self._labels, min_confidence, max_entropy)
        self._scaler, self._min_confidence, self._max_entropy = scaler, min_confidence, max_entropy
        self._posterior = None
        self._feature_count = len(means[0])

    @property
    def last_posterior(self):
        return self._posterior

    def reset(self):
        """Start a genuinely new sequence; do not reset for each candle."""
        self._posterior = None

    def update(self, observation: Sequence[float]) -> RegimeSignal:
        x = _vec(observation, "observation")
        if len(x) != self._feature_count:
            raise ValueError("observation dimensions do not match model")
        if self._scaler is not None:
            x = self._scaler.transform_one(x)
        ll = tuple(gaussian_log_likelihood(x, self._means[i], self._covars[i]) for i in range(len(self._means)))
        self._posterior = _posterior(self._start, ll) if self._posterior is None else causal_belief_update(self._posterior, self._transition, ll)
        return _signal(self._posterior, self._labels, self._min_confidence, self._max_entropy)


class AlphaBetaHMMFilter:
    """Causal alpha-beta filter using GaussianHMM-fitted emission likelihoods.

    Emissions are estimated by GaussianHMM EM, while this filter uses alpha/beta
    equal-exit recursion and ignores the fitted transition matrix. It is therefore
    a hybrid research adapter, not a full replication of the paper's experiments.
    """
    def __init__(self, model: Any, *, alpha: float, beta: float = 1.0,
                 labels: Sequence[str] | None = None, scaler=None,
                 min_confidence: float = 0.60, max_entropy: float = 0.85):
        start, means, covars, _ = _params(model)
        if not isfinite(alpha) or not 0 <= alpha <= 1.0 / (len(start) - 1):
            raise ValueError("alpha must be in [0, 1/(n_states-1)]")
        if not isfinite(beta) or beta <= 0:
            raise ValueError("beta must be finite and > 0")
        self._start, self._means, self._covars = start, means, covars
        self._labels = tuple(labels) if labels is not None else map_model_states(model)
        if len(self._labels) != len(start):
            raise ValueError("label count does not match model state count")
        _signal(start, self._labels, min_confidence, max_entropy)
        self._alpha, self._beta = alpha, beta
        self._scaler, self._min_confidence, self._max_entropy = scaler, min_confidence, max_entropy
        self._posterior = None
        self._feature_count = len(means[0])

    @property
    def last_posterior(self):
        return self._posterior

    def reset(self):
        """Start a new sequence; call once at sequence boundaries only."""
        self._posterior = None

    def update(self, observation: Sequence[float]) -> RegimeSignal:
        x = _vec(observation, "observation")
        if len(x) != self._feature_count:
            raise ValueError("observation dimensions do not match model")
        if self._scaler is not None:
            x = self._scaler.transform_one(x)
        ll = tuple(gaussian_log_likelihood(x, self._means[i], self._covars[i]) for i in range(len(self._means)))
        prior = self._start if self._posterior is None else self._posterior
        self._posterior = alpha_beta_belief_update(prior, ll, alpha=self._alpha, beta=self._beta)
        return _signal(self._posterior, self._labels, self._min_confidence, self._max_entropy)


@dataclass(frozen=True)
class FeatureScaler:
    mean: tuple[float, ...]
    scale: tuple[float, ...]

    @classmethod
    def fit(cls, rows: Sequence[Sequence[float]]) -> "FeatureScaler":
        rows = tuple(_vec(row, "feature row") for row in rows)
        if len(rows) < 2 or any(len(row) != len(rows[0]) for row in rows):
            raise ValueError("at least two consistent training rows are required")
        mean = tuple(sum(row[j] for row in rows) / len(rows) for j in range(len(rows[0])))
        scale = []
        for j, m in enumerate(mean):
            variance = sum((row[j] - m) ** 2 for row in rows) / len(rows)
            scale.append(sqrt(variance) if variance > 1e-12 else 1.0)
        return cls(mean, tuple(scale))

    def transform_one(self, row: Sequence[float]) -> tuple[float, ...]:
        row = _vec(row, "feature row")
        if len(row) != len(self.mean) or len(self.scale) != len(self.mean) or any(v <= 0 or not isfinite(v) for v in self.scale):
            raise ValueError("invalid scaler dimensions or scale")
        return tuple((row[i] - self.mean[i]) / self.scale[i] for i in range(len(row)))

    def transform(self, rows: Sequence[Sequence[float]]) -> tuple[tuple[float, ...], ...]:
        return tuple(self.transform_one(row) for row in rows)


@dataclass(frozen=True)
class FittedRegimeModel:
    model: Any
    scaler: FeatureScaler
    state_labels: tuple[str, ...]
    training_observations: int
    log_likelihood: float
    training_converged: bool

    def new_filter(self, *, min_confidence=0.60, max_entropy=0.85) -> CausalHMMFilter:
        return CausalHMMFilter(self.model, self.state_labels, scaler=self.scaler,
                               min_confidence=min_confidence, max_entropy=max_entropy)

    def new_alpha_beta_filter(self, *, alpha: float, beta: float = 1.0,
                              min_confidence=0.60, max_entropy=0.85) -> AlphaBetaHMMFilter:
        return AlphaBetaHMMFilter(self.model, alpha=alpha, beta=beta, labels=self.state_labels,
                                  scaler=self.scaler, min_confidence=min_confidence,
                                  max_entropy=max_entropy)


def train_gaussian_hmm(training_features: Sequence[Sequence[float]], *, n_states=3, n_iter=200, random_state=42) -> FittedRegimeModel:
    """Fit scaler and GaussianHMM to a training window only; fitting dependencies are optional."""
    rows = tuple(_vec(row, "training feature") for row in training_features)
    if n_states < 2 or n_states > 5 or n_iter < 10 or len(rows) < max(100, n_states * 20):
        raise ValueError("invalid state/iteration count or insufficient training data")
    if any(len(row) != 2 for row in rows):
        raise ValueError("features must be [log_return, rolling_volatility]")
    try:
        import numpy as np
        from hmmlearn.hmm import GaussianHMM
    except ImportError as exc:
        raise RuntimeError("Install fitting dependencies: pip install -e '.[research-hmm]'") from exc
    scaler = FeatureScaler.fit(rows)
    data = np.asarray(scaler.transform(rows), dtype=float)
    model = GaussianHMM(n_components=n_states, covariance_type="full", n_iter=n_iter,
                        tol=1e-3, min_covar=1e-3, random_state=random_state)
    model.fit(data)
    _params(model)
    score = float(model.score(data))
    if not isfinite(score):
        raise ValueError("model log likelihood is non-finite")
    history = list(getattr(model.monitor_, "history", ()))
    converged = len(history) >= 2 and abs(history[-1] - history[-2]) < 1e-3
    return FittedRegimeModel(model, scaler, map_model_states(model), len(rows), score, converged)


def features_from_closes(closes: Sequence[float], *, window=14) -> tuple[tuple[float, float], ...]:
    """Causal [log return, rolling sample volatility] for completed candles."""
    prices = _vec(closes, "closes")
    if any(v <= 0 for v in prices) or window < 2 or len(prices) < window + 1:
        raise ValueError("positive closes, window >= 2, and at least window+1 closes required")
    returns = tuple(log(prices[i] / prices[i - 1]) for i in range(1, len(prices)))
    out = []
    for i in range(window - 1, len(returns)):
        sample = returns[i - window + 1:i + 1]
        avg = sum(sample) / len(sample)
        var = sum((x - avg) ** 2 for x in sample) / (len(sample) - 1)
        out.append((returns[i], sqrt(max(var, 0.0))))
    return tuple(out)


@dataclass(frozen=True)
class WalkForwardFold:
    train_start: int
    train_end: int
    test_start: int
    test_end: int


def walk_forward_folds(n: int, *, train_size=500, test_size=50, step_size=None) -> tuple[WalkForwardFold, ...]:
    """Non-overlapping held-out folds with fixed-length, strictly earlier training windows."""
    step = test_size if step_size is None else step_size
    if n < 0 or train_size < 2 or test_size < 1 or step < test_size:
        raise ValueError("invalid fold sizes; step_size must be >= test_size")
    out, test_start = [], train_size
    while test_start < n:
        test_end = min(test_start + test_size, n)
        out.append(WalkForwardFold(test_start - train_size, test_start, test_start, test_end))
        test_start += step
    return tuple(out)
