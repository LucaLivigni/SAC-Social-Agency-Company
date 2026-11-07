# SAC Studio v2

SAC Studio è un **AI marketing department** locale: tu parli principalmente con un Chief Marketing AI, che conosce il prodotto, progetta il team di specialisti, assegna il lavoro, coordina gli agenti e ti coinvolge solo quando servono informazioni, accessi o decisioni.

## Flusso
1. Connect AI
2. Connect GitHub (opzionale per prodotti non software)
3. Add product: software, hardware o hybrid
4. Product discovery conversazionale
5. Chief propone il team
6. Build team
7. Talk to Chief / Create campaign
8. Guarda gli agenti lavorare e comunicare
9. Scarica READY TO PUBLISH

## Novità v2
- Chief Agent come unico interlocutore principale
- Agent Builder dinamico
- Agent Manifest: missione, prompt, tools, permessi, KPI, memory scope, escalation
- Model routing per agente: OpenAI, Anthropic o OpenAI-compatible/local
- Shared + private memory
- Inter-agent communication log visibile
- Needs You: richieste di accesso, API, decisioni e approvazioni
- Product onboarding software + hardware
- Team proposal generata dal Chief
- Permission layer per GitHub, Instagram, LinkedIn, X, image/video generation
- Revy come quality gate indipendente

## Installazione / aggiornamento macOS

Prima installazione:

```bash
git clone https://github.com/LucaLivigni/SAC-Social-Agency-Company.git
cd SAC-Social-Agency-Company
chmod +x setup_mac.sh run_mac.sh
./setup_mac.sh
./run_mac.sh
```

Aggiornamento:

```bash
cd /Users/lucagiannilivigni/Progetti/Marketing/SAC-Social-Agency-Company
git pull
./setup_mac.sh
./run_mac.sh
```

Apri `http://127.0.0.1:8000`.

## GitHub
Connections → GitHub. Usa un fine-grained PAT con Contents: Read-only e limita l'accesso alle sole repo desiderate. Il token viene salvato nel macOS Keychain quando disponibile e non viene passato ai modelli.

## Social connections
La v2 include permission/access-request layer per Instagram, LinkedIn e X. La UI non finge che un social sia collegato senza una vera autorizzazione OAuth/API. Gli agenti possono già dichiarare i tool necessari e generare richieste Needs You; i connector social reali vanno autorizzati con le rispettive app/API.

## Sicurezza
- Secrets in Keychain / fallback locale protetto
- `.env` e database esclusi dal repository
- GitHub read-only
- Repository scanner esclude segreti, build e dipendenze
- Gli agenti non ricevono token GitHub
- Publishing social non automatico finché non viene concesso esplicitamente
