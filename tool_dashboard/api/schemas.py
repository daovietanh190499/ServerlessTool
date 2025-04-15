from typing import Any, Dict, Optional
from pydantic import BaseModel, create_model, ValidationError
import json

def create_pydantic_model(schema: Dict[str, Any]) -> type[BaseModel]:
    """
    Dynamically create a Pydantic model from a JSON schema
    """
    fields = {}
    for field_name, field_type in schema.items():
        # Convert JSON schema types to Python types
        if field_type == "string":
            field_type = str
        elif field_type == "integer":
            field_type = int
        elif field_type == "number":
            field_type = float
        elif field_type == "boolean":
            field_type = bool
        else:
            field_type = str  # Default to string if type is unknown
        
        fields[field_name] = (field_type, ...)  # ... means field is required
    
    return create_model('DynamicModel', **fields)

def validate_input(tool_id: int, input_data: Dict[str, Any]) -> None:
    """
    Validate input data against the tool's input schema
    """
    from dashboard.models import InputSchema
    
    try:
        input_schema = InputSchema.objects.get(tool_id=tool_id)
        schema_dict = input_schema.schema
        model = create_pydantic_model(schema_dict)
        model(**input_data)  # This will raise ValidationError if invalid
    except InputSchema.DoesNotExist:
        raise ValidationError("No input schema defined for this tool")
    except json.JSONDecodeError:
        raise ValidationError("Invalid schema format")

def validate_output(tool_id: int, output_data: Dict[str, Any]) -> None:
    """
    Validate output data against the tool's output schema
    """
    from dashboard.models import OutputSchema
    
    try:
        output_schema = OutputSchema.objects.get(tool_id=tool_id)
        schema_dict = output_schema.schema
        model = create_pydantic_model(schema_dict)
        model(**output_data)  # This will raise ValidationError if invalid
    except OutputSchema.DoesNotExist:
        raise ValidationError("No output schema defined for this tool")
    except json.JSONDecodeError:
        raise ValidationError("Invalid schema format")

class SchemaValidationError(Exception):
    """Custom exception for schema validation errors"""
    pass 