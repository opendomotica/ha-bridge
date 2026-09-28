# Changelog

## [0.3.0]

### Added

- Added Home Assistant climate entities for OpenDomotica climate zones, including current temperature, heating status, and target temperature.
- Added support for `off`, `manual` (`heat`), and `auto` modes, with target temperature changes switching the zone to manual mode.
- Added polling and REST API support for reading and updating climate zones.
- Added the Home Assistant `valve` platform for solenoid valves of types `10004` and `10005`.
- Type `10004` reads `valve_status` and supports the `open`, `close`, `opening`, and `closing` states.
- Type `10005` reads `port_status` as the valve state.
- `port_status` interpretation accounts for the wiring: `wiring='na'` preserves the standard polarity, while `wiring='nc'` inverts `0` and `1`.
- Wiring normalization is applied both during polling and to updates received through the webhook.

### Fixed

- Prevented all entities from briefly becoming unavailable after a single failed periodic poll.

## [0.2.0]

### Added

- Added API key configuration and authentication for requests to the OpenDomotica server.
- Added suggested Home Assistant area assignment for devices.
- Added support for energy statistics, including additional daily energy sensors.

### Fixed

- Fixed polling when a device returns an empty attributes list.
- Fixed API key authentication and cover open/close commands.
- Corrected the API request used to set device values.
- Removed the persistent notification dependency.

## [0.1.0]

### Added

- Initial Home Assistant integration with configuration flow and polling for supported devices.
- Added light, switch, sensor, and cover entities backed by the OpenDomotica API.
- Added webhook support for push status updates.
