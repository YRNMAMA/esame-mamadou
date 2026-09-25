# TechConf — Microservizi per la gestione delle iscrizioni a conferenze tech

Progetto esame: implementazione spec-driven (Requirements-First) con Kiro IDE.

## Servizi implementati

| Servizio | Porta | Stato |
|---|---|---|
| user-service | 5001 | ✅ Obbligatorio |
| event-service | 5002 | ✅ Obbligatorio |
| registration-service | 5003 | ✅ Obbligatorio |

## Avvio dei servizi

```bash
# Installa le dipendenze
python3 -m pip install -e services/common
python3 -m pip install -e services/user-service
python3 -m pip install -e services/event-service
python3 -m pip install -e services/registration-service

# Avvia singolo servizio (esempio)
cd services/user-service && PORT=5001 python3 -m user_service
cd services/event-service && PORT=5002 USER_SERVICE_URL=http://localhost:5001 python3 -m event_service
cd services/registration-service && PORT=5003 USER_SERVICE_URL=http://localhost:5001 EVENT_SERVICE_URL=http://localhost:5002 python3 -m registration_service
```

## Variabili d'ambiente

| Variabile | Default | Descrizione |
|---|---|---|
| `PORT` | 5001/5002/5003 | Porta di ascolto del servizio |
| `STORAGE_BACKEND` | `memory` | Backend di persistenza: `memory`, `json`, `sqlite` |
| `DATA_DIR` | `./data` | Directory per i file json/sqlite |
| `USER_SERVICE_URL` | `http://localhost:5001` | URL del user-service |
| `EVENT_SERVICE_URL` | `http://localhost:5002` | URL dell'event-service |
| `REGISTRATION_SERVICE_URL` | `http://localhost:5003` | URL del registration-service |

## Esecuzione dei test

```bash
# Test unitari per servizio
python3 -m pytest services/user-service/tests/ -v
python3 -m pytest services/event-service/tests/ --ignore=services/event-service/tests/test_integration.py -v
python3 -m pytest services/registration-service/tests/ --ignore=services/registration-service/tests/test_integration.py --ignore=services/registration-service/tests/test_integration_resilience.py -v

# Test unitari con coverage
python3 -m pytest services/user-service/tests/ --cov=user_service --cov-report=term
python3 -m pytest services/event-service/tests/ --ignore=services/event-service/tests/test_integration.py --cov=event_service --cov-report=term
python3 -m pytest services/registration-service/tests/ --ignore=services/registration-service/tests/test_integration.py --ignore=services/registration-service/tests/test_integration_resilience.py --cov=registration_service --cov-report=term

# Integration test propri (avviano servizi reali)
python3 -m pytest services/event-service/tests/test_integration.py -v
python3 -m pytest services/registration-service/tests/test_integration.py -v
python3 -m pytest services/registration-service/tests/test_integration_resilience.py -v

# Suite di collaudo del docente
pip install -r tests/integration/requirements.txt
pytest tests/integration -m mandatory -v
```

## Verifica integrità file protetti

```bash
sha256sum -c CHECKSUMS.sha256
```

## Struttura del progetto

```
techconf-exam/
├── contracts/          # Contratti OpenAPI (NON MODIFICARE)
├── tests/integration/  # Suite collaudo docente (NON MODIFICARE)
├── services/
│   ├── common/         # Libreria condivisa (techconf_common)
│   ├── user-service/
│   ├── event-service/
│   └── registration-service/
├── .kiro/
│   ├── steering/       # Regole globali per Kiro
│   ├── specs/          # Specifiche dei servizi
│   └── hooks/          # Agent hooks
├── services.yaml       # Manifest per la suite di collaudo
└── BUGS.md             # Registro dei bug
```
