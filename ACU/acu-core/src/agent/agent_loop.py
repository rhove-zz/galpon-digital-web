"""
Main Agent Loop - ReAct Implementation
Core orchestration logic for the Autonomous Cognitive Agent.
"""

from typing import List, AsyncGenerator, Optional
from uuid import uuid4
import json

from src.agent.prompting import get_prompt_builder
from src.config.settings import agent_config
from src.llm.provider import get_llm_client as get_ollama_client
from src.memory.mysql_manager import get_db_connector
from src.tools.tools_manager import get_tools_manager
from src.utils.logger import log
from src.utils.schemas import Message, ReActState, ToolCall, ToolType


class ACUAgent:
    """
    Autonomous Cognitive Universal Agent.

    Implements the ReAct (Reason + Act) pattern with:
    - Dynamic schema injection from MySQL
    - Evolutionary memory management
    - Tool-based information access
    - Autonomous decision making
    """

    def __init__(self, domain: str = "generic", persona: str = "default"):
        """
        Initialize ACU Agent.

        Args:
            domain: Domain/project identifier (e.g., "agente360", "crm", "generic")
            persona: Perfil tecnico del agente (default, arquitecto, analista_datos, devsecops)
        """
        self.domain = domain
        self.persona = persona
        self.db_connector = get_db_connector(use_read_only=True)
        self.write_connector = get_db_connector(use_read_only=False)
        self.ollama_client = get_ollama_client()
        self.tools_manager = get_tools_manager()
        self.prompt_builder = get_prompt_builder(self.db_connector)

        self.conversation_history: List[Message] = []
        self.system_prompt: Optional[str] = None
        self.current_plan: Optional[str] = None
        self.session_id = f"{domain}-{uuid4()}"
        self.session_persisted = False
        self.total_iterations = 0

        log.info(f"ACU Agent inicializado - Dominio: {domain}")

    async def initialize(self, session_id: Optional[str] = None) -> bool:
        """
        Initialize agent dependencies and perform health checks.

        Args:
            session_id: Optional existing session ID to resume
        """
        log.info("Inicializando ACU Agent...")

        if not self.ollama_client.check_connection():
            log.error("No se pudo conectar a Ollama")
            return False

        if not self.db_connector.connect():
            log.error("No se pudo conectar a MySQL")
            return False

        schema = self.db_connector.get_database_schema()
        if not schema:
            log.warning("No se pudo extraer schema (continuando sin el)")

        self.system_prompt = self.prompt_builder.build_system_prompt(
            persona=self.persona
        )

        if session_id:
            self.session_id = session_id
            self.session_persisted = True

            # Cargar historial desde Redis
            from src.memory.redis_manager import redis_manager

            history_data = await redis_manager.get_session_history(self.session_id)
            if history_data:
                self.conversation_history = [Message(**msg) for msg in history_data]
                log.info(f"Sesion recuperada desde Redis: {self.session_id}")
        else:
            prompt_content = self.system_prompt if self.system_prompt else ""
            self.conversation_history.append(
                Message(role="system", content=prompt_content)
            )
            self.session_persisted = self.write_connector.start_agent_session(
                session_id=self.session_id,
                domain=self.domain,
            )
            if not self.session_persisted:
                log.warning("La sesion del agente no pudo persistirse")

        log.info("Inicializacion completada exitosamente")
        return True

    async def process_user_message(self, user_input: str) -> str:
        """
        Process user message through the ReAct loop.

        Args:
            user_input: User's query or instruction

        Returns:
            Final response from the agent
        """
        log.info(f"Usuario: {user_input[:100]}")

        from src.security.guardrails import guardrails

        is_safe, reason = guardrails.check_input_safety(user_input)
        if not is_safe:
            log.warning(f"Entrada de usuario bloqueada por Guardrails: {reason}")
            return f"Error de Seguridad: {reason}"

        self.conversation_history.append(Message(role="user", content=user_input))

        current_state = ReActState(step=0)
        iteration = 0

        while not current_state.is_complete and iteration < agent_config.max_iterations:
            iteration += 1
            log.info(f"\n--- ITERACION ReAct #{iteration} ---")
            current_state.action = None

            await self._observation_phase(current_state, user_input)
            await self._thought_phase(current_state, user_input)

            if current_state.is_complete:
                if not current_state.final_answer:
                    await self._conclusion_phase(current_state, user_input)
            elif current_state.action:
                await self._action_phase(current_state)
            else:
                await self._conclusion_phase(current_state, user_input)

            current_state.step += 1

        final_response = (
            current_state.final_answer or "No se pudo generar una respuesta."
        )

        # Guardrails Output Check
        is_safe, reason = guardrails.check_output_safety(final_response)
        if not is_safe:
            log.warning(f"Salida del modelo bloqueada por Guardrails: {reason}")
            final_response = f"[REDACTADO POR SEGURIDAD] La respuesta original fue bloqueada: {reason}"
        else:
            final_response = guardrails.mask_pii(final_response)

        self.total_iterations += iteration

        self.conversation_history.append(
            Message(role="assistant", content=final_response)
        )
        self._persist_conversation_turn(
            user_input=user_input,
            final_response=final_response,
            steps_used=iteration,
        )

        from src.memory.redis_manager import redis_manager

        await redis_manager.save_session_history(
            self.session_id, [msg.model_dump() for msg in self.conversation_history]
        )

        log.info(f"\nAgente: {final_response[:100]}")
        return final_response

    async def process_user_message_stream(
        self, user_input: str
    ) -> AsyncGenerator[str, None]:
        """
        Process user message through the ReAct loop and yield Server-Sent Events (SSE).
        """
        log.info(f"Usuario (Stream): {user_input[:100]}")

        from src.security.guardrails import guardrails

        is_safe, reason = guardrails.check_input_safety(user_input)
        if not is_safe:
            log.warning(f"Entrada de usuario bloqueada por Guardrails: {reason}")
            yield f"data: {json.dumps({'type': 'error', 'content': f'Error de Seguridad: {reason}'})}\n\n"
            return

        self.conversation_history.append(Message(role="user", content=user_input))

        current_state = ReActState(step=0)
        iteration = 0

        while not current_state.is_complete and iteration < agent_config.max_iterations:
            iteration += 1
            current_state.action = None

            yield f"data: {json.dumps({'type': 'status', 'content': f'Iteración {iteration} iniciada...'})}\n\n"

            # OBSERVATION Phase
            await self._observation_phase(current_state, user_input)

            # THOUGHT Phase with streaming
            yield f"data: {json.dumps({'type': 'status', 'content': 'Analizando y razonando...'})}\n\n"

            thought_buffer = ""
            action_prompt = f"""
Basandote en tu analisis:
- Observacion: {(current_state.observation or "Ninguna")[:300]}
- Pensamiento anterior: {(current_state.thought or "Ninguno")[:300]}

Cual es tu siguiente accion?

Si necesitas informacion:
1. PRIMERO, consulta tu memoria evolutiva si hay incertidumbre
2. Luego, elige entre ejecutar SQL, buscar documentos, buscar contexto BrainCore, o registrar lecciones
3. Si tienes suficiente informacion, responde al usuario

Responde en formato JSON con la herramienta a invocar, o "CONCLUDE" si has terminado.
"""
            for token in self.ollama_client.generate_stream(
                system_prompt=self.system_prompt or "",
                user_message=action_prompt,
                conversation_history=self._format_history_for_llm(),
                temperature=agent_config.temperature,
                top_p=agent_config.top_p,
            ):
                thought_buffer += token
                yield f"data: {json.dumps({'type': 'thought_token', 'content': token})}\n\n"

            # Process thought output
            tool_calls = self.ollama_client.parse_tool_calls(thought_buffer)
            if tool_calls:
                try:
                    current_state.action = ToolCall(
                        tool=tool_calls[0].get("tool", ToolType.SQL_READ),
                        parameters=tool_calls[0].get("parameters", {}),
                        reasoning=thought_buffer[:200],
                    )
                except Exception as exc:
                    log.warning(f"Tool call invalido en stream: {exc}")
                    current_state.is_complete = True
                    current_state.final_answer = (
                        "Error: invocacion de herramienta invalida."
                    )
                    yield f"data: {json.dumps({'type': 'error', 'content': current_state.final_answer})}\n\n"
                    break

                yield f"data: {json.dumps({'type': 'tool_call', 'tool': str(current_state.action.tool.value if hasattr(current_state.action.tool, 'value') else current_state.action.tool), 'parameters': current_state.action.parameters})}\n\n"

                # ACTION Phase
                yield f"data: {json.dumps({'type': 'status', 'content': f'Ejecutando {current_state.action.tool}...'})}\n\n"
                tool_result = await self.tools_manager.execute_tool(
                    current_state.action,
                    self.session_id,
                    agent_domain=self.domain,
                    agent_persona=self.persona,
                )
                if tool_result.status == "pending_approval":
                    current_state.final_answer = (
                        "Herramienta pendiente de aprobacion humana. "
                        f"ID de aprobacion: {tool_result.pending_tool_id}"
                    )
                    current_state.is_complete = True
                    yield f"data: {json.dumps({'type': 'approval_required', 'pending_tool_id': tool_result.pending_tool_id, 'tool': current_state.action.tool.value, 'parameters': current_state.action.parameters})}\n\n"
                    yield f"data: {json.dumps({'type': 'conclusion', 'content': current_state.final_answer})}\n\n"
                    break
                if tool_result.success:
                    current_state.observation = f"Resultado de {current_state.action.tool}: {str(tool_result.result)[:500]}"
                    yield f"data: {json.dumps({'type': 'tool_result', 'success': True, 'content': current_state.observation})}\n\n"
                else:
                    current_state.observation = (
                        f"Error en {current_state.action.tool}: {tool_result.error}"
                    )
                    yield f"data: {json.dumps({'type': 'tool_result', 'success': False, 'content': current_state.observation})}\n\n"
                    if current_state.action.tool == ToolType.SQL_READ:
                        yield f"data: {json.dumps({'type': 'status', 'content': 'Activando auto-corrección SQL...'})}\n\n"

                current_state.step += 1
                continue

            # No tool calls -> either "conclude" or plain response
            normalized_response = thought_buffer.lower()
            if "conclude" in normalized_response or "terminado" in normalized_response:
                yield f"data: {json.dumps({'type': 'status', 'content': 'Formulando respuesta final...'})}\n\n"
                conclusion_prompt = f"""
Basandote en toda la informacion recopilada en este analisis:

Pregunta original: {user_input}
Pasos realizados: {current_state.step}
Ultima observacion: {(current_state.observation or "Ninguna")[:300]}

Proporciona una respuesta clara, concisa y accionable al usuario.
"""
                final_answer_buffer = ""
                for token in self.ollama_client.generate_stream(
                    system_prompt=self.system_prompt or "",
                    user_message=conclusion_prompt,
                    conversation_history=self._format_history_for_llm(),
                    temperature=agent_config.temperature * 0.7,
                    top_p=agent_config.top_p,
                ):
                    final_answer_buffer += token
                    yield f"data: {json.dumps({'type': 'answer_token', 'content': token})}\n\n"

                current_state.final_answer = final_answer_buffer
                current_state.is_complete = True
            else:
                current_state.is_complete = True
                current_state.final_answer = thought_buffer

        final_answer = current_state.final_answer or "No se pudo generar respuesta."

        # Guardrails Output Check
        is_safe, reason = guardrails.check_output_safety(final_answer)
        if not is_safe:
            log.warning(
                f"Salida del modelo bloqueada por Guardrails en stream: {reason}"
            )
            final_answer = f"[REDACTADO POR SEGURIDAD] La respuesta original fue bloqueada: {reason}"
            yield f"data: {json.dumps({'type': 'error', 'content': final_answer})}\n\n"
        else:
            final_answer = guardrails.mask_pii(final_answer)

        self.total_iterations += iteration

        self.conversation_history.append(
            Message(role="assistant", content=final_answer)
        )
        self._persist_conversation_turn(user_input, final_answer, iteration)

        # Guardar historial asincronamente en Redis
        from src.memory.redis_manager import redis_manager

        await redis_manager.save_session_history(
            self.session_id, [msg.model_dump() for msg in self.conversation_history]
        )

        yield f"data: {json.dumps({'type': 'done', 'iterations': iteration, 'session_id': str(self.session_id)})}\n\n"

    def _persist_conversation_turn(
        self,
        user_input: str,
        final_response: str,
        steps_used: int,
    ) -> None:
        """Persist one conversation turn without blocking agent response."""
        if not self.session_persisted:
            return

        persisted = self.write_connector.log_conversation_context(
            session_id=self.session_id,
            user_query=user_input,
            agent_response=final_response,
            steps_used=steps_used,
        )
        if not persisted:
            log.debug("Contexto conversacional no persistido")

    async def _observation_phase(self, state: ReActState, user_query: str):
        """OBSERVATION phase: Analyze context and available information."""
        log.debug("OBSERVATION: Analizando contexto...")

        context_msg = f"""
## OBSERVACION

Usuario pregunta: {user_query}

Paso actual: {state.step}
Observacion previa: {state.observation or "Ninguna"}

Que informacion tengo? Que informacion necesito?
"""

        state.observation = context_msg
        log.debug(f"Contexto construido: {context_msg[:200]}")

    async def _thought_phase(self, state: ReActState, user_query: str):
        """
        THOUGHT phase: Reason about next action.
        Includes planning for complex tasks (>3 steps).
        """
        log.debug("THOUGHT: Razonando sobre acciones...")

        if state.step == 0:
            planning_prompt = f"""
Dada esta consulta: "{user_query}"

Cuantos pasos principales necesitas para resolverla?
Si son mas de {agent_config.planning_threshold}, genera un plan step-by-step que comuniques al usuario.

Se breve y directo.
"""

            thought_response = self.ollama_client.generate_response(
                system_prompt=self.system_prompt or "",
                user_message=planning_prompt,
                conversation_history=self._format_history_for_llm(),
                temperature=agent_config.temperature,
                top_p=agent_config.top_p,
            )

            if not thought_response:
                log.error("El LLM no respondio durante la fase THOUGHT")
                state.is_complete = True
                state.final_answer = "No se pudo obtener una respuesta del modelo para planificar la tarea."
                return

            state.thought = thought_response
            log.debug(f"Pensamiento generado: {thought_response[:200]}")

            normalized_thought = thought_response.lower()
            if "<plan>" in normalized_thought:
                import re

                plan_match = re.search(
                    r"<plan>(.*?)</plan>", thought_response, re.DOTALL | re.IGNORECASE
                )
                if plan_match:
                    self.current_plan = plan_match.group(1).strip()
                    log.info(f"Plan persistente capturado: {self.current_plan[:50]}...")
            elif "plan" in normalized_thought or "pasos" in normalized_thought:
                log.info("Modo planificacion activado sin etiquetas <plan>")

        # Inject persistent plan into action context
        plan_context = (
            f"\n- Plan Actual Vigente:\n{self.current_plan}"
            if self.current_plan
            else ""
        )

        action_prompt = f"""
Basandote en tu analisis:{plan_context}
- Observacion: {(state.observation or "Ninguna")[:300]}
- Pensamiento anterior: {(state.thought or "Ninguno")[:300]}

Cual es tu siguiente accion?

Si necesitas informacion:
1. PRIMERO, consulta tu memoria evolutiva si hay incertidumbre
2. Luego, elige entre ejecutar SQL, buscar documentos, buscar contexto BrainCore, o registrar lecciones
3. Si tienes suficiente informacion, responde al usuario

Responde en formato JSON con la herramienta a invocar, o "CONCLUDE" si has terminado.
"""

        response = self.ollama_client.generate_response(
            system_prompt=self.system_prompt or "",
            user_message=action_prompt,
            conversation_history=self._format_history_for_llm(),
            temperature=agent_config.temperature,
            top_p=agent_config.top_p,
        )

        if not response:
            log.error("El LLM no respondio al decidir la siguiente accion")
            state.is_complete = True
            state.final_answer = "No se pudo obtener una respuesta del modelo para decidir la siguiente accion."
            return

        tool_calls = self.ollama_client.parse_tool_calls(response)

        if tool_calls:
            try:
                state.action = ToolCall(
                    tool=tool_calls[0].get("tool", ToolType.SQL_READ),
                    parameters=tool_calls[0].get("parameters", {}),
                    reasoning=(state.thought or "")[:200],
                )
            except Exception as exc:
                log.warning(f"Tool call invalido devuelto por el LLM: {exc}")
                state.is_complete = True
                state.final_answer = "El modelo devolvio una invocacion de herramienta invalida y el agente detuvo la ejecucion."
                return

            log.debug(f"Accion determinada: {state.action.tool}")
            return

        normalized_response = response.lower()
        state.action = None

        if "conclude" in normalized_response or "terminado" in normalized_response:
            state.is_complete = True
            state.final_answer = response
        else:
            log.warning("No se parseo herramienta clara. Continuando...")
            state.is_complete = True
            state.final_answer = response

    async def _action_phase(self, state: ReActState):
        """ACTION phase: Execute the determined tool."""
        if not state.action:
            return

        log.debug(f"ACTION: Ejecutando {state.action.tool}...")

        tool_result = await self.tools_manager.execute_tool(
            state.action,
            self.session_id,
            agent_domain=self.domain,
            agent_persona=self.persona,
        )

        if tool_result.status == "pending_approval":
            state.final_answer = (
                "Herramienta pendiente de aprobacion humana. "
                f"ID de aprobacion: {tool_result.pending_tool_id}"
            )
            state.is_complete = True
        elif tool_result.success:
            log.info(f"Herramienta exitosa ({tool_result.execution_time_ms:.1f}ms)")
            state.observation = (
                f"Resultado de {state.action.tool}: {str(tool_result.result)[:500]}"
            )
        else:
            log.warning(f"Error en herramienta: {tool_result.error}")
            state.observation = f"Error en {state.action.tool}: {tool_result.error}"

            if state.action.tool == ToolType.SQL_READ:
                log.info("Activando auto-correccion para SQL...")

    async def _conclusion_phase(self, state: ReActState, user_query: str):
        """CONCLUSION phase: Generate final answer from gathered information."""
        log.debug("CONCLUSION: Formulando respuesta final...")

        conclusion_prompt = f"""
Basandote en toda la informacion recopilada en este analisis:

Pregunta original: {user_query}
Pasos realizados: {state.step}
Ultima observacion: {(state.observation or "Ninguna")[:300]}

Proporciona una respuesta clara, concisa y accionable al usuario.
"""

        final_response = self.ollama_client.generate_response(
            system_prompt=self.system_prompt or "",
            user_message=conclusion_prompt,
            conversation_history=self._format_history_for_llm(),
            temperature=agent_config.temperature * 0.7,
            top_p=agent_config.top_p,
        )

        state.final_answer = (
            final_response
            or "No se pudo generar una conclusion porque el modelo no respondio."
        )
        state.is_complete = True

    async def resume_after_tool_approval(self, pending_tool: dict) -> str:
        """Resume a conversation after a pending HITL tool was approved and executed."""
        tool_name = str(pending_tool.get("tool", "herramienta"))
        parameters = pending_tool.get("parameters", {})
        tool_result = pending_tool.get("result", {})
        pending_tool_id = str(pending_tool.get("id", pending_tool.get("tool_id", "")))

        resume_prompt = f"""
Se aprobo y ejecuto una herramienta que habia quedado pendiente por Human-in-the-Loop.

ID de aprobacion: {pending_tool_id}
Herramienta: {tool_name}
Parametros: {json.dumps(parameters, ensure_ascii=False)}
Resultado: {json.dumps(tool_result, ensure_ascii=False)}

Retoma la conversacion con el usuario. Explica el resultado relevante de forma clara,
sin repetir detalles internos innecesarios, y continua con la respuesta final que
corresponda.
"""
        final_response = self.ollama_client.generate_response(
            system_prompt=self.system_prompt or "",
            user_message=resume_prompt,
            conversation_history=self._format_history_for_llm(),
            temperature=agent_config.temperature * 0.7,
            top_p=agent_config.top_p,
        )

        if not final_response:
            final_response = (
                "La herramienta aprobada se ejecuto, pero no se pudo generar "
                "una respuesta de reanudacion desde el modelo."
            )

        from src.security.guardrails import guardrails

        is_safe, reason = guardrails.check_output_safety(final_response)
        if not is_safe:
            log.warning(f"Salida de reanudacion HITL bloqueada: {reason}")
            final_response = (
                "[REDACTADO POR SEGURIDAD] La respuesta de reanudacion fue "
                f"bloqueada: {reason}"
            )
        else:
            final_response = guardrails.mask_pii(final_response)

        self.conversation_history.append(
            Message(role="assistant", content=final_response)
        )
        self._persist_conversation_turn(
            user_input=f"Reanudacion HITL {pending_tool_id}".strip(),
            final_response=final_response,
            steps_used=0,
        )

        from src.memory.redis_manager import redis_manager

        await redis_manager.save_session_history(
            self.session_id, [msg.model_dump() for msg in self.conversation_history]
        )
        return final_response

    def _format_history_for_llm(self) -> List[dict]:
        """Format conversation history for LLM context."""
        return [
            {"role": msg.role, "content": msg.content}
            for msg in self.conversation_history[-6:]
        ]

    async def shutdown(self):
        """Gracefully shutdown agent and cleanup resources."""
        log.info("Apagando ACU Agent...")
        if self.session_persisted:
            self.write_connector.end_agent_session(
                session_id=self.session_id,
                total_iterations=self.total_iterations,
                status="completed",
            )
        self.db_connector.disconnect()
        self.write_connector.disconnect()
        log.info("Agent desconectado")


async def get_agent(domain: str = "generic", persona: str = "default") -> ACUAgent:
    """Get a new agent instance."""
    return ACUAgent(domain=domain, persona=persona)
