from django import forms
from .models import Tool, EnvironmentVariable, ToolDependency

class ToolForm(forms.ModelForm):
    class Meta:
        model = Tool
        fields = ['name', 'description', 'python_script', 'requirements']
        widgets = {
            'python_script': forms.Textarea(attrs={
                'rows': 10,
                'class': 'form-control code-editor',
                'placeholder': '# Viết script Python của bạn ở đây\n\ndef process(input_data):\n    # Xử lý input_data\n    result = input_data\n    return result'
            }),
            'requirements': forms.Textarea(attrs={
                'rows': 5, 
                'placeholder': 'fastapi==0.95.1\nuvicorn==0.22.0\n# Thêm các gói khác ở đây'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Đảm bảo requirements có sẵn các gói mặc định khi tạo form mới
        if not self.instance.pk and not self.initial.get('requirements'):
            self.initial['requirements'] = "fastapi==0.95.1\nuvicorn==0.22.0\n"
        
        # Đảm bảo python_script có mẫu mặc định khi tạo form mới
        if not self.instance.pk and not self.initial.get('python_script'):
            self.initial['python_script'] = "# Viết script Python của bạn ở đây\n\ndef process(input_data):\n    # Xử lý input_data\n    result = input_data\n    return result"

class EnvironmentVariableForm(forms.ModelForm):
    class Meta:
        model = EnvironmentVariable
        fields = ['key', 'value', 'is_secret']

class ToolDependencyForm(forms.ModelForm):
    dependent_tool = forms.ModelChoiceField(queryset=Tool.objects.all())
    
    class Meta:
        model = ToolDependency
        fields = ['dependent_tool']
    
    def __init__(self, *args, **kwargs):
        tool = kwargs.pop('tool', None)
        super().__init__(*args, **kwargs)
        if tool:
            # Loại bỏ công cụ hiện tại và các công cụ đã phụ thuộc
            self.fields['dependent_tool'].queryset = Tool.objects.exclude(
                id__in=[tool.id] + list(tool.dependencies.values_list('dependent_tool_id', flat=True))
            ) 