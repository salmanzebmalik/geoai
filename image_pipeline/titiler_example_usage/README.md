# Example Usage

## Localhost UI
- Start by forwarding the localhost Port from the Server to your PC.
    - Run this from your machine: ssh -N -L 8000:localhost:8000 {geoai_ssh}
- Start the titiler instance on the server with the launch_titiler.sh script (first create venv_titiler)
- execute map.html for leaflet browser visualization
- map.py to rebuild map.html

## Image Extraction for Bounding Box
- Bounding Box Coordinates in EPSG4326 are used in the query.
-Example on server vs remote machine via localhost forwarding

```
curl --noproxy localhost -o munster_ger.tif "http://localhost:8000/cog/bbox/7.62121,51.94791,7.64579,51.9789.tif?url=/home/ubuntu/work/satellite_data/germany/2021/2021_08.vrt&bidx=3&bidx=2&bidx=1&rescale=0,3000"


curl --noproxy localhost -o munster_ger.tif "http://localhost:8000/mosaicjson/bbox/7.62121,51.94791,7.62179,51.94889.tif?url=/home/ubuntu/work/saved_data/collections/digital_orthofoto_nrw/mosaic.json"

curl -o munster_ortho.tif "http://localhost:8001/mosaicjson/bbox/7.62121,51.94791,7.62179,51.94889.tif?url=/home/ubuntu/work/saved_data/collections/digital_orthofoto_nrw/mosaic.json"
```

