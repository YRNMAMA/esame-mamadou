# BUGS.md — Registro dei bug

| ID | Issue | Trovato da | Tipo | Requisito | Causa radice | Test di regressione | Commit |
|---|---|---|---|---|---|---|---|
| BUG-01 | #1 | test manuale | impl | REQ-REG-B07 | Il metodo `update_status` del MemoryRepository non aggiornava `updated_at` quando il timestamp del record era uguale all'ora corrente nel test | `TestMemoryRepository::test_update_status` | da aggiungere |
| BUG-02 | #2 | test manuale | impl | REQ-USR-B01 | La validazione dell'unicità dell'email nella PUT non controllava l'ID corrente, causando un falso 409 quando si aggiornava l'email dello stesso utente con la stessa email | `TestRoutes::test_put_user_success` | da aggiungere |
