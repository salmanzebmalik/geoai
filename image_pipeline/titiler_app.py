from cogeo_mosaic.backends import MosaicBackend
from titiler.core.factory import TilerFactory
from titiler.mosaic.factory import MosaicTilerFactory
from titiler.pgstac.main import app

app.title = "GeoAI TiTiler"

cog = TilerFactory(router_prefix="/cog")
app.include_router(cog.router, prefix="/cog", tags=["COG (by file path)"])

mosaicjson = MosaicTilerFactory(
    backend=MosaicBackend,
    router_prefix="/mosaicjson",
    add_part=True,   # /mosaicjson/bbox image extraction
)
app.include_router(mosaicjson.router, prefix="/mosaicjson", tags=["MosaicJSON (by file path)"])
