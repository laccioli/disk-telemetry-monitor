# 🖥️ Central Disk Telemetry Monitor

Sistema distribuído de monitoramento e inventário de armazenamento em tempo real, projetado sob arquitetura **Agente-Servidor (Push Model)** para ambientes heterogêneos (**Linux** e **Windows**).

O projeto elimina a necessidade de acesso remoto manual (SSH/RDP) para auditoria de capacidade em múltiplos servidores e estações de trabalho, consolidando métricas de partições e uso de disco em uma API REST centralizada.

---

## 🏗️ Arquitetura e Fluxo de Dados

```text
+-----------------------+          POST /api/report          +-------------------------+
|   Agente (Windows)    | ---------------------------------> |                         |
+-----------------------+            (JSON / HTTP)           |    Servidor Central     |
                                                             |     (FastAPI + Async)   |
+-----------------------+          POST /api/report          |                         |
|    Agente (Linux)     | ---------------------------------> |  +-------------------+  |
+-----------------------+            (JSON / HTTP)           |  | Self-Monitor Task |  |
                                                             |  +-------------------+  |
+-----------------------+          GET /api/hosts            |                         |
|  Dashboard / Cliente  | <--------------------------------- |  [Inventário em RAM]    |
+-----------------------+                                    +-------------------------+
```

### Destaques Técnicos
* **Agente Leve e Multiplataforma (`agent.py`):** Coleta informações reais de partições físicas (`device`, `mountpoint`, `fstype`, capacidade total, usada, livre e percentual) utilizando `psutil`, ignorando pontos de montagem virtuais ou inacessíveis sem interromper o ciclo.
* **Auto-Monitoramento Assíncrono (`server.py`):** O servidor central executa uma rotina não-bloqueante em background (`asyncio` via `lifespan`) para auditar os seus próprios discos simultaneamente ao recebimento de telemetria externa.
* **Validação Estrita de Contratos:** Uso de **Pydantic v2** para garantir a integridade dos payloads recebidos e gerar documentação interativa automática via OpenAPI/Swagger.
* **Configuração via Variáveis de Ambiente:** Totalmente desacoplado de endereços de rede fixos, pronto para implantação via systemd, serviços Windows ou contêineres.

---

## 🛠️ Stack Tecnológica

* **Linguagem:** Python 3.11+
* **Back-end & API:** FastAPI, Uvicorn, Pydantic
* **Coleta de Sistema:** psutil
* **Comunicação HTTP:** Requests

---

## 🚀 Como Executar

### 1. Clonar o repositório
```bash
git clone https://github.com/laccioli/disk-telemetry-monitor.git
cd disk-telemetry-monitor
```

### 2. Iniciar o Servidor Central
```bash
cd server
pip install -r requirements.txt

# Opcional: definir porta customizada (padrão: 8000)
export SERVER_PORT=8000

python server.py
```
A documentação interativa da API (Swagger UI) estará disponível em `http://localhost:8000/docs`.

### 3. Iniciar o Agente nas Máquinas Monitoradas
```bash
cd agent
pip install -r requirements.txt

# Configurar o endereço do servidor central e o intervalo de envio (em segundos)
export MONITOR_SERVER_URL="http://IP_DO_SERVIDOR:8000/api/report"
export MONITOR_INTERVAL=60

python agent.py
```

---

## 📡 Endpoints da API

| Método | Rota | Descrição |
| :--- | :--- | :--- |
| `POST` | `/api/report` | Recebe o payload JSON de telemetria de um agente e atualiza o inventário. |
| `GET` | `/api/hosts` | Retorna a lista consolidada de todos os hosts ativos e seus respectivos discos. |
| `GET` | `/api/hosts/{hostname}` | Retorna os detalhes de armazenamento de um host específico. |

### Exemplo de Payload (`POST /api/report`)
```json
{
  "hostname": "SRV-LINUX-01",
  "ip": "192.168.1.50",
  "os": "Linux",
  "timestamp": "2026-11-12 23:45:00",
  "disks": [
    {
      "device": "/dev/sda1",
      "mountpoint": "/",
      "fstype": "ext4",
      "total_gb": 250.0,
      "used_gb": 112.45,
      "free_gb": 137.55,
      "percent_used": 44.98
    }
  ]
}
```

---

## 🗺️ Roadmap de Evolução

* [ ] Persistência histórica em banco de dados (SQLite / PostgreSQL) para análise de crescimento de disco.
* [ ] Autenticação via `API Key` no header das requisições dos agentes.
* [ ] Sistema de alertas (Webhook Discord/Telegram) quando `percent_used` ultrapassar 85%.
* [ ] Interface Web (Front-end) consumindo `GET /api/hosts` com barras de progresso e status online/offline baseado no último `timestamp`.