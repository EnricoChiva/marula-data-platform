# MinIO-Storage und Datenobjekte der Raw-Ingestion

Diese Notiz erklärt, wie `storage/minio.py` arbeitet und welche Rollen
`ExtractedResponse`, `IngestionResult`, `RawSnapshot`, Pydantic und ein späterer
Polars-DataFrame im Datenfluss spielen.

## Was passiert in `storage/minio.py`?

`MinioStorage` ist ein technischer Adapter zwischen der Marula-Pipeline und dem
offiziellen MinIO-Python-SDK.

Die Pipeline möchte nur eine einfache Operation verwenden:

```python
storage.put_json(
    object_name=object_name,
    content=response.content,
    metadata=metadata,
)
```

Das MinIO-SDK benötigt dafür mehrere technische Angaben. Der Adapter übersetzt
den einfachen Aufruf der Pipeline in den konkreten SDK-Aufruf.

```text
Pipeline: put_json(...)
          ↓
MinioStorage-Adapter
          ↓
MinIO-Python-SDK: put_object(...)
          ↓
MinIO-Server
```

### Erzeugung des MinIO-Clients

Im Konstruktor wird entweder ein übergebener Client verwendet oder ein echter
MinIO-Client erzeugt:

```python
self._client = client or Minio(
    endpoint=endpoint,
    access_key=access_key,
    secret_key=secret_key,
    secure=secure,
)
```

Die Parameter beschreiben:

- `endpoint`: Adresse des MinIO-Servers,
- `access_key`: Benutzerkennung,
- `secret_key`: geheimes Zugangsmittel,
- `secure`: Verwendung von HTTPS statt HTTP.

Die Zugangsdaten kommen aus der Konfiguration und dürfen niemals fest im Code
oder im Git-Repository stehen.

### Der Bucket

Ein Bucket ist der oberste logische Speicherbereich in MinIO. Für die
unveränderten Quelldaten verwendet Marula aktuell den Bucket `marula-raw`.

Die Property

```python
@property
def bucket(self) -> str:
    return self._bucket
```

erlaubt der Pipeline, den konfigurierten Namen zu lesen, ohne die internen
Attribute des Adapters zu kennen.

### Speichern mit `put_json`

Vor dem Schreiben prüft der Adapter, ob der konfigurierte Bucket existiert:

```python
if not self._client.bucket_exists(self._bucket):
    raise BucketNotFoundError(...)
```

Der Bucket wird absichtlich nicht stillschweigend durch die Pipeline angelegt.
Seine Anlage gehört zur Infrastruktur und erfolgt idempotent über
`minio-init` in Docker Compose. Ein fehlender Bucket weist daher auf eine falsch
oder unvollständig gestartete Infrastruktur hin.

Der eigentliche Upload geschieht anschließend über das MinIO-SDK:

```python
self._client.put_object(
    bucket_name=self._bucket,
    object_name=object_name,
    data=BytesIO(content),
    length=len(content),
    content_type="application/json",
    metadata=dict(metadata or {}),
)
```

Die Argumente bedeuten:

| Argument | Bedeutung |
|---|---|
| `bucket_name` | Bucket, in dem gespeichert wird |
| `object_name` | vollständiger Schlüssel beziehungsweise Pfad des Objekts |
| `data` | zu speichernder Inhalt als dateiähnlicher Datenstrom |
| `length` | Anzahl der zu übertragenden Bytes |
| `content_type` | Kennzeichnung des Inhalts als JSON |
| `metadata` | zusätzliche technische Informationen zum Objekt |

`response.content` enthält bereits Bytes. `BytesIO(content)` verpackt diese
Bytes lediglich in einen dateiähnlichen Stream, weil `put_object` einen solchen
Stream erwartet. Der JSON-Inhalt wird dabei nicht verändert.

Ein MinIO-Objekt besteht gedanklich aus:

```text
MinIO-Objekt
├── Bucket: marula-raw
├── Object Name: energy-charts/public-power/country=de/...
├── Inhalt: unveränderte JSON-Bytes
└── Metadaten: Quelle, Lizenz, Request-URL und weitere Lineage
```

## Warum existiert zusätzlich `RawStorage`?

`RawStorage` ist keine Implementierung und kein Framework. Es ist ein
`typing.Protocol` aus der Python-Standardbibliothek. Es beschreibt nur, welche
Fähigkeiten ein Speicher für diese Pipeline anbieten muss:

```python
class RawStorage(Protocol):
    @property
    def bucket(self) -> str: ...

    def put_json(
        self,
        object_name: str,
        content: bytes,
        metadata: dict[str, str] | None = None,
    ) -> None: ...
```

Die Pipeline kennt dadurch nicht die technischen Details von MinIO. Jede
konkrete Klasse, die `bucket` und eine passende `put_json`-Methode besitzt, kann
verwendet werden.

Im produktiven Lauf ist das `MinioStorage`. Im Test kann es ein kleiner
`FakeStorage` sein, der die übergebenen Werte nur im Arbeitsspeicher festhält.
So lässt sich die fachliche Pipeline ohne Docker, Netzwerk oder echte
Zugangsdaten testen.

Dieses Muster ist eine einfache Form von Dependency Injection: Die Pipeline
erzeugt ihre technischen Abhängigkeiten nicht selbst, sondern bekommt sie von
der CLI übergeben.

## Ist `put_json` eine Blaupause für ein Objekt?

Nein. `put_json` beschreibt eine Aktion:

> Speichere diese Bytes unter diesem Objektnamen und füge diese Metadaten hinzu.

Das `RawStorage`-Protocol beschreibt den Vertrag dieser Aktion. Die konkrete
technische Durchführung befindet sich in `MinioStorage.put_json`.

Der Begriff „Objekt“ hat hier außerdem zwei Bedeutungen:

- Ein Python-Objekt ist zur Laufzeit eine Instanz einer Python-Klasse.
- Ein MinIO-Objekt ist ein gespeicherter Blob aus Bytes mit Schlüssel und
  Metadaten.

Ein MinIO-Objekt muss deshalb kein Pydantic-Modell und keine Python-Klasse sein.

## Wann verwenden wir `dataclass`, Pydantic und Polars?

Nicht jeder Datencontainer benötigt Pydantic. Die drei Werkzeuge lösen
unterschiedliche Probleme:

| Werkzeug | Aufgabe im Projekt |
|---|---|
| `dataclass` | kleine interne, klar typisierte Transport- und Ergebnisobjekte |
| Pydantic | externe, potenziell ungültige JSON-Strukturen validieren |
| Polars | validierte Daten tabellarisch transformieren |

Eine Faustregel für Marula lautet:

```text
interner Rückgabewert              → dataclass
externe, nicht vertrauenswürdige Daten → Pydantic
tabellarische Transformation       → Polars DataFrame
```

Pydantic prüft, ob die Raw-Antwort der Energy-Charts-API die benötigten Felder,
Datentypen und Strukturen besitzt. Es ersetzt nicht pauschal jede kleine interne
Klasse.

Für den Public-Power-Transformationsvertrag wurde bewusst festgelegt, zunächst
nur `schema_version = "2.0"` zu akzeptieren. Eine andere Version wird abgelehnt,
bis ihre Struktur geprüft und explizit unterstützt wurde. So führen Änderungen
am Quellvertrag nicht unbemerkt zu fachlich falschen Daten.

## `ExtractedResponse`: abgeholte Daten mit Abrufkontext

Die API liefert JSON über HTTP. Der unveränderte HTTP-Body liegt als Bytes vor:

```python
@dataclass(frozen=True, slots=True)
class ExtractedResponse:
    content: bytes
    request_url: str
    extracted_at: datetime
```

Die Felder bedeuten:

- `content`: unveränderte JSON-Antwort als Bytes,
- `request_url`: die tatsächlich aufgerufene URL,
- `extracted_at`: Zeitpunkt des Abrufs in UTC.

Der API-Client parst die Antwort momentan einmal kurz mit `response.json()`, um
die grundlegend erwartete Struktur zu prüfen. Gespeichert wird trotzdem
`response.content`, damit die Raw-Schicht die ursprüngliche Darstellung erhält.

## `IngestionResult`: Quittung statt Nutzdaten

Nach dem erfolgreichen Speichern liefert die Pipeline ein kleines Ergebnis
zurück:

```python
@dataclass(frozen=True, slots=True)
class IngestionResult:
    bucket: str
    object_name: str
    extracted_at: datetime
```

`IngestionResult` enthält nicht die Daten, die nach MinIO geschrieben werden.
Es ist eine Quittung über den bereits erfolgten Schreibvorgang:

```text
Paketinhalt        → response.content
Versanddienst      → MinioStorage
Ablageort          → bucket und object_name
Einlieferungsbeleg → IngestionResult
```

Die CLI verwendet diese Quittung beispielsweise für folgende Ausgabe:

```text
Stored raw response at s3://marula-raw/energy-charts/public-power/...
```

## Warum ist `IngestionResult` kein DataFrame?

Die Raw-Ingestion soll die Quelldaten lediglich abrufen, unverändert speichern
und den Speicherort zurückmelden. Sie interpretiert die Messwerte noch nicht.

Ein DataFrame wird erst in der Transformation benötigt:

```text
Raw JSON-Bytes
      ↓
Pydantic-Validierung
      ↓
Polars-Transformation
      ↓
Polars DataFrame im Long-Format
      ↓
PostgreSQL
```

Ein DataFrame innerhalb der Raw-Ingestion würde die Grenzen vermischen und die
Gefahr erhöhen, dass die Originalantwort bereits vor dem Speichern verändert
wird.

## `RawSnapshot`: zukünftige Eingabe der Transformation

`RawSnapshot` bündelt Raw-Inhalt und Lineage für die Transformation:

```python
@dataclass(frozen=True, slots=True)
class RawSnapshot:
    content: bytes
    object_name: str
    extracted_at: datetime
```

Die Felder bedeuten:

- `content`: aus MinIO gelesene JSON-Bytes,
- `object_name`: exakter MinIO-Schlüssel als Herkunftsnachweis,
- `extracted_at`: ursprünglicher Abrufzeitpunkt.

Die geplante Transformationsschnittstelle lautet:

```python
transform_public_power(snapshot: RawSnapshot) -> pl.DataFrame
```

Aktuell ist diese Schnittstelle erst vorbereitet. Es gibt noch keinen
MinIO-Leseweg, der ein `RawSnapshot` aufbaut, und die Polars-Transformation ist
noch nicht implementiert.

## Gesamter Objektfluss

Der bereits funktionierende Schreibweg sieht so aus:

```text
CLI
│
├── erstellt EnergyChartsClient
├── erstellt MinioStorage
│
└── ruft run_public_power_ingestion(...)
        │
        ├── EnergyChartsClient.get_public_power(...)
        │       │
        │       └── ExtractedResponse
        │             ├── JSON als Bytes
        │             ├── Request-URL
        │             └── extracted_at
        │
        ├── build_raw_object_name(...)
        │       └── MinIO-Objektname als String
        │
        ├── MinioStorage.put_json(...)
        │       └── speichert JSON-Bytes in MinIO
        │
        └── IngestionResult
                └── Quittung mit Speicherort
```

Der nächste, noch nicht implementierte Lese- und Transformationsweg soll
folgendermaßen aussehen:

```text
MinIO-Objekt lesen
      ↓
RawSnapshot bilden
      ↓
JSON mit Pydantic validieren
      ↓
mit Polars ins Long-Format transformieren
      ↓
DataFrame nach PostgreSQL laden
```

Die wichtigsten mentalen Grenzen sind:

> `ExtractedResponse` transportiert die abgeholten Raw-Daten. `MinioStorage`
> speichert sie. `IngestionResult` meldet zurück, wo sie gespeichert wurden.
> `RawSnapshot` wird später die gespeicherte Quelle zur Transformation tragen.
> Ein DataFrame entsteht erst bei der Transformation.
