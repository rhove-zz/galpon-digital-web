"""
Data models and schemas for ACU using Pydantic.
Defines structured types for tools, memory, and agent state.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime


class ToolType(str, Enum):
    """Tipos de herramientas disponibles."""

    SQL_READ = "ejecutar_sql_lectura"
    VECTOR_SEARCH = "buscar_documentos"
    BRAINCORE_SEARCH = "buscar_contexto_braincore"
    REGISTER_LESSON = "registrar_leccion"
    QUERY_LESSONS = "consultar_lecciones_aprendidas"
    WEB_READ = "leer_pagina_web"
    WEB_SEARCH = "busqueda_web"
    API_REST = "peticion_api_rest"
    FILE_SYSTEM = "gestionar_archivos"
    PYTHON_SANDBOX = "ejecutar_python"
    DELEGATE_TASK = "delegar_tarea"
    WRITE_SHARED_MEMORY = "escribir_memoria_compartida"
    READ_SHARED_MEMORY = "leer_memoria_compartida"


class ToolCall(BaseModel):
    """Estructura de una llamada a herramienta."""

    tool: ToolType
    parameters: Dict[str, Any]
    reasoning: Optional[str] = Field(
        None, description="Por qué el agente invoca esta herramienta"
    )


class ToolResult(BaseModel):
    """Resultado de la ejecución de una herramienta."""

    tool: ToolType
    success: bool
    result: Any
    error: Optional[str] = None
    execution_time_ms: float
    status: str = "completed"
    pending_tool_id: Optional[str] = None


class MemoryEntry(BaseModel):
    """Entrada en la memoria evolutiva."""

    id: Optional[int] = None
    categoria: str
    leccion_aprendida: str
    fecha_registro: datetime = Field(default_factory=datetime.now)


class DatabaseSchema(BaseModel):
    """Representación del esquema dinámico de base de datos."""

    database: str
    tables: Dict[str, Dict[str, Any]]  # {table_name: {columns: [...], keys: [...]}}


class ReActState(BaseModel):
    """Estado actual del bucle ReAct."""

    step: int
    observation: Optional[str] = None
    thought: Optional[str] = None
    action: Optional[ToolCall] = None
    is_complete: bool = False
    final_answer: Optional[str] = None


class Message(BaseModel):
    """Mensaje en el historial de conversación."""

    role: str  # "user", "assistant", "system"
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)


class ConversationContext(BaseModel):
    """Contexto completo de una conversación."""

    user_query: str
    history: List[Message] = Field(default_factory=list)
    db_schema: Optional[DatabaseSchema] = None
    relevant_lessons: List[MemoryEntry] = Field(default_factory=list)
    current_step: int = 0
