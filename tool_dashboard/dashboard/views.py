from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.forms import inlineformset_factory
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.exceptions import ObjectDoesNotExist

from .models import Tool, EnvironmentVariable, ToolDependency, BuildLog, DeploymentLog, InputSchema, OutputSchema
from .forms import ToolForm, EnvironmentVariableForm, EnvironmentVariableFormSet, ToolDependencyForm, SchemaForm
import json
import subprocess
import os

import subprocess
import tempfile
import os
from django.conf import settings

class ToolListView(ListView):
    model = Tool
    template_name = 'dashboard/tool_list.html'
    context_object_name = 'tools'

class ToolDetailView(DetailView):
    model = Tool
    template_name = 'dashboard/tool_detail.html'
    context_object_name = 'tool'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tool = self.object
        context['env_vars'] = tool.environmentvariable_set.all()
        context['dependencies'] = tool.dependencies.all()
        context['build_logs'] = tool.build_logs.order_by('-timestamp')[:10]
        context['deployment_logs'] = tool.deployment_logs.order_by('-timestamp')[:5]
        
        # Format input schema
        try:
            input_schema_obj = tool.input_schema
            if input_schema_obj and input_schema_obj.schema:
                # Assume schema is already a dict if JSONField is used
                context['formatted_input_schema'] = json.dumps(input_schema_obj.schema, indent=4)
            else:
                 context['formatted_input_schema'] = None
        except ObjectDoesNotExist:
            context['formatted_input_schema'] = None

        # Format output schema
        try:
            output_schema_obj = tool.output_schema
            if output_schema_obj and output_schema_obj.schema:
                # Assume schema is already a dict if JSONField is used
                context['formatted_output_schema'] = json.dumps(output_schema_obj.schema, indent=4)
            else:
                context['formatted_output_schema'] = None
        except ObjectDoesNotExist:
            context['formatted_output_schema'] = None
        
        return context

class ToolCreateView(CreateView):
    model = Tool
    form_class = ToolForm
    template_name = 'dashboard/tool_form.html'
    success_url = reverse_lazy('dashboard:tool_list')
    
    def get_initial(self):
        initial = super().get_initial()
        initial['requirements'] = "fastapi==0.95.1\nuvicorn==0.22.0\n"
        initial['python_script'] = "# Write your Python script here\n\ndef process(input_data):\n    # Process input_data\n    result = input_data\n    return result"
        # Provide default empty JSON objects for schemas
        initial['input_schema'] = json.dumps({}, indent=4)
        initial['output_schema'] = json.dumps({}, indent=4)
        return initial
    
    def form_valid(self, form):
        # First, save the Tool object
        self.object = form.save()
        
        # Get the parsed schema data from cleaned_data
        input_schema_data = form.cleaned_data['input_schema']
        output_schema_data = form.cleaned_data['output_schema']
        
        # Create the InputSchema and OutputSchema objects
        InputSchema.objects.create(tool=self.object, schema=input_schema_data)
        OutputSchema.objects.create(tool=self.object, schema=output_schema_data)
        
        messages.success(self.request, f"Tool {self.object.name} created successfully!")
        # Redirect to the success_url (tool_list)
        return redirect(self.get_success_url())

class ToolUpdateView(UpdateView):
    model = Tool
    form_class = ToolForm
    template_name = 'dashboard/tool_form.html'
    
    def get_success_url(self):
        return reverse_lazy('dashboard:tool_detail', kwargs={'slug': self.object.slug})
    
    def form_valid(self, form):
        # Save the Tool object first
        self.object = form.save()

        # Get the parsed schema data from cleaned_data
        input_schema_data = form.cleaned_data['input_schema']
        output_schema_data = form.cleaned_data['output_schema']
        
        # Update or create the InputSchema and OutputSchema objects
        InputSchema.objects.update_or_create(
            tool=self.object,
            defaults={'schema': input_schema_data}
        )
        OutputSchema.objects.update_or_create(
            tool=self.object,
            defaults={'schema': output_schema_data}
        )

        messages.success(self.request, f"Tool {self.object.name} updated successfully!")
        # Redirect using superclass logic which uses get_success_url()
        return super().form_valid(form)

class ToolDeleteView(DeleteView):
    model = Tool
    success_url = reverse_lazy('dashboard:tool_list')
    
    def delete(self, request, *args, **kwargs):
        tool = self.get_object()
        messages.success(request, f"Tool {tool.name} has been deleted!")
        return super().delete(request, *args, **kwargs)

def script_editor_view(request, slug):
    tool = get_object_or_404(Tool, slug=slug)
    
    if request.method == 'POST':
        script_content = request.POST.get('script_content', '')
        tool.python_script = script_content
        tool.save()
        messages.success(request, "Script has been saved successfully!")
        return redirect('dashboard:tool_detail', slug=tool.slug)
    
    return render(request, 'dashboard/script_editor.html', {'tool': tool})

def manage_env_vars(request, slug):
    tool = get_object_or_404(Tool, slug=slug)
    
    if request.method == 'POST':
        formset = EnvironmentVariableFormSet(request.POST, instance=tool)
        if formset.is_valid():
            formset.save()
            messages.success(request, "Environment variables updated successfully.")
            return redirect('dashboard:tool_detail', slug=tool.slug)
    else:
        formset = EnvironmentVariableFormSet(instance=tool)
    
    return render(request, 'dashboard/env_var_form.html', {
        'tool': tool,
        'formset': formset,
    })

def add_env_var(request, slug):
    tool = get_object_or_404(Tool, slug=slug)
    
    if request.method == 'POST':
        key = request.POST.get('key')
        value = request.POST.get('value')
        is_secret = request.POST.get('is_secret') == 'on'
        
        if key and value:
            # Kiểm tra xem key đã tồn tại chưa
            if EnvironmentVariable.objects.filter(tool=tool, key=key).exists():
                messages.error(request, f"Environment variable with key '{key}' already exists.")
            else:
                EnvironmentVariable.objects.create(
                    tool=tool,
                    key=key,
                    value=value,
                    is_secret=is_secret
                )
                messages.success(request, f"Environment variable '{key}' added successfully.")
                return redirect('dashboard:manage_env_vars', slug=tool.slug)
        else:
            messages.error(request, "Vui lòng nhập cả key và value.")
    
    env_vars = EnvironmentVariable.objects.filter(tool=tool)
    return render(request, 'dashboard/manage_env_vars.html', {
        'tool': tool,
        'env_vars': env_vars,
    })

def edit_env_var(request, slug, env_id):
    tool = get_object_or_404(Tool, slug=slug)
    env_var = get_object_or_404(EnvironmentVariable, id=env_id, tool=tool)
    
    if request.method == 'POST':
        key = request.POST.get('key')
        value = request.POST.get('value')
        is_secret = request.POST.get('is_secret') == 'on'
        
        if key and value:
            # Kiểm tra xem key mới đã tồn tại chưa (nếu key thay đổi)
            if key != env_var.key and EnvironmentVariable.objects.filter(tool=tool, key=key).exists():
                messages.error(request, f"Environment variable with key '{key}' already exists.")
            else:
                env_var.key = key
                env_var.value = value
                env_var.is_secret = is_secret
                env_var.save()
                messages.success(request, f"Environment variable '{key}' updated successfully.")
                return redirect('dashboard:manage_env_vars', slug=tool.slug)
        else:
            messages.error(request, "Please enter both key and value.")
    
    return render(request, 'dashboard/edit_env_var.html', {
        'tool': tool,
        'env_var': env_var,
    })

def delete_env_var(request, slug, env_id):
    tool = get_object_or_404(Tool, slug=slug)
    env_var = get_object_or_404(EnvironmentVariable, id=env_id, tool=tool)
    
    if request.method == 'POST':
        key = env_var.key
        env_var.delete()
        messages.success(request, f"Environment variable '{key}' deleted successfully.")
    
    return redirect('dashboard:manage_env_vars', slug=tool.slug)

def manage_dependencies(request, slug):
    tool = get_object_or_404(Tool, slug=slug)
    
    if request.method == 'POST':
        form = ToolDependencyForm(request.POST, tool=tool)
        if form.is_valid():
            dependency = form.save(commit=False)
            dependency.tool = tool
            dependency.save()
            messages.success(request, "Dependency added successfully!")
            return redirect('dashboard:tool_detail', slug=tool.slug)
    else:
        form = ToolDependencyForm(tool=tool)
    
    dependencies = tool.dependencies.all()
    return render(request, 'dashboard/dependency_form.html', {
        'tool': tool,
        'form': form,
        'dependencies': dependencies
    })

def remove_dependency(request, pk):
    dependency = get_object_or_404(ToolDependency, pk=pk)
    tool_slug = dependency.tool.slug
    dependency.delete()
    messages.success(request, "Dependency deleted successfully!")
    return redirect('dashboard:tool_detail', slug=tool_slug)

def build_tool(request, slug):
    tool = get_object_or_404(Tool, slug=slug)
    
    # Gọi Jenkins pipeline để build Docker image
    try:
        # Ở đây bạn sẽ tích hợp với Jenkins API
        # Đây chỉ là mã giả
        jenkins_url = os.environ.get('JENKINS_URL', 'http://jenkins:8080')
        job_name = 'build-tool-image'
        
        # Tạo file tạm thời chứa thông tin build
        build_info = {
            'tool_id': tool.id,
            'tool_name': tool.name,
            'python_script': tool.python_script,
            'requirements': tool.requirements,
        }
        
        # Ghi log
        build_log = BuildLog.objects.create(
            tool=tool,
            status='started',
            log=f"Started building Docker image for {tool.name}"
        )
        
        # Cập nhật trạng thái tool
        tool.build_status = 'building'
        tool.save()
        
        # Gọi Jenkins API (mã giả)
        # subprocess.Popen(['curl', '-X', 'POST', f"{jenkins_url}/job/{job_name}/buildWithParameters",
        #                  '--data', f"TOOL_ID={tool.id}"])
        
        messages.success(request, f"Started building Docker image for {tool.name}. Please check the logs for progress.")
    except Exception as e:
        messages.error(request, f"Error building tool: {str(e)}")
        build_log = BuildLog.objects.create(
            tool=tool,
            status='error',
            log=f"Error: {str(e)}"
        )
        tool.build_status = 'error'
        tool.save()
    
    return redirect('dashboard:tool_detail', slug=tool.slug)

def deploy_tool(request, slug):
    tool = get_object_or_404(Tool, slug=slug)
    
    if not tool.is_built:
        messages.error(request, "Tool needs to be built before deployment!")
        return redirect('dashboard:tool_detail', slug=tool.slug)
    
    try:
        # Lấy tất cả biến môi trường
        env_vars = tool.environmentvariable_set.all()
        
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
            log=f"Started deploying {tool.name} to Kubernetes"
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
            
            messages.success(request, f"Successfully deployed {tool.name} to Kubernetes!")
        else:
            # Cập nhật log
            deploy_log.status = 'error'
            deploy_log.log += f"\n\nDeploy failed:\n{result.stderr}"
            deploy_log.save()
            
            messages.error(request, f"Error deploying tool: {result.stderr}")
        
        # Xóa file tạm
        os.unlink(temp_file_path)
        
    except Exception as e:
        messages.error(request, f"Error deploying tool: {str(e)}")
        deploy_log = DeploymentLog.objects.create(
            tool=tool,
            status='error',
            log=f"Error: {str(e)}"
        )
    
    return redirect('dashboard:tool_detail', slug=tool.slug)

def stop_tool(request, slug):
    tool = get_object_or_404(Tool, slug=slug)
    
    if not tool.is_running:
        messages.error(request, "Tool is not running!")
        return redirect('dashboard:tool_detail', slug=tool.slug)
    
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
        
        # Ghi log
        deploy_log = DeploymentLog.objects.create(
            tool=tool,
            status='stopping',
            log=f"Starting to stop {tool.name} on Kubernetes"
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
            
            messages.success(request, f"Successfully stopped {tool.name} on Kubernetes!")
        else:
            # Cập nhật log
            deploy_log.status = 'error'
            deploy_log.log += f"\n\nFailed to stop:\n{result.stderr}"
            deploy_log.save()
            
            messages.error(request, f"Error stopping tool: {result.stderr}")
        
        # Xóa file tạm
        os.unlink(temp_file_path)
        
    except Exception as e:
        messages.error(request, f"Error stopping tool: {str(e)}")
        deploy_log = DeploymentLog.objects.create(
            tool=tool,
            status='error',
            log=f"Error: {str(e)}"
        )
    
    return redirect('dashboard:tool_detail', slug=tool.slug)

def delete_tool(request, slug):
    tool = get_object_or_404(Tool, slug=slug)
    
    if request.method == 'POST':
        try:
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
                    print(f"Error stopping tool: {str(e)}")
            
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
                    print(f"Error deleting Docker image: {str(e)}")
            
            # Lưu tên để hiển thị trong thông báo
            tool_name = tool.name
            
            # Xóa công cụ
            tool.delete()
            
            messages.success(request, f'Tool {tool_name} has been deleted successfully')
            return redirect('dashboard:tool_list')
        except Exception as e:
            messages.error(request, f'Error deleting tool: {str(e)}')
            return redirect('dashboard:tool_detail', slug=slug)
    
    return render(request, 'dashboard/tool_confirm_delete.html', {'tool': tool})

# def deploy_tool(request, slug):
#     tool = get_object_or_404(Tool, slug=slug)
    
#     if not tool.is_built:
#         messages.error(request, "Công cụ cần được build trước khi deploy!")
#         return redirect('tool_detail', slug=tool.slug)
    
#     try:
#         # Ở đây bạn sẽ tích hợp với Kubernetes API
#         # Đây chỉ là mã giả
        
#         # Lấy tất cả biến môi trường
#         env_vars = {env.key: env.value for env in tool.environmentvariable_set.all()}
        
#         # Ghi log
#         deploy_log = DeploymentLog.objects.create(
#             tool=tool,
#             status='started',
#             log=f"Bắt đầu deploy {tool.name} lên Kubernetes"
#         )
        
#         # Cập nhật trạng thái tool
#         tool.is_running = True
#         tool.save()
        
#         messages.success(request, f"Đã bắt đầu deploy {tool.name} lên Kubernetes. Vui lòng kiểm tra log để biết tiến độ.")
#     except Exception as e:
#         messages.error(request, f"Lỗi khi deploy tool: {str(e)}")
#         deploy_log = DeploymentLog.objects.create(
#             tool=tool,
#             status='error',
#             log=f"Lỗi: {str(e)}"
#         )
    
#     return redirect('tool_detail', slug=tool.slug)

@csrf_exempt
def update_build_status(request):
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

def landing_page(request):
    return render(request, 'dashboard/landing.html')

class CustomLoginView(LoginView):
    template_name = 'dashboard/login.html'
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse_lazy('dashboard:tool_list')

class RegisterView(CreateView):
    form_class = UserCreationForm
    template_name = 'dashboard/register.html'
    success_url = reverse_lazy('dashboard:login')

    def form_valid(self, form):
        response = super().form_valid(form)
        user = form.save()
        login(self.request, user)
        return response 

@login_required
def edit_input_schema(request, tool_id):
    tool = get_object_or_404(Tool, id=tool_id)
    
    if request.method == 'POST':
        form = SchemaForm(request.POST)
        if form.is_valid():
            schema_data = form.cleaned_data['schema']
            
            # Create or update input schema
            InputSchema.objects.update_or_create(
                tool=tool,
                defaults={'schema': schema_data}
            )
            
            messages.success(request, "Input schema updated successfully.")
            return redirect('dashboard:tool_detail', slug=tool.slug)
        else:
            messages.error(request, "Invalid schema data.")
    else:
        initial_data = {}
        if hasattr(tool, 'input_schema'):
            initial_data['schema'] = tool.input_schema.schema
        
        form = SchemaForm(initial=initial_data)
    
    return render(request, 'dashboard/schema_form.html', {
        'form': form,
        'tool': tool,
        'title': 'Edit Input Schema'
    })

@login_required
def edit_output_schema(request, tool_id):
    tool = get_object_or_404(Tool, id=tool_id)
    
    if request.method == 'POST':
        form = SchemaForm(request.POST)
        if form.is_valid():
            schema_data = form.cleaned_data['schema']
            
            # Create or update output schema
            OutputSchema.objects.update_or_create(
                tool=tool,
                defaults={'schema': schema_data}
            )
            
            messages.success(request, 'Output schema updated successfully')
            return redirect('dashboard:tool_detail', slug=tool.slug)
    else:
        initial_data = {}
        if hasattr(tool, 'output_schema'):
            initial_data['schema'] = tool.output_schema.schema
        
        form = SchemaForm(initial=initial_data)
    
    return render(request, 'dashboard/schema_form.html', {
        'form': form,
        'tool': tool,
        'title': 'Edit Output Schema'
    }) 