# Changelog

## 1.0.0 — 2026-11-07

Prima versione utilizzabile di SAC Studio.

### Added
- Dashboard con onboarding guidato e next action.
- Agent Floor con stato, task corrente, modello e avanzamento.
- GitHub collegato alla piattaforma tramite fine-grained token read-only.
- Product Analyst che analizza repository private senza passare credenziali ai modelli.
- Discovery conversazionale dopo l'analisi del codice.
- Model Hub con OpenAI, Anthropic e provider OpenAI-compatible.
- Routing modello per singolo agente.
- Campaign workflow: Strategist → Planner → specialisti social → Revy → Creative.
- Calendario editoriale e pacchetto READY TO PUBLISH.
- Credenziali salvate nel macOS Keychain quando disponibile.
- Setup e avvio macOS tramite script.

### Safety / boundaries
- Nessuna pubblicazione social automatica in v1.0.0.
- Repository access in sola lettura.
- File sensibili e dipendenze esclusi dall'analisi repository.
