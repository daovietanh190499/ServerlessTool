from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.text import slugify

class User(AbstractUser):
    email = models.EmailField(unique=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.email

class Tool(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True)
    python_script = models.TextField(blank=True)
    requirements = models.TextField(blank=True, help_text="Mỗi package trên một dòng")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    docker_image = models.CharField(max_length=255, blank=True)
    is_built = models.BooleanField(default=False)
    is_running = models.BooleanField(default=False)
    build_status = models.CharField(max_length=50, default="not_built")
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

class EnvironmentVariable(models.Model):
    tool = models.ForeignKey(Tool, on_delete=models.CASCADE)
    key = models.CharField(max_length=255)
    value = models.TextField()
    is_secret = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ('tool', 'key')
    
    def __str__(self):
        return f"{self.key} ({self.tool.name})"

class ToolDependency(models.Model):
    tool = models.ForeignKey(Tool, on_delete=models.CASCADE, related_name='dependencies')
    dependent_tool = models.ForeignKey(Tool, on_delete=models.CASCADE, related_name='dependent_tools')
    
    class Meta:
        unique_together = ('tool', 'dependent_tool')
    
    def __str__(self):
        return f"{self.tool.name} -> {self.dependent_tool.name}"

class BuildLog(models.Model):
    tool = models.ForeignKey(Tool, on_delete=models.CASCADE, related_name='build_logs')
    log = models.TextField()
    status = models.CharField(max_length=50)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.tool.name} - {self.timestamp}"

class DeploymentLog(models.Model):
    tool = models.ForeignKey(Tool, on_delete=models.CASCADE, related_name='deployment_logs')
    log = models.TextField()
    status = models.CharField(max_length=50)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.tool.name} - {self.timestamp}" 