from __future__ import annotations

import sys
from datetime import date
from types import SimpleNamespace


def test_compute_time_series_retries_transient_internal_error(monkeypatch):
    import app.gee as gee

    monkeypatch.setattr(gee, "initialize_ee", lambda: None)
    monkeypatch.setattr(gee, "geojson_to_ee_geometry", lambda geojson: geojson)
    monkeypatch.setattr(gee, "get_settings", lambda: SimpleNamespace(max_timeseries_points=100))

    class _FakeImage:
        def reduceRegion(self, **kwargs):  # type: ignore[no-untyped-def]
            return {"nightlights": 42.0}

    monkeypatch.setattr(gee, "build_metric_image", lambda *args, **kwargs: _FakeImage())

    call_state = {"get_info_calls": 0}
    deadline_calls: list[float] = []

    class _FakeDate:
        def __init__(self, value: str):
            self._value = value

        def advance(self, amount: int, unit: str):  # type: ignore[no-untyped-def]
            return self

        def format(self, fmt: str):  # type: ignore[no-untyped-def]
            if fmt == "YYYY-MM":
                return self._value[:7]
            return self._value

    class _FakeReducer:
        @staticmethod
        def mean():
            return object()

    class _FakeList:
        def __init__(self, items):  # type: ignore[no-untyped-def]
            self._items = list(items)

        def map(self, fn):  # type: ignore[no-untyped-def]
            return [fn(item) for item in self._items]

    class _FakeFeature:
        def __init__(self, _geom, properties):  # type: ignore[no-untyped-def]
            self.properties = properties

    class _FakeFeatureCollection:
        def __init__(self, features):  # type: ignore[no-untyped-def]
            self._features = features

        def getInfo(self):  # type: ignore[no-untyped-def]
            call_state["get_info_calls"] += 1
            if call_state["get_info_calls"] == 1:
                raise RuntimeError(
                    "An internal error has occurred (request: ef2663aa-429d-4eca-b44c-d638fc0f3df6) "
                    '(computation: "62PI6XV5UEAFZNMX6XEVM4MW")'
                )
            return {"features": [{"properties": feature.properties} for feature in self._features]}

    fake_ee = SimpleNamespace(
        Date=lambda value: _FakeDate(value),
        Reducer=_FakeReducer,
        List=lambda items: _FakeList(items),
        Feature=lambda _geom, props: _FakeFeature(_geom, props),
        FeatureCollection=lambda features: _FakeFeatureCollection(features),
        data=SimpleNamespace(setDeadline=lambda ms: deadline_calls.append(ms)),
    )
    monkeypatch.setitem(sys.modules, "ee", fake_ee)

    sleep_calls: list[float] = []
    monkeypatch.setattr(gee.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    result = gee.compute_time_series(
        geometry_geojson={"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
        metric="nightlights",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31),
        granularity="monthly",
    )

    assert result == [("2024-01", 42.0)]
    assert call_state["get_info_calls"] == 2
    assert sleep_calls == [gee._GEE_TRANSIENT_RETRY_BASE_DELAY_SECONDS]
    assert deadline_calls == [gee._GEE_GETINFO_TIMEOUT * 1000]
