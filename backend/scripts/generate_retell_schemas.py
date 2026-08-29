import os
import json
import sys

# Ensure backend path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.tools.appointments import (
    CheckCalendarAvailabilityTool,
    BookNewAppointmentTool,
    CancelExistingAppointmentTool,
    RescheduleAppointmentTool,
    AddToWaitlistTool
)
from src.tools.clinical import (
    LogPatientSymptomsTool,
    CheckExistingPatientTool
)
from src.tools.telephony import (
    SendLiveSmsLinkTool,
    TransferCallToHumanTool
)
from src.tools.tenant_faq import (
    CheckServicePricingTool,
    GetClinicFaqTool
)

def generate_all_schemas():
    tools = [
        CheckCalendarAvailabilityTool(),
        BookNewAppointmentTool(),
        CancelExistingAppointmentTool(),
        RescheduleAppointmentTool(),
        AddToWaitlistTool(),
        LogPatientSymptomsTool(),
        CheckExistingPatientTool(),
        SendLiveSmsLinkTool(),
        TransferCallToHumanTool(),
        CheckServicePricingTool(),
        GetClinicFaqTool()
    ]
    
    output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'schemas_output'))
    os.makedirs(output_dir, exist_ok=True)
    
    all_schemas = []
    
    for tool in tools:
        schema = tool.get_retell_schema()
        all_schemas.append(schema)
        
        # Save individually
        file_path = os.path.join(output_dir, f"{tool.name}.json")
        with open(file_path, "w") as f:
            json.dump(schema, f, indent=2)
            
    # Save combined
    with open(os.path.join(output_dir, "all_retell_tools.json"), "w") as f:
        json.dump(all_schemas, f, indent=2)
        
    print(f"Successfully generated {len(tools)} Retell AI tool schemas in '{output_dir}' directory!")

if __name__ == "__main__":
    generate_all_schemas()
