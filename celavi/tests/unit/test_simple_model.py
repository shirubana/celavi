import pytest
import pandas as pd
from random import randint, seed
import numpy as np
from scipy.stats import weibull_min

from celavi.simple_model import Context

np.random.seed(0)
lifespan_fns = {
    "nacelle": lambda: 30,
    "blade": lambda: round(float(weibull_min.rvs(2, loc=0, scale=17, size=1))),
    "foundation": lambda: 50,
    "tower": lambda: 50,
}


@pytest.fixture
def components():
    turbine = [
        {
            "kind": "blade",
            "xlat": 39.9106,
            "ylon": -105.2347,
            "year": 2000,
        },
        {
            "kind": "blade",
            "xlat": 39.9106,
            "ylon": -105.2347,
            "year": 2000,
        },
        {
            "kind": "blade",
            "xlat": 39.9106,
            "ylon": -105.2347,
            "year": 2000,
        },
        {
            "kind": "nacelle",
            "xlat": 39.9106,
            "ylon": -105.2347,
            "year": 2000,
        },
        {
            "kind": "tower",
            "xlat": 39.9106,
            "ylon": -105.2347,
            "year": 2000,
        },
        {
            "kind": "foundation",
            "xlat": 39.9106,
            "ylon": -105.2347,
            "year": 2000,
        },
    ]
    return pd.DataFrame(turbine)


@pytest.fixture
def context():
    return Context()


def test_years_to_timestep(context):
    expected = 160
    actual = context.years_to_timesteps(40)
    assert expected == actual


def test_timesteps_to_years(context):
    expected = 2000
    actual = context.timesteps_to_years(80)
    assert expected == actual


def test_population(context, components):
    seed(0)
    context.populate(components, lifespan_fns)
    expected = 6
    actual = len(context.components)
    assert expected == actual


def test_context_run(context, components):
    seed(0)
    context.populate(components, lifespan_fns)
    context.run()
