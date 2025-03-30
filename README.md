

# Tool Dashboard

Tool Dashboard is a Django application for managing, building, and deploying FastAPI tools as microservices on Kubernetes.

## Features

- Create and manage FastAPI tools
- Edit Python code with Monaco Editor
- Manage environment variables and dependencies
- Build Docker images through Jenkins
- Deploy applications to Kubernetes
- Full API with Swagger UI documentation
- Build and deployment logs management

## Requirements

- Python 3.8+
- Django 4.2+
- Docker
- Kubernetes cluster
- Jenkins (optional, for building)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/tool-dashboard.git
cd tool-dashboard
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate  # Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create and apply migrations:
```bash
python manage.py makemigrations
python manage.py migrate
```

5. Create a superuser:
```bash
python manage.py createsuperuser
```

6. Run the server:
```bash
python manage.py runserver
```

7. Access the dashboard at http://localhost:8000

## Configuration

### Jenkins Configuration

To use Jenkins for building Docker images, you need to configure the following environment variables:

```
JENKINS_URL=http://jenkins:8080
JENKINS_USER=admin
JENKINS_TOKEN=your_jenkins_api_token
```

### Kubernetes Configuration

Ensure kubectl is properly configured to connect to your Kubernetes cluster. You can configure the default namespace in settings.py:

```python
KUBERNETES_NAMESPACE = os.environ.get('KUBERNETES_NAMESPACE', 'tools')
```

## Usage

### Creating a New Tool

1. Access the dashboard and click "Create New Tool"
2. Fill in the required information:
   - Tool name
   - Description
   - Python script (the process() function is required)
   - Requirements (fastapi and uvicorn are added automatically)
3. Click "Save" to create the tool

### Building a Tool

1. Access the tool detail page
2. Click the "Build" button
3. The build process will be executed through Jenkins
4. Build results will be displayed in the "Build Logs" tab

### Deploying a Tool

1. After a successful build, click the "Run" button
2. The tool will be deployed to Kubernetes
3. Deployment status will be displayed in the "Deployment Logs" tab

### Managing Environment Variables

1. Access the tool detail page
2. Click the "Environment Variables" tab
3. Add, edit, or delete environment variables
4. Mark variables as "Secret" if needed

### Managing Dependencies

1. Access the tool detail page
2. Click the "Dependencies" tab
3. Add other tools that this tool depends on

## API

Tool Dashboard provides a complete API for integration with other systems:

- `GET /api/tools/`: Get a list of all tools
- `GET /api/tools/{id}/`: Get detailed information about a tool
- `POST /api/tools/create/`: Create a new tool
- `DELETE /api/tools/{id}/delete/`: Delete a tool
- `POST /api/tools/{id}/deploy/`: Deploy a tool
- `POST /api/tools/{id}/stop/`: Stop a running tool
- `POST /api/build-callback/`: Callback API for the build process

Full API documentation is available at `/api/docs/`

## Project Structure

```
tool_dashboard/
├── api/                  # API application
├── dashboard/            # Dashboard application
├── jenkins/              # Jenkins configuration
├── kubernetes/           # Kubernetes templates
├── templates/            # FastAPI templates
├── static/               # Static files
├── manage.py             # Django management script
├── requirements.txt      # Dependencies
└── README.md             # Documentation
```

## Data Models

- **Tool**: FastAPI tool
- **EnvironmentVariable**: Environment variables for a tool
- **ToolDependency**: Dependency relationships between tools
- **BuildLog**: Build process logs
- **DeploymentLog**: Deployment process logs

## Contributing

Contributions are always welcome! Please create an issue or pull request on GitHub.

## License

This project is distributed under the MIT license. See the `LICENSE` file for more details.

## Contact

If you have any questions, please contact [daovietanh19xx@gmail.com](mailto:daovietanh19xx@gmail.com).
