from django.urls import path

from .views import FAQListView

app_name = "content"

urlpatterns = [
    path("faq/", FAQListView.as_view(), name="faq"),
]
