from django.urls import path
from . import views

urlpatterns = [
    path('', views.ToolListView.as_view(), name='tool_list'),
    path('tool/create/', views.ToolCreateView.as_view(), name='tool_create'),
    path('tool/<slug:slug>/', views.ToolDetailView.as_view(), name='tool_detail'),
    path('tool/<slug:slug>/update/', views.ToolUpdateView.as_view(), name='tool_update'),
    path('tool/<slug:slug>/delete/', views.ToolDeleteView.as_view(), name='tool_delete'),
    path('tool/<slug:slug>/script/', views.script_editor_view, name='script_editor'),
    path('tool/<slug:slug>/env-vars/', views.manage_env_vars, name='manage_env_vars'),
    path('tool/<slug:slug>/dependencies/', views.manage_dependencies, name='manage_dependencies'),
    path('dependency/<int:pk>/remove/', views.remove_dependency, name='remove_dependency'),
    path('tool/<slug:slug>/build/', views.build_tool, name='build_tool'),
    path('tool/<slug:slug>/deploy/', views.deploy_tool, name='deploy_tool'),
    path('api/update-build-status/', views.update_build_status, name='update_build_status'),
    path('tool/<slug:slug>/stop/', views.stop_tool, name='stop_tool'),
] 