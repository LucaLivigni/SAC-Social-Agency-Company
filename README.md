# SAC Studio

SAC Studio è un workspace locale per gestire un team di agenti AI dedicati al marketing di uno o più prodotti.

## Primo utilizzo

1. **Connect AI** — collega OpenAI e/o Anthropic.
2. **Connect GitHub** — collega la piattaforma a GitHub con un fine-grained token read-only.
3. **Choose a product repo** — SAC analizza codice e documentazione.
4. **Product discovery** — rispondi solo alle domande che il codice non può risolvere.
5. **Create campaign** — osserva gli agenti lavorare e ottieni piano, post, review e visual.

GitHub è collegato alla **piattaforma**, non ai modelli. Gli agenti usano un tool server-side; il token GitHub non entra mai nei prompt.

## Installazione macOS

```bash
git clone https://github.com/LucaLivigni/SAC-Social-Agency-Company.git
cd SAC-Social-Agency-Company
chmod +x setup_mac.sh run_mac.sh
./setup_mac.sh
./run_mac.sh
```

Apri `http://127.0.0.1:8000`.

## Aggiornamenti

Dopo il primo clone:

```bash
git pull
./run_mac.sh
```

Se cambiano le dipendenze:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

## GitHub

Dalla UI: **Connections → GitHub → Configure**.

Usa un fine-grained personal access token limitato alle sole repository che vuoi rendere leggibili a SAC e con **Contents: Read-only**. Il token viene salvato nel Keychain di macOS.

## Modelli

Provider inclusi:
- OpenAI
- Anthropic
- endpoint OpenAI-compatible, utile per Ollama, LM Studio, vLLM o gateway compatibili

Ogni agente può usare un model profile diverso.

## Sicurezza

- `.env` non viene committato.
- GitHub token e API key inserite dalla UI vengono salvati nel Keychain di macOS quando disponibile.
- Il token GitHub non viene passato ai modelli.
- L'analisi repository ignora file sensibili, build e dipendenze e limita la quantità di contenuto letta.
- La pubblicazione social è manuale in questa versione.
