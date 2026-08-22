import pytest

from agent.agent import normalize_application_id


@pytest.mark.parametrize(
    "value",
    [
        "APP001",
        "app001",
        "a p p zero zero one",
        "pp001",
        "0001",
        "PP001APP",
    ],
)
def test_normalize_application_id_accepts_supported_forms(value: str):
    assert normalize_application_id(value) == "APP001"


@pytest.mark.parametrize(
    "value",
    [
        "",
        "hello",
        "APP12",
        "APP1234",
    ],
)
def test_normalize_application_id_rejects_invalid_forms(value: str):
    assert normalize_application_id(value) is None
