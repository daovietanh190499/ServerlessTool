from django import forms
from django.forms import inlineformset_factory
from .models import Tool, EnvironmentVariable, ToolDependency, InputSchema, OutputSchema
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
import json

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
    input_schema = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 6, 'placeholder': '{\n    "param1": "string",\n    "param2": "number"\n}'}),
        help_text="Define the expected JSON structure for input data. This schema will be used to validate incoming requests to the tool's API endpoint.",
        required=True
    )
    output_schema = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 6, 'placeholder': '{\n    "result": "string",\n    "status_code": "integer"\n}'}),
        help_text="Define the expected JSON structure for the tool's output. This helps document the tool's response format.",
        required=True
    )

    class Meta:
        model = Tool
        fields = ['name', 'description', 'python_script', 'requirements']
        widgets = {
            'python_script': forms.Textarea(attrs={
                'rows': 10,
                'class': 'form-control code-editor',
                'placeholder': '# Write your Python script here\n\ndef process(input_data):\n    # Process input_data\n    result = input_data\n    return result'
            }),
            'requirements': forms.Textarea(attrs={
                'rows': 5, 
                'placeholder': 'fastapi==0.95.1\nuvicorn==0.22.0\n# Add other packages here'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default values for new instances
        if not self.instance.pk:
            if not self.initial.get('requirements'):
                self.initial['requirements'] = "fastapi==0.95.1\nuvicorn==0.22.0\n"
            if not self.initial.get('python_script'):
                self.initial['python_script'] = "# Write your Python script here\n\ndef process(input_data):\n    # Process input_data\n    result = input_data\n    return result"
            if 'input_schema' not in self.initial:
                self.initial['input_schema'] = json.dumps({}, indent=4)
            if 'output_schema' not in self.initial:
                self.initial['output_schema'] = json.dumps({}, indent=4)
        # Load existing schema data for existing instances
        else:
            try:
                input_schema_obj = self.instance.input_schema
                if input_schema_obj and input_schema_obj.schema:
                     self.initial['input_schema'] = json.dumps(input_schema_obj.schema, indent=4)
            except InputSchema.DoesNotExist:
                self.initial['input_schema'] = json.dumps({}, indent=4)
            
            try:
                output_schema_obj = self.instance.output_schema
                if output_schema_obj and output_schema_obj.schema:
                     self.initial['output_schema'] = json.dumps(output_schema_obj.schema, indent=4)
            except OutputSchema.DoesNotExist:
                 self.initial['output_schema'] = json.dumps({}, indent=4)

    def clean_input_schema(self):
        data = self.cleaned_data['input_schema']
        try:
            # Validate and parse JSON
            parsed_data = json.loads(data)
            if not isinstance(parsed_data, dict):
                raise forms.ValidationError("Input schema must be a valid JSON object.")
            return parsed_data # Return parsed dict
        except json.JSONDecodeError:
            raise forms.ValidationError("Invalid JSON format for Input Schema.")
        except Exception as e:
            raise forms.ValidationError(f"Error parsing Input Schema: {e}")

    def clean_output_schema(self):
        data = self.cleaned_data['output_schema']
        try:
            # Validate and parse JSON
            parsed_data = json.loads(data)
            if not isinstance(parsed_data, dict):
                raise forms.ValidationError("Output schema must be a valid JSON object.")
            return parsed_data # Return parsed dict
        except json.JSONDecodeError:
            raise forms.ValidationError("Invalid JSON format for Output Schema.")
        except Exception as e:
            raise forms.ValidationError(f"Error parsing Output Schema: {e}")

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

class SchemaForm(forms.Form):
    schema = forms.JSONField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 10,
            'placeholder': 'Enter JSON schema here...'
        }),
        help_text='Enter a valid JSON schema for input/output validation'
    )

    def clean_schema(self):
        schema = self.cleaned_data['schema']
        try:
            # Validate that it's a valid JSON
            json.dumps(schema)
            return schema
        except (TypeError, ValueError):
            raise forms.ValidationError('Invalid JSON format') 