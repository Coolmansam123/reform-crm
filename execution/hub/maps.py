"""Shared Google Maps + AdvancedMarker helpers.

After the AdvancedMarkerElement migration sweep (commits 7a7fd3a..20833b6),
several pages were left carrying near-identical color palettes, office-pin
builders, legacy-icon adapters, and script-URL strings. This module pulls the
truly redundant bits into one place so future tweaks (palette adjustments,
glyph changes, library/version bumps) only need to land here.

Pages don't import individual functions at runtime — JS is emitted as Python
strings and concatenated into the page's `<script>` body. Consumers pick the
constants they need:

    from hub.maps import (
        MAP_PALETTE_JS,        # color tables
        OFFICE_PIN_JS,         # _mapOfficePin / _mapOfficePinNavy factories
        ICON_BRIDGE_JS,        # _mapIconEl(legacyIconObj) -> HTMLElement
        PULSE_KEYFRAME_CSS,    # @keyframes gpulse for alert pins
        map_script_url,        # build &v=weekly&libraries=marker URL
    )

Each consuming file is responsible for namespacing the JS it includes
(no two pages should both import OFFICE_PIN_JS twice; redeclaration of
`_mapOfficePin` would error). All factories are guarded against missing
google.maps.marker library.
"""


# ─── JS: color palettes ─────────────────────────────────────────────────────
# Combined venue-status colors (sales pipeline) + route-stop status colors.
# Some keys overlap (e.g. 'In Progress'), but the values match across the two
# domains so a single map serves both. Pages can index into _MAP_STATUS_COLORS
# whether they're rendering a venue or a stop.
MAP_PALETTE_JS = r"""
const _MAP_STATUS_COLORS = {
  // Venue / outreach pipeline
  'Not Contacted':       '#4285f4',
  'Contacted':           '#fbbc04',
  'In Discussion':       '#ff9800',
  'Active Partner':      '#34a853',
  'Active Relationship': '#34a853',
  // Route-stop statuses
  'Pending':             '#9e9e9e',
  'In Progress':         '#fbbc04',
  'Visited':             '#34a853',
  'Skipped':             '#f97316',
  'Not Reached':         '#ef4444',
};
const _MAP_TOOL_BORDER = { gorilla: '#ea580c', community: '#059669' };
const _MAP_BOX_COLORS  = { action: '#ef4444', warning: '#f59e0b', ok: '#059669' };
"""


# ─── JS: office-pin factories ───────────────────────────────────────────────
# Two variants — the bright red star matches Google's home-base look and is
# used by the venue/admin maps. The navy variant reads as "command HQ" on the
# rep's route + outreach maps where the pin sits among numbered stops.
OFFICE_PIN_JS = r"""
function _mapOfficePin() {
  // Returns the PinElement.element ready to drop into AdvancedMarker.content.
  if (!(google.maps.marker && google.maps.marker.PinElement)) return null;
  return new google.maps.marker.PinElement({
    background: '#ea4335', borderColor: '#b31412',
    glyphColor: '#fff',    glyph: '★', scale: 1.1,
  }).element;
}

function _mapOfficePinNavy() {
  if (!(google.maps.marker && google.maps.marker.PinElement)) return null;
  return new google.maps.marker.PinElement({
    background: '#1e3a5f', borderColor: '#0f1e35',
    glyphColor: '#fff',    glyph: '★', scale: 1.4,
  }).element;
}
"""


# ─── JS: legacy icon → HTMLElement bridge ───────────────────────────────────
# The batch generators (generate_*_map.py) build SVG-data-URI icon objects
# in the legacy `{url, scaledSize, anchor}` shape. AdvancedMarker requires an
# HTMLElement. This adapter wraps the URL in an <img> sized to scaledSize so
# existing markerIcon()/homeMarkerIcon() output works without rewriting the
# SVG generation. AdvancedMarker anchors content's bottom-center at
# marker.position, which matches the SVG pin-tip anchor.
ICON_BRIDGE_JS = r"""
function _mapIconEl(iconObj) {
  const img = document.createElement('img');
  img.src = iconObj.url;
  if (iconObj.scaledSize) {
    img.style.width  = iconObj.scaledSize.width  + 'px';
    img.style.height = iconObj.scaledSize.height + 'px';
    img.style.display = 'block';
  }
  return img;
}
"""


# ─── CSS: pulse keyframe for alert pins ─────────────────────────────────────
# Used by overdue-box ring animation in pages/map.py. Drop into the page's
# inline <style> block (the keyframe is global once defined; no scoping risk
# unless two pages both inject it on the same DOM, which doesn't happen here).
PULSE_KEYFRAME_CSS = """
<style>
@keyframes gpulse {
  0%   { transform:scale(1);    opacity:.55 }
  100% { transform:scale(1.7);  opacity:0 }
}
</style>
"""


# ─── Python: Maps JS API URL builder ────────────────────────────────────────
def map_script_url(api_key: str, callback: str = "") -> str:
    """Returns the Maps JavaScript API loader URL with the marker library
    enabled and pinned to weekly so AdvancedMarkerElement is available.

    `api_key` is the Google Maps API key (typically `os.environ["GOOGLE_MAPS_API_KEY"]`).
    `callback` is an optional global function name to fire when the script
    finishes loading; if empty, no callback param is appended.
    """
    base = f"https://maps.googleapis.com/maps/api/js?key={api_key}&v=weekly&libraries=marker"
    if callback:
        base += f"&callback={callback}"
    return base
