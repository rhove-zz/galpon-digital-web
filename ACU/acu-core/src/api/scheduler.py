"""
Background scheduler module for maintenance tasks like data pruning.
"""

import asyncio
import signal
from typing import Literal

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.config.settings import system_config
from src.memory.mysql_manager import MySQLConnector
from src.utils.logger import log

scheduler = AsyncIOScheduler()
SchedulerContext = Literal["api", "worker"]
VALID_SCHEDULER_MODES = {"disabled", "api", "worker", "all"}


def run_pruning_jobs():
    """
    Execute pruning logic for audit logs, sessions and conversation context.
    This job runs in a separate background context.
    """
    audit_retention_days = system_config.audit_retention_days
    conversation_retention_days = system_config.conversation_retention_days
    log.info(
        "Iniciando rutina de poda (pruning): "
        f"auditoria={audit_retention_days} dias, "
        f"conversaciones={conversation_retention_days} dias..."
    )

    db_connector = MySQLConnector(use_read_only=False)
    if not db_connector.connect():
        log.error("Fallo la conexion a la BD durante la rutina de poda de logs.")
        return

    try:
        res_tool = db_connector.prune_tool_execution_log(
            older_than_days=audit_retention_days
        )
        if not res_tool.get("success"):
            log.warning(
                f"Advertencia al purgar tool_execution_log: {res_tool.get('error')}"
            )

        res_api = db_connector.prune_api_access_log(
            older_than_days=audit_retention_days
        )
        if not res_api.get("success"):
            log.warning(f"Advertencia al purgar api_access_log: {res_api.get('error')}")

        res_context = db_connector.prune_conversation_context(
            older_than_days=conversation_retention_days
        )
        if not res_context.get("success"):
            log.warning(
                f"Advertencia al purgar conversation_context: "
                f"{res_context.get('error')}"
            )

        res_sessions = db_connector.prune_agent_sessions(
            older_than_days=conversation_retention_days
        )
        if not res_sessions.get("success"):
            log.warning(
                f"Advertencia al purgar agent_sessions: {res_sessions.get('error')}"
            )

        log.info("Rutina de poda finalizada.")
    finally:
        db_connector.disconnect()


def run_braincore_sync_job():
    """
    Monitorea carpetas locales y sincroniza el BrainCore automaticamente.
    """
    paths_str = system_config.braincore_sync_paths.strip()
    if not paths_str:
        return

    log.info("Iniciando rutina de sincronizacion de BrainCore...")
    paths = [p.strip() for p in paths_str.split(",") if p.strip()]

    from src.braincore.manager import get_braincore_manager

    manager = get_braincore_manager()

    for path in paths:
        log.info(f"Sincronizando ruta en BrainCore: {path}")
        result = manager.ingest_path(
            path=path, source_type="auto", domain="daemon_sync"
        )
        if result.get("success"):
            data = result.get("data", {})
            log.info(
                f"BrainCore Sync Exitoso ({path}): "
                f"{data.get('sources_indexed')} archivos, "
                f"{data.get('chunks_indexed')} chunks."
            )
        else:
            log.warning(f"Error sincronizando {path}: {result.get('error')}")


def scheduler_should_start(context: SchedulerContext) -> bool:
    """Return whether the scheduler should start in the given runtime context."""
    mode = system_config.scheduler_mode.strip().lower()
    if mode not in VALID_SCHEDULER_MODES:
        log.warning(
            f"ACU_SCHEDULER_MODE invalido: {system_config.scheduler_mode}. "
            "Usando modo disabled."
        )
        return False
    return mode == "all" or mode == context


def start_scheduler(context: SchedulerContext = "api") -> bool:
    """Configure and start the background scheduler when enabled for context."""
    if not scheduler_should_start(context):
        log.info(
            f"Scheduler no iniciado en contexto '{context}' "
            f"(ACU_SCHEDULER_MODE={system_config.scheduler_mode})."
        )
        return False

    if scheduler.running:
        log.info("Scheduler ya estaba iniciado; no se duplican jobs.")
        return True

    scheduler.add_job(
        run_pruning_jobs,
        CronTrigger(hour=3, minute=0),
        id="prune_logs_job",
        replace_existing=True,
    )
    scheduler.add_job(
        run_braincore_sync_job,
        CronTrigger(hour="0,6,12,18", minute=0),
        id="braincore_sync_job",
        replace_existing=True,
    )

    scheduler.start()
    log.info(f"Scheduler de rutinas asincronas iniciado en contexto '{context}'.")
    return True


def shutdown_scheduler():
    """Stop the background scheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        log.info("Scheduler detenido.")


def get_scheduler_status() -> dict:
    """Return scheduler runtime status for monitoring endpoints."""
    mode = system_config.scheduler_mode.strip().lower()
    jobs = scheduler.get_jobs() if scheduler.running else []
    return {
        "mode": mode,
        "valid_mode": mode in VALID_SCHEDULER_MODES,
        "running": bool(scheduler.running),
        "jobs_count": len(jobs),
        "jobs": [job.id for job in jobs],
    }


async def run_scheduler_worker() -> None:
    """Run the scheduler as a dedicated long-lived worker process."""
    started = start_scheduler(context="worker")
    if not started:
        log.warning("Scheduler worker finalizado porque no esta habilitado.")
        return

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass

    try:
        await stop_event.wait()
    finally:
        shutdown_scheduler()


def main() -> None:
    """CLI entrypoint: python -m src.api.scheduler."""
    asyncio.run(run_scheduler_worker())


if __name__ == "__main__":
    main()
