import os
import socket
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, List

import psutil
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("disk-monitor-server")


class DiskInfo(BaseModel):
    device: str
    mountpoint: str
    fstype: str
    total_gb: float
    used_gb: float
    free_gb: float
    percent_used: float


class HostPayload(BaseModel):
    hostname: str
    ip: str
    os: str
    timestamp: str
    disks: List[DiskInfo]


# Inventário em memória indexado por hostname
inventory: Dict[str, dict] = {}
MONITOR_INTERVAL = int(os.getenv("MONITOR_INTERVAL", "60"))


def get_local_server_disks() -> List[DiskInfo]:
    """Coleta métricas das partições locais da máquina receptora."""
    disks = []
    for p in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(p.mountpoint)
            disks.append(
                DiskInfo(
                    device=p.device,
                    mountpoint=p.mountpoint,
                    fstype=p.fstype,
                    total_gb=round(usage.total / (1024**3), 2),
                    used_gb=round(usage.used / (1024**3), 2),
                    free_gb=round(usage.free / (1024**3), 2),
                    percent_used=usage.percent,
                )
            )
        except (PermissionError, OSError):
            continue
    return disks


def get_local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


async def auto_monitor_server_disks():
    """Tarefa assíncrona em background que monitora o próprio servidor central."""
    hostname = f"{socket.gethostname()} (Servidor Central)"
    local_ip = get_local_ip()
    os_name = "Linux" if os.name == "posix" else "Windows"

    while True:
        try:
            payload = HostPayload(
                hostname=hostname,
                ip=local_ip,
                os=os_name,
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                disks=get_local_server_disks(),
            )
            inventory[hostname] = payload.model_dump()
            logger.info(f"[Local] Discos do servidor central atualizados ({len(payload.disks)} partições).")
        except Exception as e:
            logger.error(f"[Local] Erro ao coletar discos locais: {e}")

        await asyncio.sleep(MONITOR_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(auto_monitor_server_disks())
    yield
    task.cancel()


app = FastAPI(
    title="Central Disk Telemetry API",
    description="API centralizada para ingestão e consulta de métricas de armazenamento multiplataforma.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.post("/api/report", status_code=201)
def receive_report(payload: HostPayload):
    """Recebe e registra relatórios enviados pelos agentes remotos."""
    inventory[payload.hostname] = payload.model_dump()
    logger.info(f"[Remoto] Telemetria recebida de {payload.hostname} ({payload.ip}) [{payload.os}]")
    return {"status": "success", "message": "Relatório registrado"}


@app.get("/api/hosts", response_model=List[HostPayload])
def list_hosts():
    """Retorna o inventário consolidado de todos os hosts monitorados."""
    return list(inventory.values())


@app.get("/api/hosts/{hostname}", response_model=HostPayload)
def get_host(hostname: str):
    """Busca as métricas de um host específico pelo hostname."""
    host = inventory.get(hostname)
    if not host:
        raise HTTPException(status_code=404, detail="Máquina não encontrada no inventário")
    return host


if __name__ == "__main__":
    host = os.getenv("SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("SERVER_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)