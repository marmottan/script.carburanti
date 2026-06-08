# Script `carburanti.py`

Trova i distributori di carburante più vicini e i prezzi migliori nella tua zona, utilizzando i dati ufficiali del MIMIT.

## Utilizzo

```bash
python3 carburanti.py
```

Inserisci CAP, località e raggio di ricerca (1–50 km).

In alternativa, puoi usare le variabili d'ambiente:

```bash
CAP_RIFERIMENTO=00100 NOME_LOCALITA=Roma RAGGIO_KM=5 python3 carburanti.py
```

## Variabili d'ambiente

| Variabile           | Descrizione                                 |
| ------------------- | ------------------------------------------- |
| `CAP_RIFERIMENTO`   | CAP di partenza                             |
| `COORD_RIFERIMENTO` | Coordinate manuali nel formato `lat,lon`    |
| `NOME_LOCALITA`     | Nome della località da mostrare nell'output |
| `RAGGIO_KM`         | Raggio di ricerca in km (1–50)              |

## Requisiti

* Python 3.6 o superiore
* Connessione Internet

## Fonti dati

* Anagrafica e prezzi carburanti: dati open data del MIMIT (rilevazione alle 08:00)
* Geocodifica CAP: Zippopotam.us

## Licenza

GPLv3
