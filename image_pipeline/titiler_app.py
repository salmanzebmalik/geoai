from fastapi import FastAPI
from cogeo_mosaic.backends import MosaicBackend
from titiler.core.factory import TilerFactory
from titiler.mosaic.factory import MosaicTilerFactory
from titiler.core.errors import DEFAULT_STATUS_CODES, add_exception_handlers
from titiler.mosaic.errors import MOSAIC_STATUS_CODES

app = FastAPI(title="GeoAI TiTiler")

cog = TilerFactory(router_prefix="cog")
app.include_router(cog.router, prefix="/cog", tags=["COG"])

mosaic = MosaicTilerFactory(
    backend=MosaicBackend,
    router_prefix="mosaicjson",
    add_part=True,   # registers /mosaicjson/bbox and /mosaicjson/feature
)
app.include_router(mosaic.router, prefix="/mosaicjson", tags=["Mosaic"])

add_exception_handlers(app, {**DEFAULT_STATUS_CODES, **MOSAIC_STATUS_CODES})
