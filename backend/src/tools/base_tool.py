import traceback
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import log


class BaseTool(ABC):
    """
    Abstract base class for all AI Voice Tools.
    Forces a standard execution pattern, error handling, and audit logging.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name matching the Retell AI schema (e.g., 'book_new_appointment')"""
        pass
        
    @property
    @abstractmethod
    def description(self) -> str:
        """Description of what the tool does, for the LLM to understand."""
        pass
        
    @property
    @abstractmethod
    def args_schema(self) -> type[BaseModel]:
        """Pydantic model defining the arguments schema."""
        pass
        
    def get_retell_schema(self) -> dict[str, Any]:
        """Generates OpenAI-compatible function schema for Retell AI."""
        schema = self.args_schema.model_json_schema()
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": schema.get("properties", {}),
                    "required": schema.get("required", [])
                }
            }
        }

    async def run(self, db: AsyncSession, tenant_id: str, call_id: str, args: dict[str, Any]) -> dict[str, Any]:
        """
        Wrapper to handle validation, logging and top-level exception catching.
        """
        log.info(f"[Tool:{self.name}] Executing for call {call_id} with args: {args}")
        try:
            # Pydantic validation
            validated_args = self.args_schema(**args).model_dump()
            
            result = await self.execute(db, tenant_id, call_id, validated_args)
            log.info(f"[Tool:{self.name}] Execution successful.")
            return {"success": True, "result": result}
        except ValidationError as e:
            log.warning(f"[Tool:{self.name}] Validation failed: {e}")
            return {
                "success": False,
                "message": f"Tool argument validation failed. Please provide correct parameters. Details: {e.errors()}"
            }
        except Exception as e:
            log.error(f"[Tool:{self.name}] Execution failed: {str(e)}")
            log.debug(traceback.format_exc())
            # Return graceful error to AI so it can inform the patient
            return {
                "success": False,
                "error": {
                    "message": str(e)
                }
            }

    @abstractmethod
    async def execute(self, db: AsyncSession, tenant_id: str, call_id: str, args: dict[str, Any]) -> dict[str, Any]:
        """
        Actual tool logic to be implemented by subclasses.
        """
        pass
