"""Import the FastAPI app with the documented dummy environment."""


def test_server_imports_and_exposes_health():
    import server

    paths = {getattr(route, "path", None) for route in server.app.routes}
    assert "/api/health" in paths
    assert server.app.router.lifespan_context is not None
