import random
from runtime.core.invariants import no_duplicate_economic_effects
from runtime.core.models import RuntimeState
from runtime.core.state import RuntimeStateMachine
def randomized_state_machine_trials(seed=20261003,trials=500):
 rng=random.Random(seed); failures=0
 for _ in range(trials):
  sm=RuntimeStateMachine()
  for s in [RuntimeState.SELF_CHECK,RuntimeState.BROKER_CONNECTING,RuntimeState.BROKER_VERIFIED,RuntimeState.MARKET_READY,RuntimeState.DECISION_READY]:sm.transition(s)
  try:sm.transition(rng.choice([RuntimeState.CAPITAL_PROTECTED,RuntimeState.HEALTHY,RuntimeState.AUTHORIZED]))
  except ValueError:failures+=1
 return {"trials":trials,"failures":failures}
def bounded_effect_sequences(seed=20261003,trials=500):
 rng=random.Random(seed);return all(no_duplicate_economic_effects(rng.randint(0,1)) for _ in range(trials))
