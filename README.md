# OpenDomotica Bridge

Integrazione custom per Home Assistant che fa da **ponte (bridge)** tra un
server di domotica esterno e Home Assistant: scopre i dispositivi esposti dal
server, li rappresenta come entità HA (luci, interruttori, sensori, tapparelle,
climatizzazione) e inoltra i comandi impartiti da Home Assistant verso il
server.

## Struttura del progetto

```
custom_components/opendomotica_bridge/
├── __init__.py        # setup/unload della config entry, avvio del coordinator
├── api.py             # client verso il server di domotica
├── config_flow.py      # flusso di configurazione UI (host/porta/SSL) + opzioni
├── const.py            # DOMAIN, piattaforme, mappatura codice "type" -> categoria
├── coordinator.py       # polling periodico dei dispositivi (DataUpdateCoordinator)
├── entity.py            # entità base condivisa (device_info, disponibilità)
├── light.py, switch.py, sensor.py, cover.py, climate.py  # piattaforme entità
├── manifest.json
├── strings.json / translations/  # testi UI (en, it)
```

## Contratto API del server di domotica

Il client in `api.py` chiama le seguenti API REST (basate su `http(s)://<host>:<port>/api/v1`):

| Azione | Endpoint |
|---|---|
| Lista dispositivi | `GET /devices` |
| Valore di un attributo | `GET /devices/{device_id}/attributes/{attribute}` |
| Accendi | `POST /devices/{device_id}/execute/turn_on` |
| Spegni | `POST /devices/{device_id}/execute/turn_off` |
| Inverti stato | `POST /devices/{device_id}/execute/toggle` |
| Imposta un valore | `POST /devices/{device_id}/execute/set_value?value=...` |

La lista dispositivi non contiene lo stato: il coordinator interroga
l'attributo giusto per ogni dispositivo (in base al codice `type`, vedi
`const.DEVICE_STATUS_ATTRIBUTE`) a ogni ciclo di polling e lo unisce ai
metadati sotto la chiave `status_value`. Attributi confermati:

| Attributo | Usato da |
|---|---|
| `port_status` | on/off (luci, interruttori, prese, elettrovalvole, ecc. — default) |
| `current_value` | sensori di temperatura; posizione tapparelle (scala 0-250) |
| `current_power` | sensori di assorbimento elettrico |
| `current_power_ac` | inverter fotovoltaici (produzione) |

Formato di un elemento della lista dispositivi:

```jsonc
{
  "device_id": "178",
  "device_description": "Luce porta 128",
  "node_id": "2",
  "node_port": "128",
  "type": "10001",           // codice numerico, vedi mappatura sotto
  "group_id": "12",
  "gui_description": null,    // nome preferito se impostato, altrimenti device_description
  "gui_icon": null,
  "update_timestamp": "1788109334",
  "event_timestamp": "1788109334"
}
```

### Mappatura codice `type` → categoria HA

Definita in `const.DEVICE_TYPE_MAP`, modificabile se la tua installazione usa
altri codici:

| Codice | Dispositivo | Categoria HA |
|---|---|---|
| 10001 | Luce | light |
| 10008 | Led strip WS2812B | light |
| 10002 | Presa | switch |
| 10003 | Caldaia | switch |
| 10004 | Elettrovalvola riscaldamento | switch |
| 10005 | Elettrovalvola irrigazione | switch |
| 10006 | Alimentatore | switch |
| 10101 | Ricevitore AV | switch |
| 20005 | Interruttore | switch |
| 20006 | Interruttore virtuale | switch |
| 10007 | Motore apri/chiudi | cover |
| 20002 | Sensore temperatura | sensor |
| 20003 | Contatore energia elettrica | sensor |
| 20004 | Inverter SMA | sensor |
| 30001 | UPS | sensor |
| 20001 | Pulsante | non esposto di default (ingresso momentaneo) |

### Limitazioni note (da adattare se necessario)

- **Luci**: solo accensione/spegnimento (`ColorMode.ONOFF`); `port_status` non
  ha una scala di luminosità confermata. Se un dispositivo supporta il
  dimming, aggiorna `light.py` per usare `async_set_value`.
- **Tapparelle**: posizione letta/scritta da `current_value` su scala 0-250 e
  riconvertita in percentuale 0-100 per Home Assistant; nessun comando "stop"
  confermato, quindi `CoverEntityFeature.STOP` non è esposto.
- **Climatizzazione**: nessun codice `type` è mappato di default su
  `climate`, perché l'API non espone temperatura corrente/target né modalità
  HVAC separate. La piattaforma resta pronta per l'uso ma va completata se il
  tuo server espone questi dati.
- **UPS** (30001): usa `port_status` come attributo di default, non
  confermato: adatta `const.DEVICE_STATUS_ATTRIBUTE` se necessario.

Per adattare endpoint, autenticazione o parsing, modifica solo `api.py`: il
resto dell'integrazione dipende esclusivamente dai suoi metodi pubblici
(`async_get_devices`, `async_get_device_attribute`, `async_turn_on`,
`async_turn_off`, `async_toggle`, `async_set_value`).

## Installazione


### Tramite HACS (repository custom)

1. In HACS → Integrazioni → menu (⋮) → **Repository personalizzate**.
2. Aggiungi l'URL di questo repository con categoria **Integration**.
3. Installa "OpenDomotica Bridge" e riavvia Home Assistant.

### Manuale

Copia la cartella `custom_components/opendomotica_bridge` nella cartella
`custom_components` della tua configurazione Home Assistant e riavvia.

## Configurazione

Impostazioni → Dispositivi e servizi → Aggiungi integrazione →
**OpenDomotica Bridge**. Inserisci host, porta e se usare HTTPS per il server
di domotica.

L'intervallo di aggiornamento (polling) è configurabile dalle opzioni
dell'integrazione dopo l'installazione (default: 30 secondi).

## Licenza

[MIT](LICENSE)


### Tramite HACS (repository custom)

1. In HACS → Integrazioni → menu (⋮) → **Repository personalizzate**.
2. Aggiungi l'URL di questo repository con categoria **Integration**.
3. Installa "OpenDomotica Bridge" e riavvia Home Assistant.

### Manuale

Copia la cartella `custom_components/opendomotica_bridge` nella cartella
`custom_components` della tua configurazione Home Assistant e riavvia.

## Configurazione

Impostazioni → Dispositivi e servizi → Aggiungi integrazione →
**OpenDomotica Bridge**. Inserisci host e porta del server di domotica.

L'intervallo di aggiornamento (polling) è configurabile dalle opzioni
dell'integrazione dopo l'installazione (default: 30 secondi).

## Licenza

[MIT](LICENSE)
