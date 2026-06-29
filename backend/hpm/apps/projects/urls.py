from django.urls import path
from . import views


urlpatterns = [
    path("", views.project_list),
    path("user/<int:user_id>/", views.user_project_list),
    path("<int:project_id>/jira-board/issue/<str:issue_key>/status/", views.project_jira_board_issue_status),
    path("<int:project_id>/jira-board/issue/<str:issue_key>/rank/", views.project_jira_board_issue_rank),
    path("<int:project_id>/jira-board/issue/<str:issue_key>/", views.project_jira_board_issue),
    path("<int:project_id>/jira-board/", views.project_jira_board),
    path("<int:project_id>/", views.project_detail),
]
