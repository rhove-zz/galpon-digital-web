# 📚 Referencias - Recursos Externos y Documentación

Compilación de documentación externa, estándares, patrones y recursos útiles.

---

## 🏛️ Patrones y Conceptos

### ReAct Pattern (Reason + Act)
**Archivo**: [react-pattern.md](react-pattern.md)  
**Tipo**: Patrón de diseño  
**Aplicación**: Core del agent loop  

**Descripción**: Patrón iterativo que intercala razonamiento con acción.

**Referencias**:
- Papel original: https://arxiv.org/abs/2210.03629
- Componentes: Observation → Thought → Action → Conclude

---

### Clean Architecture
**Documento**: [clean-architecture.md](clean-architecture.md) (referencia planificada)
**Tipo**: Principios de diseño  
**Aplicación**: Estructura de módulos  

**Principios**:
- Independencia de frameworks
- Testeable
- Agnóstico a UI/DB
- Fácil mantenimiento

---

### SOLID Principles
**Documento**: [solid-principles.md](solid-principles.md) (referencia planificada)
**Tipo**: Principios OOP  

**Aplicación en ACU**:
- S (Single Responsibility): Cada módulo una responsabilidad
- O (Open/Closed): Extensible sin modificar
- L (Liskov): Substituibilidad de componentes
- I (Interface Segregation): Interfaces específicas
- D (Dependency Inversion): Inyección de dependencias

---

### Domain-Driven Design (DDD)
**Documento**: [ddd-concepts.md](ddd-concepts.md) (referencia planificada)
**Tipo**: Metodología de diseño  

**Aplicación**: Lenguaje ubicuo alrededor de ReAct, Herramientas, Memoria

---

## 🔧 Tecnologías

### Ollama - Local LLM
**Enlace**: https://ollama.ai/  
**Documento**: [ollama-docs.md](ollama-docs.md)  

**Uso en ACU**:
- HTTP API en puerto 11434
- Soporte para múltiples modelos
- Ejecución local (privada)
- API compatible con OpenAI

**Modelos soportados**:
- Mistral 7B (recomendado)
- Gemma 7B
- Neural Chat 7B

---

### MySQL 8.0
**Enlace**: https://dev.mysql.com/  
**Documento**: [mysql-docs.md](mysql-docs.md)  

**Uso en ACU**:
- Base de datos de memoria evolutiva
- Lectura de `information_schema`
- Usuario read-only (`acu_reader`)
- Puerto 3306

**Conceptos clave**:
- information_schema (metadatos)
- Privileges (permisos)
- User management

---

### ChromaDB - Vector Database
**Enlace**: https://www.trychroma.com/  
**Documento**: [chromadb-docs.md](chromadb-docs.md) (referencia planificada)

**Uso planeado**:
- Búsqueda semántica de documentos
- Embeddings con sentence-transformers
- Fase 2 implementation

---

### Docker & Docker Compose
**Enlace**: https://www.docker.com/  
**Documento**: [docker-docs.md](docker-docs.md) (referencia planificada)

**Uso en ACU**:
- Containerización de servicios
- Orquestación local con Compose
- Reproducibilidad
- CI/CD ready

---

### Pydantic v2
**Enlace**: https://docs.pydantic.dev/  
**Documento**: [pydantic-docs.md](pydantic-docs.md) (referencia planificada)

**Uso en ACU**:
- Validación de datos
- Serialización JSON
- Type hints
- Error messages claros

---

## 📚 Estándares de Código

### PEP 8 - Python Style Guide
**Enlace**: https://pep8.org/  

**Aplicación en ACU**:
- Naming conventions
- Indentation (4 espacios)
- Line length (88 con Black)
- Imports organization

### Type Hints (PEP 484)
**Enlace**: https://www.python.org/dev/peps/pep-0484/  

**Aplicación en ACU**:
- 100% type hints en todo código
- Optional para valores opcionales
- Union para tipos múltiples
- Generic types para colecciones

### Docstring Format (PEP 257)
**Enlace**: https://www.python.org/dev/peps/pep-0257/  

**Aplicación en ACU**:
- Google-style docstrings
- Descripción clara
- Args y Returns
- Examples

---

## 🧪 Testing

### Pytest
**Enlace**: https://docs.pytest.org/  
**Documento**: [pytest-guide.md](pytest-guide.md) (referencia planificada)

**Uso planeado en Fase 2**:
- Unit tests
- Integration tests
- Fixtures
- Mocking

### Test Coverage
**Herramienta**: coverage.py  
**Meta**: >80% coverage en Fase 2

---

## 📖 Formatos de Documentación

### Markdown
**Especificación**: https://commonmark.org/  
**Herramienta**: GitHub Flavored Markdown (GFM)

**Elementos usados**:
- Headers (#, ##, ###)
- Lists (-, •)
- Code blocks (```python```)
- Tables
- Links y referencias

### Mermaid Diagrams
**Enlace**: https://mermaid.js.org/  

**Tipos usados**:
- Flowcharts
- State diagrams
- Dependency graphs

---

## 🔗 Tutoriales y Guías Internas

### Python Async/Await
**Documento**: [python-async-guide.md](python-async-guide.md) (referencia planificada)

Cómo usar `asyncio` en ACU:
- async def / await
- asyncio.run()
- Coroutines
- Event loops

### SQL Query Optimization
**Documento**: [sql-optimization.md](sql-optimization.md) (referencia planificada)

Best practices para queries SELECT en ACU.

### LLM Prompting
**Documento**: [llm-prompting-guide.md](llm-prompting-guide.md) (referencia planificada)

Técnicas para mejores prompts:
- Few-shot learning
- Prompt engineering
- Tool use optimization

---

## 📊 Métricas y Monitoring

### Python Code Metrics
**Herramientas**:
- Black (formatting)
- Flake8 (linting)
- Pylint (code analysis)
- Coverage.py (test coverage)

### Logging Best Practices
**Documento**: [logging-guide.md](logging-guide.md) (referencia planificada)

---

## 🌐 APIs y Servicios Externos

### Ollama HTTP API
**Documentación**: https://github.com/ollama/ollama/blob/main/docs/api.md  

**Endpoints usados**:
- POST /api/generate
- GET /api/tags
- POST /api/pull

### OpenAI API Compatibility
**Enlace**: https://openai.com/api/  

**Nota**: Ollama API es compatible, uso local

---

## 📚 Libros y Papers Recomendados

### Papers
- ReAct Pattern: https://arxiv.org/abs/2210.03629
- Language Models as Zero-Shot Planners
- Chain-of-Thought Prompting

### Libros
- Clean Architecture (Robert C. Martin)
- Design Patterns (Gang of Four)
- Python Cookbook

---

## 🔍 Herramientas Útiles

### IDE & Editors
- VS Code (recomendado)
- PyCharm Pro
- Vim/Neovim

### CLI Tools
- git
- Docker CLI
- python
- pip / poetry

### Dev Tools
- Docker Desktop
- MySQL Workbench
- Postman / Insomnia

---

## 📋 Cómo Usar Esta Sección

### Para Entender un Concepto
1. Buscar en índice arriba
2. Leer documento si existe (README de tema)
3. Seguir enlace externo si aplica
4. Consultar código fuente

### Para Agregar una Referencia
1. Crear documento: `tema.md`
2. Agregar al índice de este README
3. Incluir enlaces externos
4. Dar contexto de uso en ACU

---

## 🗺️ Mapa de Referencias

```
Conceptos
├─ Patrones
│  ├─ ReAct
│  ├─ Clean Architecture
│  └─ Domain-Driven Design
└─ Principios
   ├─ SOLID
   └─ Type Safety

Tecnologías
├─ LLM
│  └─ Ollama
├─ Base de Datos
│  └─ MySQL
├─ Vector DB
│  └─ ChromaDB
└─ Lenguaje
   ├─ Python 3.11+
   └─ AsyncIO

Herramientas
├─ Development
│  ├─ Docker
│  └─ Docker Compose
├─ Testing
│  └─ Pytest
└─ Code Quality
   ├─ Black
   ├─ Flake8
   └─ Coverage
```

---

## 🔗 Enlaces Rápidos

**Documentación del Proyecto**:
- [README Principal](../../README.md)
- [Arquitectura](../01-estructura/01-arquitectura-core.md)
- [Componentes](../03-componentes/README.md)
- [Decisiones](../04-decisiones/README.md)

**Recursos Externos**:
- [Ollama](https://ollama.ai/)
- [MySQL Docs](https://dev.mysql.com/)
- [Python Docs](https://docs.python.org/)
- [AsyncIO Guide](https://docs.python.org/3/library/asyncio.html)

---

**Última actualización**: 23 Abril 2024  
**Próxima actualización**: Agregar documentos específicos conforme se necesiten
