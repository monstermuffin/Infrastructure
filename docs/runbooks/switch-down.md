# SwitchDown

## What it means

A site collector has had no SNMP answer from a switch for 10 minutes (both scrape jobs of the switch, `snmp_interfaces` and `snmp_health`, are failing). Traffic, port state and health readings for that switch are not being recorded. The switch may be off or unreachable, or the collector can no longer read it (SNMP disabled, community changed, address restriction, firewall).

If the whole site is silent, look at `SiteUnreachable` first. If only one of the two jobs fails the switch is answering and this alert does not fire.

## First three checks

1. Is the switch reachable from the collector? On the site's collector: `ping -c 3 <switch address>`. The addresses are in `monitoring_topology.switches`.
2. Does it answer SNMP? From the collector, or any host allowed by the switch's SNMP settings: `snmpget -v2c -c <community> <switch address> 1.3.6.1.2.1.1.5.0` (the community is the site's `snmp_community_<site>` vault value; do not paste it anywhere shared). A timeout with a working `ping` points at the SNMP settings or a firewall; a wrong community also times out.
3. Metric: `up{job=~"snmp_.*", host="<switch>"}` and `snmp_scrape_duration_seconds{host="<switch>"}` in Grafana Explore, and the Switches dashboard. On the collector, `journalctl -u alloy -n 100` shows scrape errors.

## Common causes and fixes

- The switch lost power or was rebooted: it comes back on its own; the alert clears after the next successful scrape.
- SNMP got disabled, or its allowed addresses or community were changed on the switch (a firmware upgrade or a settings reset can do this): re-enable SNMP with the site's community and allow the collector's address in the switch's SNMP settings.
- The community was rotated on the switch but not in the vault: update `snmp_community_<site>` in the collector's `podman.yml` and deploy the collector. Alloy re-reads the credential file within a minute, no restart is needed.
- A firewall or routing change blocks UDP 161 from the collector to the switch's management address: restore the rule.
- The collector's Alloy failed to load its config: `alloy validate /etc/alloy`, and redeploy the collector role. Then all switches at the site go quiet together.

## When it is safe to silence

During planned work on the switch or its management network. Create an Alertmanager silence on `alertname="SwitchDown"` and `host="<switch>"` with an expiry and a comment. A switch that is meant to stay off (spare or test gear) belongs on `monitoring_switchdown_ignore` in the hub's `podman.yml`, which the rule leaves out.
