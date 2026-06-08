import urllib.request
import csv
import io
import json
import math
import os
import datetime
from collections import defaultdict
from email.utils import parsedate_to_datetime

CSV_PREZZI_URL = "https://www.mimit.gov.it/images/exportCSV/prezzo_alle_8.csv"
CSV_ANAGRAFICA_URL = (
    "https://www.mimit.gov.it/images/exportCSV/anagrafica_impianti_attivi.csv"
)
GEOCODE_URL = "https://api.zippopotam.us/IT/"
EARTH_RADIUS_KM = 6371

# Ordine di priorità dei carburanti nel sommario
CARBURANTI_ORDINE = [
    "Benzina",
    "Benzina Plus",
    "Benzina Speciale",
    "Gasolio",
    "Gasolio Premium",
    "Gasolio Plus",
    "GPL",
    "Metano",
    "Blue Super",
    "Blue Diesel",
    "HiQ Perform+",
    "Excellium Diesel",
    "V-Power Diesel",
    "Supreme Diesel",
    "Supreme Plus Diesel",
]


def geocoda_cap(cap):
    """Risolve un CAP italiano in coordinate e nomi località tramite Zippopotam.us."""
    try:
        url = GEOCODE_URL + cap
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode('utf-8'))
        places = data.get("places", [])
        if not places:
            return None, None
        lat = float(places[0]["latitude"])
        lon = float(places[0]["longitude"])
        nomi = [p["place name"] for p in places]
        return (lat, lon), nomi
    except Exception as e:
        print(f"Impossibile geocodificare il CAP {cap}: {e}")
        return None, None


def chiedi_input(prompt, default=None, default_label=None):
    """Chiede un input all'utente con eventuale valore default."""
    if default is not None:
        label = default_label or default
        prompt += f" [{label}]: "
    else:
        prompt += ": "
    valore = input(prompt).strip()
    return valore if valore else default


def richiedi_parametri():
    """Chiede all'utente i parametri di localizzazione se non forniti via env vars."""
    cap = os.getenv("CAP_RIFERIMENTO") or chiedi_input("Inserisci il tuo CAP")
    while not cap or not cap.isdigit() or len(cap) != 5:
        print("CAP non valido (inserisci 5 cifre)")
        cap = chiedi_input("Inserisci il tuo CAP")

    coord_env = os.getenv("COORD_RIFERIMENTO")
    localita_env = os.getenv("NOME_LOCALITA")

    if coord_env:
        coord = tuple(float(x.strip()) for x in coord_env.split(","))
        localita = localita_env or "localita"
    else:
        coord_geo, nomi_geo = geocoda_cap(cap)
        if coord_geo:
            if len(nomi_geo) > 1:
                print(f"CAP {cap} corrisponde a:")
                for i, nome in enumerate(nomi_geo, 1):
                    print(f"  {i}. {nome}")
                scelta_raw = chiedi_input(
                    "Digita la località o il relativo numero",
                    str(len(nomi_geo)),
                    default_label=f"default: {nomi_geo[-1]}",
                )
                scelta = scelta_raw or str(len(nomi_geo))
                try:
                    idx = int(scelta) - 1
                    if 0 <= idx < len(nomi_geo):
                        localita_geo = nomi_geo[idx]
                    else:
                        print(f"Scelta non valida, uso {nomi_geo[-1]}")
                        localita_geo = nomi_geo[-1]
                except ValueError:
                    if scelta.lower() in (n.lower() for n in nomi_geo):
                        localita_geo = next(
                            (n for n in nomi_geo if n.lower() == scelta.lower()),
                            nomi_geo[-1],
                        )
                    else:
                        print(f"Scelta non valida, uso {nomi_geo[-1]}")
                        localita_geo = nomi_geo[-1]
            else:
                localita_geo = nomi_geo[0]
            print(f"Coordinate: {coord_geo[0]:.4f}, {coord_geo[1]:.4f}")
            coord = coord_geo
            localita = localita_env or localita_geo
        else:
            while True:
                coord_str = chiedi_input(
                    "Geocodifica fallita. Inserisci le coordinate (lat,lon) — es. 40.6828,14.7681"
                )
                try:
                    coord = tuple(float(x.strip()) for x in coord_str.split(","))
                    if len(coord) == 2:
                        break
                    print("Inserisci due valori separati da virgola (lat,lon)")
                except ValueError:
                    print("Coordinate non valide, usa il formato lat,lon (es. 40.6828,14.7681)")
            localita = localita_env or chiedi_input(
                "Nome della località (per l'output)", "localita"
            )

    raggio_str = os.getenv("RAGGIO_KM") or chiedi_input(
        "Raggio di ricerca in km", "10",
        default_label="min: 1 / max: 50 / default: 10",
    )
    raggio = None
    while raggio is None:
        try:
            val = int(raggio_str)
            if 1 <= val <= 50:
                raggio = val
            else:
                print("Raggio non valido (deve essere tra 1 e 50)")
                raggio_str = chiedi_input(
                    "Raggio di ricerca in km", "10",
                    default_label="min: 1 / max: 50 / default: 10",
                )
        except ValueError:
            print("Inserisci un numero intero")
            raggio_str = chiedi_input(
                "Raggio di ricerca in km", "10",
                default_label="min: 1 / max: 50 / default: 10",
            )

    return coord, raggio, localita


def scarica_csv(url):
    """Scarica il CSV da URL e restituisce i dati e la data Last-Modified."""
    try:
        with urllib.request.urlopen(url) as response:
            dati = response.read().decode('utf-8')
            last_modified = response.headers.get('Last-Modified')
            return dati, last_modified
    except Exception as e:
        print(f"Errore nel download del CSV da {url}: {e}")
        return None, None


def leggi_csv(dati_csv, delimiter='|'):
    """Legge i dati CSV da stringa e restituisce una lista di dizionari."""
    f = io.StringIO(dati_csv)
    try:
        next(f)
    except StopIteration:
        return []
    reader = csv.DictReader(f, delimiter=delimiter)
    return list(reader)


def distanza_haversine(coord1, coord2):
    """Calcola la distanza in km tra due coordinate (lat, lon) usando la formula di Haversine."""
    lat1, lon1 = coord1
    lat2, lon2 = coord2
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * c


def filtra_impianti(anagrafica, coord_rif, raggio_km):
    """Filtra gli impianti per distanza dal punto di riferimento."""
    risultati = []
    for imp in anagrafica:
        lat_str = (imp.get("Latitudine") or "").replace(",", ".").strip()
        lon_str = (imp.get("Longitudine") or "").replace(",", ".").strip()
        try:
            lat = float(lat_str)
            lon = float(lon_str)
        except ValueError:
            continue

        dist = distanza_haversine(coord_rif, (lat, lon))
        if dist <= raggio_km:
            imp = dict(imp)
            imp["Distanza_km"] = dist
            risultati.append(imp)
    return risultati


def formatta_data_last_modified(data_str):
    """Formatta la data Last-Modified in orario locale leggibile."""
    if not data_str:
        return "non disponibile"
    try:
        dt = parsedate_to_datetime(data_str)
        dt_locale = dt.astimezone()
        return dt_locale.strftime("%Y-%m-%d %H:%M:%S %Z")
    except Exception:
        return data_str


def ordina_carburanti(carburanti_keys):
    """Ordina i carburanti per priorità, poi alfabeticamente per i rimanenti."""
    ordinati = []
    rimanenti = list(carburanti_keys)
    for c in CARBURANTI_ORDINE:
        if c in rimanenti:
            ordinati.append(c)
            rimanenti.remove(c)
    ordinati.extend(sorted(rimanenti))
    return ordinati


def nome_impianto(imp, bandiera):
    """Costruisce il nome visualizzato dell'impianto con bandiera."""
    nome = imp.get("Nome Impianto") or imp.get("Gestore") or "Sconosciuto"
    return f"[{bandiera}] {nome}" if bandiera else nome


def scrivi_sommario(f_out, titolo, migliori):
    """Scrive un sommario con banner e lista migliori prezzi."""
    if not migliori:
        return
    print("\n" + "=" * 60, file=f_out)
    print(titolo, file=f_out)
    print("=" * 60, file=f_out)
    for carburante in ordina_carburanti(migliori.keys()):
        prezzo, nome_imp, dist = migliori[carburante]
        dist_str = f"{dist:.2f} km" if dist is not None else "N/A"
        print(f"  {carburante}: € {prezzo:.3f} - {nome_imp} ({dist_str})", file=f_out)


def salva_prezzi_su_file(
    prezzi,
    impianti_filtrati,
    percorso_file,
    data_documento=None,
    nome_localita="localita",
    raggio_km=10,
):
    """Salva i dati degli impianti e prezzi in un file di testo, con intestazioni e ordinamento."""
    prezzi_per_id = defaultdict(list)
    for p in prezzi:
        id_impianto = p.get("idImpianto")
        if id_impianto:
            prezzi_per_id[id_impianto].append(p)

    impianti_ordinati = sorted(impianti_filtrati, key=lambda x: x.get("Distanza_km", float("inf")))

    # Raccogli i migliori prezzi per sommario
    migliori_self = {}
    migliori_servito = {}

    with open(percorso_file, "w", encoding="utf-8") as f_out:
        data_formattata = formatta_data_last_modified(data_documento)
        fonte = "www.mimit.gov.it"
        titolo = f"PREZZI CARBURANTI — {nome_localita} ({raggio_km} km)"
        print("=" * 60, file=f_out)
        print(titolo, file=f_out)
        print("=" * 60, file=f_out)
        print(
            f"Prezzi aggiornati il: {data_formattata} (Fonte: {fonte})",
            file=f_out,
        )
        print(
            f"Impianti ordinati per distanza crescente dal punto di riferimento "
            f"({nome_localita}, {raggio_km} km).",
            file=f_out,
        )

        if not impianti_ordinati:
            print(f"Nessun impianto trovato entro {raggio_km} km.", file=f_out)
            return

        for impianto in impianti_ordinati:
            id_impianto = impianto.get("idImpianto")
            bandiera = (impianto.get("Bandiera") or "").strip()
            nome = nome_impianto(impianto, bandiera)
            indirizzo = impianto.get("Indirizzo", "Indirizzo non disponibile")
            distanza = impianto.get("Distanza_km", None)

            testo_blocco = f"\nImpianto: {nome}\nIndirizzo: {indirizzo}"
            if distanza is not None:
                testo_blocco += f"\nDistanza: {distanza:.2f} km"
            print(testo_blocco, file=f_out)

            if id_impianto in prezzi_per_id:
                # Raggruppa per tipo carburante, distingui self/servito
                carburanti = {}
                for p in prezzi_per_id[id_impianto]:
                    carburante = p.get("descCarburante") or "Sconosciuto"
                    prezzo_str = p.get("prezzo") or ""
                    is_self = p.get("isSelf")
                    try:
                        prezzo = float(prezzo_str)
                    except (ValueError, TypeError):
                        continue
                    if carburante not in carburanti:
                        carburanti[carburante] = {}
                    if is_self == "1":
                        carburanti[carburante]["self"] = prezzo
                    else:
                        carburanti[carburante]["full"] = prezzo

                if carburanti:
                    print("Prezzi carburanti:", file=f_out)
                    for carburante, prezzi_tipo in carburanti.items():
                        if "self" in prezzi_tipo:
                            riga = f"  - {carburante}: € {prezzi_tipo['self']:.3f} (self)"
                            if "full" in prezzi_tipo:
                                riga += f" / (servito): € {prezzi_tipo['full']:.3f}"
                            print(riga, file=f_out)
                            # Traccia miglior prezzo self-service
                            if carburante not in migliori_self or prezzi_tipo["self"] < migliori_self[carburante][0]:
                                migliori_self[carburante] = (
                                    prezzi_tipo["self"],
                                    nome_impianto(impianto, bandiera),
                                    distanza,
                                )
                        elif "full" in prezzi_tipo:
                            print(f"  - {carburante}: € {prezzi_tipo['full']:.3f} (servito)", file=f_out)

                        # Traccia miglior prezzo servito
                        if "full" in prezzi_tipo:
                            if carburante not in migliori_servito or prezzi_tipo["full"] < migliori_servito[carburante][0]:
                                migliori_servito[carburante] = (
                                    prezzi_tipo["full"],
                                    nome_impianto(impianto, bandiera),
                                    distanza,
                                )
                else:
                    print("Prezzi non disponibili", file=f_out)
            else:
                print("Prezzi non disponibili", file=f_out)

        # Sommari migliori prezzi
        scrivi_sommario(f_out, "MIGLIORI PREZZI SELF-SERVICE", migliori_self)
        scrivi_sommario(f_out, "MIGLIORI PREZZI SERVITO", migliori_servito)

    os.chmod(percorso_file, 0o444)


def get_output_path(nome_localita="localita", raggio_km=10):
    """Genera il percorso completo del file di output sul Desktop con timestamp."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"carburanti_{nome_localita}_{raggio_km}km_{timestamp}.txt"
    return os.path.join(os.path.expanduser("~"), "Desktop", filename)


def main():
    coord_rif, raggio_km, nome_localita = richiedi_parametri()

    print("Scarico anagrafica impianti...")
    dati_anagrafica, _ = scarica_csv(CSV_ANAGRAFICA_URL)

    print("Scarico prezzi carburanti...")
    dati_prezzi, data_file = scarica_csv(CSV_PREZZI_URL)

    if not dati_anagrafica or not dati_prezzi:
        print("Errore nel download dei dati, impossibile proseguire.")
        return

    anagrafica = leggi_csv(dati_anagrafica)
    prezzi = leggi_csv(dati_prezzi)

    if anagrafica and prezzi:
        impianti_filtrati = filtra_impianti(anagrafica, coord_rif, raggio_km)
        print(f"Impianti trovati entro {raggio_km} km: {len(impianti_filtrati)}")
    else:
        print("Dati anagrafica o prezzi mancanti/vuoti dopo la lettura.")
        return

    print("Salvo output...")
    output_path = get_output_path(nome_localita, raggio_km)
    salva_prezzi_su_file(
        prezzi,
        impianti_filtrati,
        output_path,
        data_documento=data_file,
        nome_localita=nome_localita,
        raggio_km=raggio_km,
    )
    print(f"Output salvato in: {output_path}")


if __name__ == "__main__":
    main()
