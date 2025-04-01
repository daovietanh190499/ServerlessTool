from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy
from django.views.generic import CreateView
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.mixins import UserPassesTestMixin
from .forms import CustomUserCreationForm

def landing_page(request):
    return render(request, 'dashboard/landing.html')

def logout_view(request):
    logout(request)
    messages.success(request, '👋 See you again! You have been successfully logged out.')
    return redirect('landing')

class UnauthenticatedUserMixin(UserPassesTestMixin):
    def test_func(self):
        return not self.request.user.is_authenticated

class CustomLoginView(UnauthenticatedUserMixin, LoginView):
    template_name = 'dashboard/login.html'
    redirect_authenticated_user = True
    form_class = AuthenticationForm

    def get_success_url(self):
        messages.success(self.request, '🎉 Welcome back! You have successfully logged in.')
        next_url = self.request.GET.get('next')
        if next_url:
            return next_url
        return reverse_lazy('landing')

    def form_invalid(self, form):
        messages.error(self.request, '❌ Oops! The email or password you entered is incorrect. Please try again.')
        return super().form_invalid(form)

    def form_valid(self, form):
        response = super().form_valid(form)
        # Add cache control headers to prevent back button issues
        response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response

class RegisterView(UnauthenticatedUserMixin, CreateView):
    form_class = CustomUserCreationForm
    template_name = 'dashboard/register.html'
    success_url = reverse_lazy('login')

    def form_valid(self, form):
        try:
            user = form.save()
            messages.success(self.request, '✨ Awesome! Your account has been created successfully. Please log in to continue.')
            return redirect('login')
        except Exception as e:
            messages.error(self.request, f'❌ Something went wrong: {str(e)}')
            return self.form_invalid(form)

    def form_invalid(self, form):
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(self.request, f'❌ {field.title()}: {error}')
        return super().form_invalid(form) 