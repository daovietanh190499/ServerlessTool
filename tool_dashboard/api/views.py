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
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample

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


# Serializer cho việc tạo công cụ
class ToolCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tool
        fields = ['name', 'description', 'python_script', 'requirements']

@extend_schema(
    description="Tạo công cụ mới",
    request=ToolCreateSerializer,
    responses={
        201: {"type": "object", "properties": {
            "id": {"type": "integer"},
            "name": {"type": "string"},
            "slug": {"type": "string"},
            "message": {"type": "string"}
        }},
        400: {"type": "object", "properties": {"error": {"type": "string"}}}
    }
)
@api_view(['POST'])
@permission_classes([AllowAny])
def create_tool_api(request):
    try:
        serializer = ToolCreateSerializer(data=request.data)
        if serializer.is_valid():
            # Tạo công cụ mới
            tool = serializer.save()
            
            # Đảm bảo requirements có fastapi và uvicorn
            default_packages = ["fastapi==0.95.1", "uvicorn==0.22.0"]
            current_requirements = tool.requirements.splitlines() if tool.requirements else []
            current_packages = [line.split('==')[0] for line in current_requirements if line.strip()]
            
            for package in default_packages:
                package_name = package.split('==')[0]
                if package_name not in current_packages:
                    if tool.requirements and not tool.requirements.endswith('\n'):
                        tool.requirements += '\n'
                    tool.requirements += package + '\n'
            
            tool.save()
            
            return JsonResponse({
                'id': tool.id,
                'name': tool.name,
                'slug': tool.slug,
                'message': f'Công cụ {tool.name} đã được tạo thành công'
            }, status=201)
        else:
            return JsonResponse({'error': serializer.errors}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

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


@extend_schema(
    description="Xóa một công cụ",
    parameters=[
        OpenApiParameter(name="tool_id", type=int, location=OpenApiParameter.PATH, description="ID của công cụ")
    ],
    responses={
        200: {"type": "object", "properties": {"message": {"type": "string"}}},
        404: {"type": "object", "properties": {"error": {"type": "string"}}},
        400: {"type": "object", "properties": {"error": {"type": "string"}}}
    }
)
@api_view(['DELETE'])
@permission_classes([AllowAny])
def delete_tool_api(request, tool_id):
    try:
        tool = Tool.objects.get(id=tool_id)
        
        # Nếu công cụ đang chạy, dừng nó trước
        if tool.is_running:
            try:
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
                
                # Thực thi lệnh kubectl delete
                subprocess.run(
                    ['kubectl', 'delete', '-f', temp_file_path],
                    capture_output=True,
                    text=True
                )
                
                # Xóa file tạm
                os.unlink(temp_file_path)
            except Exception as e:
                # Ghi log lỗi nhưng vẫn tiếp tục xóa công cụ
                print(f"Lỗi khi dừng công cụ: {str(e)}")
        
        # Nếu có Docker image, xóa nó
        if tool.docker_image:
            try:
                subprocess.run(
                    ['docker', 'rmi', tool.docker_image],
                    capture_output=True,
                    text=True
                )
            except Exception as e:
                # Ghi log lỗi nhưng vẫn tiếp tục xóa công cụ
                print(f"Lỗi khi xóa Docker image: {str(e)}")
        
        # Lưu tên để hiển thị trong thông báo
        tool_name = tool.name
        
        # Xóa công cụ
        tool.delete()
        
        return JsonResponse({'message': f'Công cụ {tool_name} đã được xóa thành công'})
    except Tool.DoesNotExist:
        return JsonResponse({'error': 'Không tìm thấy công cụ'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)