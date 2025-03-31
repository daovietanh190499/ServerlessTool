from django import forms
from django.forms import inlineformset_factory
from .models import Tool, EnvironmentVariable, ToolDependency
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    
    class Meta:
        model = get_user_model()
        fields = ('username', 'email', 'password1', 'password2')
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if get_user_model().objects.filter(email=email).exists():
            raise forms.ValidationError('This email is already registered.')
        return email
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user

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
        widgets = {
            'key': forms.TextInput(attrs={'class': 'form-control'}),
            'value': forms.TextInput(attrs={'class': 'form-control'}),
            'is_secret': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

EnvironmentVariableFormSet = inlineformset_factory(
    Tool, 
    EnvironmentVariable, 
    form=EnvironmentVariableForm,
    extra=1,
    can_delete=True
)

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