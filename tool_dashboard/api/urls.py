from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from . import views

urlpatterns = [
    path('tools/', views.tool_list, name='api_tool_list'),
    path('tools/<int:tool_id>/', views.tool_detail, name='api_tool_detail'),
    path('build-callback/', views.build_callback, name='api_build_callback'),
    path('tools/<int:tool_id>/deploy/', views.deploy_tool_api, name='api_deploy_tool'),
    path('tools/<int:tool_id>/stop/', views.stop_tool_api, name='api_stop_tool'),
    
    # Thêm URL cho Swagger UI
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]