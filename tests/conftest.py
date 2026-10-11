import json
from datetime import datetime
from pathlib import Path

import pytest
from hypothesis import settings

from pc_sourcing.models import Offer

settings.register_profile("pilot", max_examples=100, derandomize=True, database=None)
settings.load_profile("pilot")
ROOT = Path(__file__).resolve().parents[1]
GOLDEN = json.loads((ROOT / "fixtures/golden.json").read_text())
AS_OF = datetime.fromisoformat(GOLDEN["as_of"].replace("Z", "+00:00"))


@pytest.fixture
def corpus():
    return GOLDEN


@pytest.fixture
def as_of():
    return AS_OF


@pytest.fixture
def sample(corpus):
    return Offer.model_validate(corpus["cases"][2]["offer"])
