import re

class IntentParser:
    async def parse_intent(self, text: str) -> str:
        """
        Parses inbound SMS text to determine patient intent.
        Returns one of: 'CANCEL', 'RESCHEDULE', 'CONFIRM', 'SUPPORT'
        """
        text = text.lower().strip()
        
        # TCPA compliance opt-out check (STOP keywords take absolute precedence)
        if re.search(r"\b(stop|unsubscribe|optout|opt-out|cancel_sms)\b", text):
            return "OPT_OUT"
            
        # Simple keyword matching for the Phase 2 MVP
        if re.search(r"\b(cancel|no|don'?t|quit|abort)\b", text):
            return "CANCEL"
        elif re.search(r"\b(reschedule|change|move|different time|later|earlier)\b", text):
            return "RESCHEDULE"
        elif re.search(r"\b(yes|confirm|ok|okay|yep|sure|see you)\b", text):
            return "CONFIRM"
        else:
            return "SUPPORT"

intent_parser = IntentParser()
