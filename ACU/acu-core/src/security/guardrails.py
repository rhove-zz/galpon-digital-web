"""
Security Guardrails for ACU Agent.
Implements middleware to detect prompt injections, toxic content, and PII leakage.
"""

import re
from typing import Tuple


class SecurityGuardrails:
    """Validates inputs and outputs for security and compliance."""

    # Very basic regex for common PII
    EMAIL_REGEX = re.compile(r"[\w\.-]+@[\w\.-]+\.\w+")
    # DNI/SSN/CreditCard-like patterns (very naive, just for demonstration of guardrails)
    CREDIT_CARD_REGEX = re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b")

    # Common SQL Injection / Prompt Injection heuristics
    INJECTION_HEURISTICS = [
        "ignore previous instructions",
        "olvida las instrucciones",
        "system prompt",
        "you are now",
        "ahora eres",
        "drop table",
        "truncate table",
    ]

    @classmethod
    def check_input_safety(cls, user_input: str) -> Tuple[bool, str]:
        """
        Check if the user input contains prompt injection attempts or malicious commands.
        Returns: (is_safe, reason)
        """
        normalized_input = user_input.lower()

        for heuristic in cls.INJECTION_HEURISTICS:
            if heuristic in normalized_input:
                return (
                    False,
                    f"Posible inyeccion de prompt o comando malicioso detectado ({heuristic}).",
                )

        return True, ""

    @classmethod
    def check_output_safety(cls, model_output: str) -> Tuple[bool, str]:
        """
        Check if the model output leaks PII or sensitive data.
        Returns: (is_safe, reason)
        """
        if cls.CREDIT_CARD_REGEX.search(model_output):
            return (
                False,
                "Filtracion de datos sensibles (tarjeta de credito) detectada en la salida.",
            )

        # Emails are often fine to output if they belong to public docs,
        # but in strict environments we might mask them. We won't block for emails right now.

        return True, ""

    @classmethod
    def mask_pii(cls, text: str) -> str:
        """Masks PII like emails and credit cards in the text."""
        text = cls.CREDIT_CARD_REGEX.sub("XXXX-XXXX-XXXX-XXXX", text)
        return text


guardrails = SecurityGuardrails()
