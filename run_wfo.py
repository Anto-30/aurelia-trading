"""Convenience entry point for the research-only Deriv walk-forward lab.

This wrapper delegates to the isolated research module and does not connect to
a broker or authorize capital.
"""
from research.labs.deriv_tick_momentum_absorption import main

if __name__ == "__main__":
    main()
