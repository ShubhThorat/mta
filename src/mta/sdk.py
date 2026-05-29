"""MTA BusTime SDK — SIRI real-time bus data via bustime.mta.info."""

from __future__ import annotations

import json
import re
import urllib.request
from typing import Any

MTA_BASE = "https://bustime.mta.info"
MTA_KEY = "TEST"

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

_LINE_FULL_RE = re.compile(r"^MTA\s+NYCT_(.+)$", re.IGNORECASE)
_LINE_SHORT_RE = re.compile(r"^([A-Za-z]{1,3}\d+(?:-SBS|-\+|[+]?)?)$")


def _normalize_line(line: str) -> str:
    """Convert 'M15', 'B44-SBS', 'Bx12', 'mta nyct_m15', etc. to 'MTA NYCT_M15'."""
    line = line.strip()
    m = _LINE_FULL_RE.match(line)
    if m:
        route = m.group(1)
    else:
        route = line
    # Preserve Bx/bx prefix casing (Bronx routes use 'Bx'), uppercase everything else
    if re.match(r"^[Bb][Xx]\d", route):
        route = "Bx" + route[2:].upper().lstrip("X")
    else:
        route = route.upper()
    return f"MTA NYCT_{route}"


def _get(path: str, params: dict, timeout: int = 30) -> dict:
    from urllib.parse import urlencode
    qs = urlencode({**params, "key": MTA_KEY})
    url = f"{MTA_BASE}{path}?{qs}"
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


# ---------------------------------------------------------------------------
# Slim helpers
# ---------------------------------------------------------------------------

def _first(val: Any) -> Any:
    if isinstance(val, list) and val:
        return val[0]
    return val


def _slim_journey(mvj: dict) -> dict:
    out: dict[str, Any] = {}
    line = _first(mvj.get("PublishedLineName")) or mvj.get("LineRef", "")
    if line:
        out["line"] = line
    dest = _first(mvj.get("DestinationName"))
    if dest:
        out["destination"] = dest
    direction = mvj.get("DirectionRef")
    if direction is not None:
        out["direction"] = direction
    vehicle = mvj.get("VehicleRef")
    if vehicle:
        out["vehicleRef"] = vehicle
    loc = mvj.get("VehicleLocation")
    if loc:
        out["location"] = {"lat": loc.get("Latitude"), "lon": loc.get("Longitude")}
    bearing = mvj.get("Bearing")
    if bearing is not None:
        out["bearing"] = bearing
    progress = mvj.get("ProgressRate")
    if progress:
        out["progressRate"] = progress
    monitored = mvj.get("Monitored")
    if monitored is not None:
        out["monitored"] = monitored
    return out


def _slim_call(call: dict) -> dict:
    out: dict[str, Any] = {}
    stop_name = _first(call.get("StopPointName"))
    if stop_name:
        out["stopName"] = stop_name
    stop_ref = call.get("StopPointRef", "")
    if stop_ref:
        out["stopRef"] = stop_ref.replace("MTA_", "")
    at_stop = call.get("VehicleAtStop")
    if at_stop is not None:
        out["atStop"] = at_stop
    ext = (call.get("Extensions") or {}).get("Distances") or {}
    if ext.get("PresentableDistance"):
        out["presentableDistance"] = ext["PresentableDistance"]
    if ext.get("StopsFromCall") is not None:
        out["stopsAway"] = ext["StopsFromCall"]
    if ext.get("DistanceFromCall") is not None:
        out["distanceFt"] = round(ext["DistanceFromCall"])
    return out


def _slim_arrival(visit: dict) -> dict | None:
    mvj = visit.get("MonitoredVehicleJourney")
    if not mvj:
        return None
    out = _slim_journey(mvj)
    call = mvj.get("MonitoredCall")
    if call:
        out.update(_slim_call(call))
    return out


def _slim_vehicle(activity: dict) -> dict | None:
    mvj = activity.get("MonitoredVehicleJourney")
    if not mvj:
        return None
    out = _slim_journey(mvj)
    call = mvj.get("MonitoredCall")
    if call:
        stop_name = _first(call.get("StopPointName"))
        if stop_name:
            out["nextStop"] = stop_name
    return out


def _slim_stop(stop: dict) -> dict:
    out: dict[str, Any] = {
        "id": stop.get("id", "").replace("MTA NYCT_", ""),
        "name": stop.get("name", ""),
    }
    if stop.get("lat") is not None:
        out["lat"] = stop["lat"]
    if stop.get("lon") is not None:
        out["lon"] = stop["lon"]
    if stop.get("direction"):
        out["direction"] = stop["direction"]
    return out


# ---------------------------------------------------------------------------
# Public fetch functions
# ---------------------------------------------------------------------------

def fetch_arrivals(stop_id: str, line: str | None = None, limit: int = 10, timeout: int = 30) -> dict:
    """Real-time arrivals at a stop (SIRI StopMonitoring)."""
    params: dict[str, Any] = {"MonitoringRef": stop_id}
    if line:
        params["LineRef"] = _normalize_line(line)
    data = _get("/api/siri/stop-monitoring.json", params, timeout=timeout)

    delivery = (
        data.get("Siri", {})
        .get("ServiceDelivery", {})
        .get("StopMonitoringDelivery", [{}])
    )
    if delivery:
        delivery = delivery[0]
    visits = delivery.get("MonitoredStopVisit") or []

    arrivals = [a for a in (_slim_arrival(v) for v in visits[:limit]) if a]
    return {
        "stopId": stop_id,
        "line": line.upper() if line else None,
        "arrivals": arrivals,
        "count": len(arrivals),
    }


def fetch_vehicles(line: str, timeout: int = 30) -> dict:
    """Active vehicles on a route (SIRI VehicleMonitoring)."""
    line_ref = _normalize_line(line)
    data = _get("/api/siri/vehicle-monitoring.json", {"LineRef": line_ref}, timeout=timeout)

    delivery = (
        data.get("Siri", {})
        .get("ServiceDelivery", {})
        .get("VehicleMonitoringDelivery", [{}])
    )
    if delivery:
        delivery = delivery[0]
    activities = delivery.get("VehicleActivity") or []

    vehicles = [v for v in (_slim_vehicle(a) for a in activities) if v]
    return {
        "line": line_ref.replace("MTA NYCT_", ""),
        "vehicles": vehicles,
        "count": len(vehicles),
    }


def fetch_route_stops(line: str, timeout: int = 30) -> dict:
    """All stops on a route in order."""
    line_ref = _normalize_line(line)
    route_id = urllib.request.quote(line_ref)
    data = _get(f"/api/where/stops-for-route/{route_id}.json", {"includePolylines": "false"}, timeout=timeout)

    entry = data.get("data", {}).get("entry", {})
    refs = entry.get("stopIds") or []
    stops_map = {s["id"]: s for s in (data.get("data", {}).get("references", {}).get("stops") or [])}

    stops = []
    for ref in refs:
        s = stops_map.get(ref)
        if s:
            stops.append(_slim_stop(s))

    return {
        "line": line_ref.replace("MTA NYCT_", ""),
        "stops": stops,
        "count": len(stops),
    }


def fetch_stops_near(lat: float, lon: float, radius: float = 0.003, timeout: int = 30) -> dict:
    """Find bus stops near a lat/lon coordinate."""
    span = radius
    data = _get("/api/where/stops-for-location.json", {
        "lat": lat, "lon": lon,
        "latSpan": span, "lonSpan": span,
    }, timeout=timeout)

    raw_stops = data.get("data", {}).get("stops") or []
    stops = [_slim_stop(s) for s in raw_stops]
    return {
        "lat": lat,
        "lon": lon,
        "stops": stops,
        "count": len(stops),
    }
