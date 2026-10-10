# P2 frozen snapshot - 5 October 2026 (IMF PortWatch)

Corridor layer of the UAE Food Supply Resilience Stress Test. Do not edit these files; a new download is a new cut.

| File | Content | Coverage |
|---|---|---|
| corridor_ports_daily_2026-10-05.csv | Daily port calls and import/export tonnes by vessel type: Fujairah (port362), Khor Fakkan (port561), Sohar (port988), Duqm (port984), Salalah (port746), Jeddah (port518), King Abdullah Port (port2031) | 2023-01-01 to 2026-09-25 |
| chokepoints_daily_2026-10-05.csv | Daily transits by vessel type: Hormuz (chokepoint6), Bab el-Mandeb (chokepoint4), Suez (chokepoint1), Cape of Good Hope (chokepoint7) | 2023-01-01 to 2026-09-27 |

Retrieved 2026-10-05 from https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/<service>/FeatureServer/0/query (Daily_Ports_Data, Daily_Chokepoints_Data), paginated, outFields=*, where year>=2023. Code: src/p2_corridors_v0.2.py. Hashes: SHA256SUMS.

Source: International Monetary Fund, PortWatch. AIS-based estimates of total cargo, not food; non-commercial reuse with attribution to the IMF.
