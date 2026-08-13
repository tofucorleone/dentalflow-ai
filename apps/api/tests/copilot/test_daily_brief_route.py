from fastapi.routing import APIRoute

from app.auth import current_user
from app.copilot.router import router
from app.deps import authenticated_clinic_id


def test_daily_brief_route_is_protected():
    route = next(
        item
        for item in router.routes
        if isinstance(item, APIRoute)
        and item.path == "/copilot/daily-brief"
        and "GET" in item.methods
    )

    dependency_calls = {
        dependency.call
        for dependency in route.dependant.dependencies
    }

    assert current_user in dependency_calls
    assert authenticated_clinic_id in dependency_calls
