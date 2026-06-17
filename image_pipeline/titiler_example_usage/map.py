import folium
import requests
import webbrowser
from pathlib import Path

TITILER = "http://localhost:8004"
MOSAIC_PATH = "/home/ubuntu/work/saved_data/collections/digital_orthofoto_nrw/mosaic.json"
GERMANY_COG_PATH = "/home/ubuntu/work/satellite_data/germany/2021/2021_08.vrt"
print("step1")
tj = requests.get(
    f"{TITILER}/mosaicjson/WebMercatorQuad/tilejson.json", params={"url": MOSAIC_PATH}
).json()
print("step2")
lon, lat, zoom = tj["center"]
west, south, east, north = tj["bounds"]

m = folium.Map(location=[lat, lon], zoom_start=int(zoom), tiles="OpenStreetMap")

cog_layer = folium.TileLayer(
    tiles=tj["tiles"][0],
    attr="mosaic.json via TiTiler",
    name="mosaic.json",
    overlay=True,
    control=True,
    min_zoom=tj["minzoom"],
    max_zoom=tj["maxzoom"],
)
cog_layer.add_to(m)
print("step3")
germany_tj = requests.get(
    f"{TITILER}/cog/WebMercatorQuad/tilejson.json",
    params={"url": GERMANY_COG_PATH, "bidx": [3, 2, 1], "rescale": "0,3000"},
).json()

germany_layer = folium.TileLayer(
    tiles=germany_tj["tiles"][0],
    attr="Germany 2021 via TiTiler",
    name="germany 2021",
    overlay=True,
    control=True,
    show=False,
    min_zoom=6,
    max_zoom=22,
)
germany_layer.add_to(m)

m.fit_bounds([[south, west], [north, east]])
folium.LayerControl().add_to(m)

panel_html = """
<div id="zoom-panel" style="
    position: fixed; top: 10px; left: 60px; z-index: 9999;
    background: rgba(0,0,0,0.75); color: #fff; font: 12px/1.4 monospace;
    padding: 8px 10px; border-radius: 6px; max-width: 320px;">
  <div>zoom: <span id="zp-zoom">-</span></div>
  <div>last COG tile: <span id="zp-last">-</span></div>
  <div style="margin-top:4px;">recent (newest first):</div>
  <div id="zp-log" style="max-height: 160px; overflow-y: auto;"></div>
</div>
"""

panel_js = f"""
<script>
window.addEventListener('load', function () {{
  var MAP_NAME = '{m.get_name()}';
  var COG_NAME = '{cog_layer.get_name()}';

  function tryInit() {{
    var map = window[MAP_NAME];
    var cog = window[COG_NAME];
    if (!map || !cog) {{ setTimeout(tryInit, 50); return; }}

    var zEl = document.getElementById('zp-zoom');
    var lastEl = document.getElementById('zp-last');
    var logEl = document.getElementById('zp-log');
    var entries = [];

    function setZoom() {{ zEl.textContent = map.getZoom(); }}
    setZoom();
    map.on('zoomend', setZoom);

    cog.on('tileloadstart', function (e) {{
      var c = e.coords;
      var s = 'z=' + c.z + ' x=' + c.x + ' y=' + c.y;
      console.log('[COG tile request] ' + s);
      lastEl.textContent = s;
      entries.unshift(s);
      if (entries.length > 30) entries.pop();
      logEl.innerHTML = entries.map(function (t) {{ return '<div>' + t + '</div>'; }}).join('');
    }});

    console.log('[zoom-panel] hooked into', MAP_NAME, COG_NAME);
  }}
  tryInit();
}});
</script>
"""

m.get_root().html.add_child(folium.Element(panel_html + panel_js))

output = Path(__file__).parent / "map.html"
m.save(str(output))

webbrowser.open(output.as_uri())
print(f"Map saved to {output}")
