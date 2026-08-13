from fastapi.routing import APIRoute

from app.core import router
from app.deps import authenticated_clinic_id


def test_list_appointments_uses_authenticated_clinic():
    route = next(
        item
        for item in router.routes
        if isinstance(item, APIRoute)
        and item.path == "/appointments"
        and "GET" in item.methods
    )

    dependency_calls = {
        dependency.call
        for dependency in route.dependant.dependencies
    }

    assert authenticated_clinic_id in dependency_calls
