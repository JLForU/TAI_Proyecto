"""PB-U7-01/02: exposición Prometheus bien formada y allowlist estricta.

PB-U7-01: cualquier conjunto de samples del catálogo produce exactamente un
``# HELP`` y un ``# TYPE`` por familia y líneas de muestra con nombre de familia.
PB-U7-02: un sample con labels fuera de la allowlist siempre se rechaza.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from sentinel.core.metrics.collect import render_prometheus
from sentinel.foundation.metrics_contract import (
    ALLOWED_LABELS_DEFAULT,
    FORBIDDEN_LABELS,
    METRIC_FAMILIES,
)

_label_name = st.sampled_from(sorted(ALLOWED_LABELS_DEFAULT - FORBIDDEN_LABELS))
_label_value = st.text(
    alphabet=st.characters(blacklist_categories=("Cc", "Cs", "Zl", "Zp")),
    max_size=20,
)
_family = st.sampled_from(METRIC_FAMILIES)
_value = st.floats(allow_nan=False, allow_infinity=False, width=32)


@settings(max_examples=60, deadline=None)
@given(
    st.lists(
        st.tuples(
            _family,
            st.dictionaries(_label_name, _label_value, max_size=3),
            _value,
        ),
        min_size=1,
        max_size=8,
    )
)
def test_render_has_one_help_and_type_per_family(samples) -> None:  # type: ignore[no-untyped-def]
    text = render_prometheus(samples)
    families = {name for name, _labels, _value in samples}
    for family in families:
        assert text.count(f"# HELP {family} ") == 1
        assert text.count(f"# TYPE {family} ") == 1
    for line in text.splitlines():
        if line.startswith("#"):
            continue
        name = line.split("{", 1)[0].split(" ", 1)[0]
        assert name in families


@settings(max_examples=40, deadline=None)
@given(
    st.dictionaries(
        st.text(min_size=1, max_size=15),
        st.text(max_size=10),
        min_size=1,
        max_size=3,
    )
)
def test_render_rejects_labels_outside_allowlist(labels) -> None:  # type: ignore[no-untyped-def]
    if not set(labels) - ALLOWED_LABELS_DEFAULT:
        pytest.skip("todos los labels generados son válidos")
    with pytest.raises(ValueError):
        render_prometheus([("sentinel_flows_total", labels, 1.0)])
