from django.urls import path
from django.contrib.auth.decorators import login_required
from . import views

urlpatterns = [
    path('', login_required(views.ToolListView.as_view()), name='tool_list'),
    path('tool/create/', login_required(views.ToolCreateView.as_view()), name='tool_create'),
    path('tool/<slug:slug>/', login_required(views.ToolDetailView.as_view()), name='tool_detail'),
    path('tool/<slug:slug>/update/', login_required(views.ToolUpdateView.as_view()), name='tool_update'),
    path('tool/<slug:slug>/delete/', login_required(views.ToolDeleteView.as_view()), name='tool_delete'),
    path('tool/<slug:slug>/script/', login_required(views.script_editor_view), name='script_editor'),
    path('tool/<slug:slug>/env-vars/', login_required(views.manage_env_vars), name='manage_env_vars'),
    path('tools/<slug:slug>/env-vars/add/', login_required(views.add_env_var), name='add_env_var'),
    path('tools/<slug:slug>/env-vars/<int:env_id>/edit/', login_required(views.edit_env_var), name='edit_env_var'),
    path('tools/<slug:slug>/env-vars/<int:env_id>/delete/', login_required(views.delete_env_var), name='delete_env_var'),
    path('tool/<slug:slug>/dependencies/', login_required(views.manage_dependencies), name='manage_dependencies'),
    path('dependency/<int:pk>/remove/', login_required(views.remove_dependency), name='remove_dependency'),
    path('tool/<slug:slug>/build/', login_required(views.build_tool), name='build_tool'),
    path('tool/<slug:slug>/deploy/', login_required(views.deploy_tool), name='deploy_tool'),
    path('api/update-build-status/', login_required(views.update_build_status), name='update_build_status'),
    path('tool/<slug:slug>/stop/', login_required(views.stop_tool), name='stop_tool'),
    path('tool/<slug:slug>/delete/', login_required(views.delete_tool), name='tool_delete'),
] 