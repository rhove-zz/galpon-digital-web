"""
ACU Core - Main entry point.
Autonomous Cognitive Universal Agent Orchestrator.
"""

import asyncio
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent))

from src.agent.agent_loop import ACUAgent
from src.utils.logger import log


async def main():
    """Main entry point for the interactive ACU agent."""
    log.info("=" * 60)
    log.info("ACU - AGENTE COGNITIVO UNIVERSAL v1.0")
    log.info("=" * 60)

    agent = ACUAgent(domain="generic")

    try:
        success = await agent.initialize()
        if not success:
            log.error("Inicializacion fallida. Abortando.")
            return 1

        log.info("\nAgente listo. Escribe 'salir' para terminar.\n")

        while True:
            try:
                user_input = input("Tu: ").strip()

                if not user_input:
                    continue

                if user_input.lower() in ["salir", "exit", "quit"]:
                    log.info("Hasta luego.")
                    break

                response = await agent.process_user_message(user_input)
                print(f"\nAgente: {response}\n")
            except KeyboardInterrupt:
                log.info("\nInterrupcion del usuario.")
                break
            except Exception as exc:
                log.error(f"Error en loop: {exc}")
                continue

        return 0
    except Exception as exc:
        log.error(f"Error critico: {exc}")
        return 1
    finally:
        await agent.shutdown()


async def demo_mode():
    """Demo mode with predefined queries."""
    log.info("=" * 60)
    log.info("ACU - MODO DEMOSTRACION")
    log.info("=" * 60)

    agent = ACUAgent(domain="demo")

    try:
        success = await agent.initialize()
        if not success:
            return 1

        demo_queries = [
            "Cuantos usuarios activos tenemos en la base de datos?",
            "Busca informacion sobre configuracion de autenticacion",
            "Cual es la estructura de la tabla de usuarios?",
        ]

        for query in demo_queries:
            log.info(f"\nDemo Query: {query}")
            response = await agent.process_user_message(query)
            print(f"Respuesta: {response}\n")
            print("-" * 60)

        return 0
    except Exception as exc:
        log.error(f"Error en demo: {exc}")
        return 1
    finally:
        await agent.shutdown()


def print_banner():
    """Print application banner."""
    banner = """
    ==============================================================
      ACU - AGENTE COGNITIVO UNIVERSAL v1.0
      Autonomous Reasoning + Acting Orchestrator
      Stack: Python | Ollama | MySQL | Local Docs Search
      Pattern: ReAct (Reason + Act)
    ==============================================================
    """
    print(banner)


if __name__ == "__main__":
    print_banner()

    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        exit_code = asyncio.run(demo_mode())
    else:
        exit_code = asyncio.run(main())

    sys.exit(exit_code)
