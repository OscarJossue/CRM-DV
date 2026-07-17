from django.urls import path

from . import views


app_name = "contractor_portal"

urlpatterns = [
    path("", views.portal_home, name="home"),
    path("language/", views.portal_language, name="language"),
    path("inspections/", views.inspection_list, name="inspection_list"),
    path(
        "inspections/<int:id_assignment>/",
        views.inspection_detail,
        name="inspection_detail",
    ),
    path(
        "inspections/<int:id_assignment>/submit/",
        views.inspection_submit,
        name="inspection_submit",
    ),
    path(
        "inspections/<int:id_assignment>/photos/<int:id_image>/delete/",
        views.inspection_photo_delete,
        name="inspection_photo_delete",
    ),
    path("projects/", views.project_list, name="project_list"),
    path(
        "projects/<int:id_project>/",
        views.project_detail,
        name="project_detail",
    ),
    path(
        "projects/<int:id_project>/submit/",
        views.project_submit,
        name="project_submit",
    ),
    path(
        "projects/<int:id_project>/photos/<str:photo_kind>/<int:id_photo>/delete/",
        views.project_photo_delete,
        name="project_photo_delete",
    ),
]
