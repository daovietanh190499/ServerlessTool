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
    messages.success(request, 'Successfully logged out!')
    return redirect('landing')

class UnauthenticatedUserMixin(UserPassesTestMixin):
    def test_func(self):
        return not self.request.user.is_authenticated

class CustomLoginView(UnauthenticatedUserMixin, LoginView):
    template_name = 'dashboard/login.html'
    redirect_authenticated_user = False
    form_class = AuthenticationForm

    def get_success_url(self):
        messages.success(self.request, 'Successfully logged in!')
        return reverse_lazy('landing')

    def form_invalid(self, form):
        messages.error(self.request, 'Invalid email or password.')
        return super().form_invalid(form)

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Successfully logged in!')
        return response

class RegisterView(UnauthenticatedUserMixin, CreateView):
    form_class = CustomUserCreationForm
    template_name = 'dashboard/register.html'
    success_url = reverse_lazy('login')

    def form_valid(self, form):
        try:
            user = form.save()
            messages.success(self.request, 'Account created successfully! Please log in.')
            return redirect('login')
        except Exception as e:
            messages.error(self.request, f'Error creating account: {str(e)}')
            return self.form_invalid(form)

    def form_invalid(self, form):
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(self.request, f"{field}: {error}")
        return super().form_invalid(form) 