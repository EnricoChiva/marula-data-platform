# 🌱 Marula Data Platform

Die **Marula Data Platform** ist mein persönliches Lern- und Entwicklungsprojekt rund um **Data Engineering**, **Self-Hosting** und **moderne Datenplattformen**.

Das Ziel ist es, eine Datenplattform **Schritt für Schritt** aufzubauen – nicht als fertiges Produkt, sondern als nachvollziehbare Reise. Jede neue Komponente wird bewusst eingeführt, dokumentiert und in die bestehende Architektur integriert.

Dieses Repository dient gleichzeitig als:

* 📚 Lernprojekt
* 🛠 Technisches Portfolio
* 📝 Dokumentation meiner Fortschritte
* 💡 Grundlage für technische Blog- und LinkedIn-Beiträge

---

# 🎯 Ziele

* Eine moderne Data Platform auf einem eigenen VPS aufbauen
* Data-Engineering-Konzepte praktisch verstehen
* Open-Source-Technologien sinnvoll kombinieren
* Best Practices für Infrastruktur, ETL und Datenmodellierung anwenden
* Erfahrungen transparent dokumentieren

---

# 🚀 Geplante Technologien

Die Plattform wächst schrittweise und wird im Laufe der Zeit unter anderem folgende Technologien integrieren:

* Docker
* Dokploy
* PostgreSQL
* MinIO
* Python
* Polars
* Apache Superset
* n8n
* DuckDB
* dbt
* FastAPI
* MCP Server

Nicht alle Komponenten sind von Anfang an vorhanden – sie werden im Projektverlauf ergänzt.

---

# 🗺 Roadmap

## Version 1

* Repository aufsetzen
* PostgreSQL deployen
* MinIO deployen
* Erste ETL-Pipeline entwickeln
* Daten aus einer öffentlichen API abrufen
* Rohdaten im Data Lake speichern
* Daten transformieren
* Daten in PostgreSQL laden

Weitere Ausbaustufen folgen.

---

# 💻 Lokale Entwicklungsumgebung

PostgreSQL und MinIO laufen lokal in Docker-Containern. Die verwendeten
Hauptversionen entsprechen der Umgebung auf OVHCloud, während Daten und
Zugangsdaten vollständig von der Serverumgebung getrennt bleiben.

## Voraussetzungen

* Docker Desktop mit Docker Compose

## Erster Start

```bash
cp .env.local.example .env.local
docker compose up -d
docker compose ps
```

Nach erfolgreichem Start sind die Dienste ausschließlich lokal erreichbar:

* PostgreSQL: `localhost:5433` (Container-intern weiterhin `5432`)
* MinIO S3 API: `http://localhost:9000`
* MinIO Console: `http://localhost:9001`

Beim Start wird der lokale Bucket `marula-raw` automatisch angelegt. Der
zugehörige `minio-init`-Container beendet sich danach erfolgreich; der Status
`Exited (0)` ist für diesen einmaligen Initialisierungsschritt normal.

Die Zugangsdaten stehen in der lokalen `.env.local`. Diese Datei wird nicht in
Git eingecheckt. Die eingecheckte `.env.local.example` enthält ausschließlich
ungefährliche Entwicklungswerte.

## Stoppen und erneut starten

```bash
docker compose stop
docker compose start
```

`stop` behält die lokalen Daten in Docker-Volumes. Um die Container zu
entfernen und später mit denselben Daten neu zu erstellen:

```bash
docker compose down
```

> **Achtung:** `docker compose down --volumes` löscht zusätzlich alle lokalen
> PostgreSQL- und MinIO-Daten.

---

# 🐍 Python-Entwicklungsumgebung

Die Pipeline ist als installierbare Python-Anwendung mit `src`-Layout
aufgebaut. `uv` verwaltet die Python-Version, Abhängigkeiten, virtuelle
Umgebung und das Lockfile.

## Voraussetzungen

```bash
brew install uv
```

## Umgebung einrichten

```bash
uv sync
```

`uv sync` installiert bei Bedarf die festgelegte Python-Version, erzeugt die
lokale `.venv` und installiert exakt die in `uv.lock` aufgelösten
Abhängigkeiten. Eine manuelle Aktivierung ist für den normalen Workflow nicht
nötig.

## Anwendung und Qualitätschecks ausführen

```bash
uv run marula-pipeline
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Wer die virtuelle Umgebung explizit aktivieren möchte, kann weiterhin den
klassischen Weg verwenden:

```bash
source .venv/bin/activate
```

---

# 📖 Projektphilosophie

Anstatt sofort eine komplexe Enterprise-Architektur aufzubauen, entsteht die Plattform iterativ.

Jede Erweiterung soll:

* ein konkretes Problem lösen,
* einen neuen technischen Aspekt vermitteln,
* nachvollziehbar dokumentiert werden und
* die bestehende Plattform sinnvoll erweitern.

So entsteht über die Zeit eine vollständige, praxisnahe Data Platform.

---

# 📄 Lizenz

Dieses Projekt befindet sich aktuell im Aufbau. Eine Lizenz wird zu einem späteren Zeitpunkt ergänzt.
