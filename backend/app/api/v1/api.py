"""Router principal da API v1."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin,
    auth,
    catalog,
    checkout,
    courses_admin,
    leads,
    student,
    webhooks,
    tracking,
    users,
    ai,
    admin_portals,
    public_portals,
    uploads,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(leads.router, prefix="/leads", tags=["leads"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(courses_admin.router, prefix="/admin", tags=["admin-courses"])
api_router.include_router(catalog.router, prefix="/catalog", tags=["catalog"])
api_router.include_router(checkout.router, prefix="/checkout", tags=["checkout"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(student.router, prefix="/student", tags=["student"])
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])
api_router.include_router(admin_portals.router, prefix="/admin/portals", tags=["admin-portals"])
api_router.include_router(public_portals.router, prefix="/public/portals", tags=["public-portals"])
api_router.include_router(uploads.router, prefix="/uploads", tags=["Uploads"])
api_router.include_router(tracking.router, prefix="", tags=["tracking"])
