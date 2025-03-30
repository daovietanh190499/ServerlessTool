from django import forms
from .models import Tool, EnvironmentVariable, ToolDependency

class ToolForm(forms.ModelForm):
    class Meta:
        model = Tool
        fields = ['name', 'description', 'python_script', 'requirements']
        widgets = {
            'python_script': forms.HiddenInput(),
            'requirements': forms.Textarea(attrs={'rows': 5, 'placeholder': 'fastapi==0.95.1\nuvicorn==0.22.0'})
        }

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