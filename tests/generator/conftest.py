"""Shared fixtures for generator tests: plans and simulations, cached per session."""

from __future__ import annotations

import functools

import pytest

from wcb.world.planner import make_plan
from wcb.world.simulator import Simulation, simulate

# Seeds used for calibration averages; chosen once, never tuned per test.
CALIBRATION_SEEDS = (0, 1, 2, 3, 4, 5)


@functools.cache
def cached_plan(seed: int, size: str = "standard", weeks: int = 1) -> dict:
    return make_plan(seed, size=size, weeks=weeks)


@functools.cache
def cached_sim(seed: int, size: str = "standard", weeks: int = 1) -> Simulation:
    return simulate(make_plan(seed, size=size, weeks=weeks), seed)


@pytest.fixture(scope="session")
def plan_of():
    return cached_plan


@pytest.fixture(scope="session")
def sim_of():
    return cached_sim
