from django.urls import path

from .views import submit_inquiry

app_name = "leads"

urlpatterns = [
    path("submit/", submit_inquiry, name="submit"),
]
