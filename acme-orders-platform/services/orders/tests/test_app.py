import pytest

from app import _orders, app


@pytest.fixture
def client():
    _orders.clear()
    app.config["TESTING"] = True
    app.config["READY"] = True
    yield app.test_client()
    app.config["READY"] = True


def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json == {"status": "ok"}


def test_readyz_ready(client):
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json == {"status": "ready"}


def test_readyz_not_ready_returns_503(client):
    app.config["READY"] = False
    response = client.get("/readyz")
    assert response.status_code == 503


def test_healthz_still_ok_when_not_ready(client):
    app.config["READY"] = False
    assert client.get("/healthz").status_code == 200


def test_create_order_returns_201(client):
    response = client.post("/orders", json={"product": "coffee"})
    assert response.status_code == 201
    assert response.json == {"id": 1, "order": {"product": "coffee"}}


@pytest.mark.parametrize(
    "kwargs",
    [
        {"json": {}},
        {"json": {"product": ""}},
        {"json": {"product": 42}},
        {"json": ["coffee"]},
        {"data": "not json", "content_type": "application/json"},
        {"data": "no content type"},
    ],
)
def test_create_order_rejects_bad_input(client, kwargs):
    response = client.post("/orders", **kwargs)
    assert response.status_code == 400
    assert "error" in response.json


def test_list_orders_starts_empty(client):
    assert client.get("/orders").json == {"orders": []}


def test_orders_are_listed_with_incrementing_ids(client):
    client.post("/orders", json={"product": "coffee"})
    client.post("/orders", json={"product": "tea"})
    orders = client.get("/orders").json["orders"]
    assert [o["id"] for o in orders] == [1, 2]


def test_unknown_route_returns_json_404(client):
    response = client.get("/nope")
    assert response.status_code == 404
    assert response.json == {"error": "Not Found"}


def test_metrics_expose_request_counter_and_histogram(client):
    client.get("/healthz")
    body = client.get("/metrics").get_data(as_text=True)
    assert "http_requests_total" in body
    assert 'route="/healthz"' in body
    assert "http_request_duration_seconds_bucket" in body


def test_metrics_label_uses_route_not_raw_path(client):
    client.get("/no-such-page-12345")
    body = client.get("/metrics").get_data(as_text=True)
    assert "no-such-page-12345" not in body
    assert 'route="unmatched"' in body


def test_request_id_is_echoed(client):
    response = client.get("/healthz", headers={"X-Request-ID": "abc-123"})
    assert response.headers["X-Request-ID"] == "abc-123"
