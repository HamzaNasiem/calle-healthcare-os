from retell import Retell
import anyio
from typing import Dict, Any
from .base_connector import BaseVoiceConnector
from ...core.config import settings
from ...core.resilience import CircuitBreaker

# Share a single circuit breaker across all Retell Voice connector instances
retell_breaker = CircuitBreaker("RetellVoice", failure_threshold=5, recovery_timeout_seconds=60.0)

class RetellVoiceConnector(BaseVoiceConnector):
    def __init__(self):
        # Initialize Retell SDK client dynamically
        self.retell = Retell(api_key=settings.RETELL_API_KEY)

    def _create_llm(self, **kwargs) -> Any:
        return self.retell.llm.create(**kwargs)

    def _create_agent(self, **kwargs) -> Any:
        return self.retell.agent.create(**kwargs)

    def _retrieve_agent(self, agent_id: str) -> Any:
        return self.retell.agent.retrieve(agent_id)

    def _update_llm(self, llm_id: str, **kwargs) -> Any:
        return self.retell.llm.update(llm_id, **kwargs)

    def _create_phone_call(self, **kwargs) -> Any:
        return self.retell.call.create_phone_call(**kwargs)

    def _stop_call(self, call_id: str) -> Any:
        return self.retell.call.stop(call_id)

    async def create_agent(self, clinic_name: str, prompt: str, webhook_url: str) -> str:
        async def _execute():
            # Create Retell LLM
            llm = await anyio.to_thread.run_sync(
                lambda: self._create_llm(
                    general_prompt=prompt,
                    general_tools=[
                        {
                            "type": "end_call",
                            "name": "end_call",
                            "description": "End the call with user."
                        }
                    ]
                )
            )
            
            # Create Retell Agent
            agent = await anyio.to_thread.run_sync(
                lambda: self._create_agent(
                    response_engine={
                        "type": "retell-llm",
                        "llm_id": llm.llm_id
                    },
                    agent_name=f"{clinic_name} Receptionist",
                    voice_id="11labs-Adrian",
                    language="en-US",
                    webhook_url=webhook_url
                )
            )
            return agent.agent_id

        return await retell_breaker.call(_execute)

    async def update_agent(self, agent_id: str, prompt: str) -> None:
        async def _execute():
            agent = await anyio.to_thread.run_sync(lambda: self._retrieve_agent(agent_id))
            llm_id = None
            if agent and agent.response_engine:
                if hasattr(agent.response_engine, "llm_id"):
                    llm_id = agent.response_engine.llm_id
                elif isinstance(agent.response_engine, dict):
                    llm_id = agent.response_engine.get("llm_id")
                    
            if not llm_id:
                raise Exception("Could not resolve Retell LLM ID for the agent.")
                
            await anyio.to_thread.run_sync(
                lambda: self._update_llm(
                    llm_id,
                    general_prompt=prompt,
                    general_tools=[
                        {
                            "type": "end_call",
                            "name": "end_call",
                            "description": "End the call with user."
                        }
                    ]
                )
            )

        await retell_breaker.call(_execute)

    async def make_outbound_call(self, from_number: str, to_number: str, agent_id: str, call_type: str, dynamic_variables: dict) -> str:
        async def _execute():
            call = await anyio.to_thread.run_sync(
                lambda: self._create_phone_call(
                    from_number=from_number,
                    to_number=to_number,
                    override_agent_id=agent_id,
                    retell_llm_dynamic_variables={
                        "call_type": call_type,
                        **dynamic_variables
                    }
                )
            )
            return call.call_id

        return await retell_breaker.call(_execute)

    async def stop_call(self, call_id: str) -> None:
        async def _execute():
            await anyio.to_thread.run_sync(lambda: self._stop_call(call_id))

        await retell_breaker.call(_execute)
