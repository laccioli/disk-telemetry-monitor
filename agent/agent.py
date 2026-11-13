import os
import socket
import time
import logging
from datetime import datetime
from typing import Dict, Any

import psutil
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("disk-monitor-agent")

SERVER_URL = os.getenv("MONITOR_SERVER_URL", "http://localhost:8000/api/report")
INTERVALO_SEGUNDOS = int(os.getenv("MONITOR_INTERVAL", "60"))


def get_local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def coletar_metricas() -> Dict[str, Any]:
    disks = []
    for p in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(p.mountpoint)
            disks.append(
                {
                    "device": p.device,
                    "mountpoint": p.mountpoint,
                    "fstype": p.fstype,
                    "total_gb": round(usage.total / (1024**3), 2),
                    "used_gb": round(usage.used / (1024**3), 2),
                    "free_gb": round(usage.free / (1024**3), 2),
                    "percent_used": usage.percent,
                }
            )
        except (PermissionError, OSError):
            continue

    return {
        "hostname": socket.gethostname(),
        "ip": get_local_ip(),
        "os": "Linux" if os.name == "posix" else "Windows",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "disks": disks,
    }


def enviar_relatorio():
    payload = coletar_metricas()
    try:
        response = requests.post(SERVER_URL, json=payload, timeout=10)
        if response.status_code in (200, 201):
            logger.info(f"Relatório enviado com sucesso ({len(payload['disks'])} partições).")
        else:
            logger.warning(f"Servidor respondeu com erro ({response.status_code}): {response.text}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Falha na conexão com {SERVER_URL}: {e}")


def main():
    logger.info(f"Agente iniciado. Alvo: {SERVER_URL} | Intervalo: {INTERVALO_SEGUNDOS}s")
    while True:
        try:
            enviar_relatorio()
        except Exception as e:
            logger.error(f"Erro inesperado durante o ciclo de coleta: {e}")

        time.sleep(INTERVALO_SEGUNDOS)


if __name__ == "__main__":
    main()