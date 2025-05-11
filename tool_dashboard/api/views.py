from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from dashboard.models import Tool, BuildLog, DeploymentLog, InputSchema, OutputSchema
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
from rest_framework.response import Response
from rest_framework import status
from .schemas import validate_input, validate_output, SchemaValidationError

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
    },
    examples=[
        OpenApiExample(
            'Ví dụ tạo công cụ',
            value={
                'name': 'Công cụ mới',
                'description': 'Mô tả công cụ',
                'python_script': '# Script Python\n\ndef process(input_data):\n    return {"result": input_data}',
                'requirements': 'fastapi==0.95.1\nuvicorn==0.22.0\npandas==1.5.3'
            },
            request_only=True,
        )
    ]
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
            
            # Đảm bảo python_script có mẫu mặc định nếu trống
            if not tool.python_script:
                tool.python_script = "# Write your Python script here\n\ndef process(input_data):\n    # Process input_data\n    result = input_data\n    return result"
            
            tool.save()
            
            return JsonResponse({
                'id': tool.id,
                'name': tool.name,
                'slug': tool.slug,
                'message': f'Tool {tool.name} created successfully'
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
    description="Deploy a tool to Kubernetes",
    parameters=[
        OpenApiParameter(name="tool_id", type=int, location=OpenApiParameter.PATH, description="ID of the tool")
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
                'message': 'Tool needs to be built before deployment'
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
            log=f"Started deploying {tool.name} to Kubernetes via API"
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
            deploy_log.log += f"\n\nSuccessfully deployed:\n{result.stdout}"
            deploy_log.save()
            
            return JsonResponse({
                'status': 'success',
                'message': f"Successfully deployed {tool.name} to Kubernetes",
                'details': result.stdout
            })
        else:
            # Cập nhật log
            deploy_log.status = 'error'
            deploy_log.log += f"\n\nDeployment failed:\n{result.stderr}"
            deploy_log.save()
            
            return JsonResponse({
                'status': 'error',
                'message': f"Error deploying tool",
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
    description="Stop a running tool on Kubernetes",
    parameters=[
        OpenApiParameter(name="tool_id", type=int, location=OpenApiParameter.PATH, description="ID of the tool")
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
                'message': 'Tool is not running'
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
            log=f"Started stopping {tool.name} on Kubernetes via API"
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
            deploy_log.log += f"\n\nSuccessfully stopped:\n{result.stdout}"
            deploy_log.save()
            
            return JsonResponse({
                'status': 'success',
                'message': f"Successfully stopped {tool.name} on Kubernetes",
                'details': result.stdout
            })
        else:
            # Cập nhật log
            deploy_log.status = 'error'
            deploy_log.log += f"\n\nDeployment failed:\n{result.stderr}"
            deploy_log.save()
            
            return JsonResponse({
                'status': 'error',
                'message': f"Error stopping tool",
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
    description="Delete a tool",
    parameters=[
        OpenApiParameter(name="tool_id", type=int, location=OpenApiParameter.PATH, description="ID of the tool")
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
        
        # If the tool is running, stop it first
        if tool.is_running:
            try:
                # Create a temporary file to save YAML
                with tempfile.NamedTemporaryFile(suffix='.yaml', delete=False) as temp_file:
                    temp_file_path = temp_file.name
                    
                    # Read the YAML template
                    with open(os.path.join(settings.BASE_DIR, 'kubernetes/deployment_template.yaml'), 'r') as f:
                        deployment_template = f.read()
                    
                    # Replace variables in the template
                    deployment_yaml = deployment_template.format(
                        tool_slug=tool.slug,
                        docker_image=tool.docker_image,
                        env_vars=""
                    )
                    
                    temp_file.write(deployment_yaml.encode())
                
                # Execute the kubectl delete command
                subprocess.run(
                    ['kubectl', 'delete', '-f', temp_file_path],
                    capture_output=True,
                    text=True
                )
                
                # Delete the temporary file
                os.unlink(temp_file_path)
            except Exception as e:
                # Log the error but continue with tool deletion
                print(f"Error stopping tool: {str(e)}")
        
        # If there is a Docker image, delete it
        if tool.docker_image:
            try:
                subprocess.run(
                    ['docker', 'rmi', tool.docker_image],
                    capture_output=True,
                    text=True
                )
            except Exception as e:
                # Log the error but continue with tool deletion
                print(f"Error deleting Docker image: {str(e)}")
        
        # Lưu tên để hiển thị trong thông báo
        tool_name = tool.name
        
        # Xóa công cụ
        tool.delete()
        
        return JsonResponse({'message': f'Tool {tool_name} has been deleted successfully'})
    except Tool.DoesNotExist:
        return JsonResponse({'error': 'Tool not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@api_view(['POST'])
def update_input_schema(request, tool_id):
    try:
        tool = Tool.objects.get(id=tool_id)
        schema_data = request.data.get('schema')
        
        if not schema_data:
            return Response(
                {"error": "Schema data is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate that schema_data is valid JSON
        try:
            json.loads(json.dumps(schema_data))
        except json.JSONDecodeError:
            return Response(
                {"error": "Invalid JSON schema"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create or update input schema
        input_schema, created = InputSchema.objects.update_or_create(
            tool=tool,
            defaults={'schema': schema_data}
        )
        
        return Response({
            "message": "Input schema updated successfully",
            "schema": input_schema.schema
        })
    
    except Tool.DoesNotExist:
        return Response(
            {"error": "Tool not found"},
            status=status.HTTP_404_NOT_FOUND
        )

@api_view(['POST'])
def update_output_schema(request, tool_id):
    try:
        tool = Tool.objects.get(id=tool_id)
        schema_data = request.data.get('schema')
        
        if not schema_data:
            return Response(
                {"error": "Schema data is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate that schema_data is valid JSON
        try:
            json.loads(json.dumps(schema_data))
        except json.JSONDecodeError:
            return Response(
                {"error": "Invalid JSON schema"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create or update output schema
        output_schema, created = OutputSchema.objects.update_or_create(
            tool=tool,
            defaults={'schema': schema_data}
        )
        
        return Response({
            "message": "Output schema updated successfully",
            "schema": output_schema.schema
        })
    
    except Tool.DoesNotExist:
        return Response(
            {"error": "Tool not found"},
            status=status.HTTP_404_NOT_FOUND
        )

@api_view(['POST'])
def execute_tool(request, tool_id):
    try:
        tool = Tool.objects.get(id=tool_id)
        input_data = request.data
        
        # Validate input against schema
        try:
            validate_input(tool_id, input_data)
        except ValidationError as e:
            return Response(
                {"error": "Input validation failed", "details": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Execute the tool (existing logic)
        # ... existing execution code ...
        
        # Validate output against schema
        try:
            validate_output(tool_id, output_data)
        except ValidationError as e:
            return Response(
                {"error": "Output validation failed", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        return Response(output_data)
    
    except Tool.DoesNotExist:
        return Response(
            {"error": "Tool not found"},
            status=status.HTTP_404_NOT_FOUND
        )
    except SchemaValidationError as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )