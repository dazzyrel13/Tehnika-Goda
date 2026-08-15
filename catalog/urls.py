from django.urls import path

from .views import (
    HomeView,
    VehicleDetailView,
    VehicleDossierView,
    VehicleListView,
    search_ajax,
    vehicle_report_pdf,
)

app_name = "catalog"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("cars/", VehicleListView.as_view(), name="index"),
    path(
        "category/<slug:category_slug>/",
        VehicleListView.as_view(),
        name="category",
    ),
    path(
        "brand/<slug:brand_slug>/",
        VehicleListView.as_view(),
        name="brand",
    ),
    path("search-ajax/", search_ajax, name="search_ajax"),

    path("vehicle/<slug:slug>/", VehicleDetailView.as_view(), name="vehicle_detail"),
    path(
        "vehicle/<slug:slug>/dossier/",
        VehicleDossierView.as_view(),
        name="vehicle_dossier",
    ),
    path(
        "vehicle/<slug:slug>/report.pdf",
        vehicle_report_pdf,
        name="vehicle_report_pdf",
    ),
]
