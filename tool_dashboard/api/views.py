from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from dashboard.models import Tool, BuildLog
import json
from rest_framework.decorators import api_view, permission_classes, schema
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from dashboard.models import Tool, BuildLog, DeploymentLog
import tempfile
import os
import subprocess
from django.conf import settings

@extend_schema(
    description="Lấy danh sách tất cả các công cụ",
    responses={200: {"type": "object", "properties": {"tools": {"type": "array"}}}}
)
@api_view(['GET'])
@permission_classes([AllowAny])
def tool_list(request):
    tools = Tool.objects.all().values('id', 'name', 'slug', 'is_built', 'is_running', 'build_status')
    return JsonResponse({'tools': list(tools)})

@extend_schema(
    description="Lấy thông tin chi tiết của một công cụ",
    parameters=[
        OpenApiParameter(name="tool_id", type=int, location=OpenApiParameter.PATH, description="ID của công cụ")
    ],
    responses={
        200: {"type": "object"},
        404: {"type": "object", "properties": {"error": {"type": "string"}}}
    }
)
@api_view(['GET'])
@permission_classes([AllowAny])
def tool_detail(request, tool_id):
    try:
        tool = Tool.objects.get(id=tool_id)
        data = {
            'id': tool.id,
            'name': tool.name,
            'slug': tool.slug,
            'description': tool.description,
            'requirements': tool.requirements,
            'is_built': tool.is_built,
            'is_running': tool.is_running,
            'build_status': tool.build_status,
            'docker_image': tool.docker_image,
            'env_vars': list(tool.environment_variables.values('key', 'value', 'is_secret')),
            'dependencies': list(tool.dependencies.values_list('dependent_tool_id', flat=True))
        }
        return JsonResponse(data)
    except Tool.DoesNotExist:
        return JsonResponse({'error': 'Tool not found'}, status=404)

@extend_schema(
    description="Callback API cho quá trình build",
    request={"type": "object", "properties": {
        "tool_id": {"type": "integer"},
        "status": {"type": "string"},
        "log": {"type": "string"},
        "image_name": {"type": "string"}
    }},
    responses={
        200: {"type": "object", "properties": {"status": {"type": "string"}}},
        400: {"type": "object", "properties": {"status": {"type": "string"}, "message": {"type": "string"}}}
    }
)
@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_exempt
def build_callback(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            tool_id = data.get('tool_id')
            status = data.get('status')
            log = data.get('log', '')
            image_name = data.get('image_name', '')
            
            tool = Tool.objects.get(id=tool_id)
            
            # Cập nhật trạng thái build
            tool.build_status = status
            if status == 'success':
                tool.is_built = True
                tool.docker_image = image_name
            tool.save()
            
            # Ghi log
            BuildLog.objects.create(
                tool=tool,
                status=status,
                log=log
            )
            
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'})

@extend_schema(
    description="Deploy một công cụ lên Kubernetes",
    parameters=[
        OpenApiParameter(name="tool_id", type=int, location=OpenApiParameter.PATH, description="ID của công cụ")
    ],
    responses={
        200: {"type": "object", "properties": {"status": {"type": "string"}, "message": {"type": "string"}}},
        400: {"type": "object", "properties": {"status": {"type": "string"}, "message": {"type": "string"}}},
        404: {"type": "object", "properties": {"status": {"type": "string"}, "message": {"type": "string"}}}
    }
)
@api_view(['POST'])
@permission_classes([AllowAny])
def deploy_tool_api(request, tool_id):
    try:
        tool = Tool.objects.get(id=tool_id)
        
        if not tool.is_built:
            return JsonResponse({
                'status': 'error',
                'message': 'Công cụ cần được build trước khi deploy'
            }, status=400)
        
        # Lấy tất cả biến môi trường
        env_vars = tool.environment_variables.all()
        
        # Tạo chuỗi env vars cho file YAML
        env_vars_yaml = ""
        for env in env_vars:
            env_vars_yaml += f"        - name: {env.key}\n"
            env_vars_yaml += f"          value: \"{env.value}\"\n"
        
        # Đọc template YAML
        with open(os.path.join(settings.BASE_DIR, 'kubernetes/deployment_template.yaml'), 'r') as f:
            deployment_template = f.read()
        
        # Thay thế các biến trong template
        deployment_yaml = deployment_template.format(
            tool_slug=tool.slug,
            docker_image=tool.docker_image,
            env_vars=env_vars_yaml
        )
        
        # Tạo file tạm thời để lưu YAML
        with tempfile.NamedTemporaryFile(suffix='.yaml', delete=False) as temp_file:
            temp_file_path = temp_file.name
            temp_file.write(deployment_yaml.encode())
        
        # Ghi log
        deploy_log = DeploymentLog.objects.create(
            tool=tool,
            status='started',
            log=f"Bắt đầu deploy {tool.name} lên Kubernetes thông qua API"
        )
        
        # Thực thi lệnh kubectl apply
        result = subprocess.run(
            ['kubectl', 'apply', '-f', temp_file_path],
            capture_output=True,
            text=True
        )
        
        # Kiểm tra kết quả
        if result.returncode == 0:
            # Cập nhật trạng thái tool
            tool.is_running = True
            tool.save()
            
            # Cập nhật log
            deploy_log.status = 'success'
            deploy_log.log += f"\n\nDeploy thành công:\n{result.stdout}"
            deploy_log.save()
            
            return JsonResponse({
                'status': 'success',
                'message': f"Đã deploy {tool.name} lên Kubernetes thành công",
                'details': result.stdout
            })
        else:
            # Cập nhật log
            deploy_log.status = 'error'
            deploy_log.log += f"\n\nDeploy thất bại:\n{result.stderr}"
            deploy_log.save()
            
            return JsonResponse({
                'status': 'error',
                'message': f"Lỗi khi deploy tool",
                'details': result.stderr
            }, status=400)
        
        # Xóa file tạm
        os.unlink(temp_file_path)
        
    except Tool.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Tool not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

@extend_schema(
    description="Dừng một công cụ đang chạy trên Kubernetes",
    parameters=[
        OpenApiParameter(name="tool_id", type=int, location=OpenApiParameter.PATH, description="ID của công cụ")
    ],
    responses={
        200: {"type": "object", "properties": {"status": {"type": "string"}, "message": {"type": "string"}}},
        400: {"type": "object", "properties": {"status": {"type": "string"}, "message": {"type": "string"}}},
        404: {"type": "object", "properties": {"status": {"type": "string"}, "message": {"type": "string"}}}
    }
)
@api_view(['POST'])
@permission_classes([AllowAny])
def stop_tool_api(request, tool_id):
    try:
        tool = Tool.objects.get(id=tool_id)
        
        if not tool.is_running:
            return JsonResponse({
                'status': 'error',
                'message': 'Công cụ không đang chạy'
            }, status=400)
        
        # Tạo file tạm thời để lưu YAML
        with tempfile.NamedTemporaryFile(suffix='.yaml', delete=False) as temp_file:
            temp_file_path = temp_file.name
            
            # Đọc template YAML
            with open(os.path.join(settings.BASE_DIR, 'kubernetes/deployment_template.yaml'), 'r') as f:
                deployment_template = f.read()
            
            # Thay thế các biến trong template
            deployment_yaml = deployment_template.format(
                tool_slug=tool.slug,
                docker_image=tool.docker_image,
                env_vars=""
            )
            
            temp_file.write(deployment_yaml.encode())
        
        # Ghi log
        deploy_log = DeploymentLog.objects.create(
            tool=tool,
            status='stopping',
            log=f"Bắt đầu dừng {tool.name} trên Kubernetes thông qua API"
        )
        
        # Thực thi lệnh kubectl delete
        result = subprocess.run(
            ['kubectl', 'delete', '-f', temp_file_path],
            capture_output=True,
            text=True
        )
        
        # Kiểm tra kết quả
        if result.returncode == 0:
            # Cập nhật trạng thái tool
            tool.is_running = False
            tool.save()
            
            # Cập nhật log
            deploy_log.status = 'stopped'
            deploy_log.log += f"\n\nDừng thành công:\n{result.stdout}"
            deploy_log.save()
            
            return JsonResponse({
                'status': 'success',
                'message': f"Đã dừng {tool.name} trên Kubernetes thành công",
                'details': result.stdout
            })
        else:
            # Cập nhật log
            deploy_log.status = 'error'
            deploy_log.log += f"\n\nDừng thất bại:\n{result.stderr}"
            deploy_log.save()
            
            return JsonResponse({
                'status': 'error',
                'message': f"Lỗi khi dừng tool",
                'details': result.stderr
            }, status=400)
        
        # Xóa file tạm
        os.unlink(temp_file_path)
        
    except Tool.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Tool not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)