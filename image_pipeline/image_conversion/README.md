# Image Conversion
## Germany
The provided Germany images were defined by the .vrt file, pointing at 16bit raw TIFFs. We built a single Cloud-Optimized GeoTIFF (COG) with 8bit for higher performance (as no TiTiler Rescaling is needed this way).

## NRW Orthophotos
We had 2 large COGs from 2021 and 2022, including two distinct areas from NRW (North & South). For simple usage via TiTiler as a single map, we created a mosaic.json pointing each Tile to the to be used COG.

## Sentinel Images
As the Sentinel Images span the entire planet and multiple years, we reduced them down to only the Tiles over Germany and some neighboring areas. First, the raw band-wise .jp2 files were combined into a RGB-COG per Tile and similarly to the Germany dataset, rescaled to 8bit. Contrary to the two other image sources, no combined COG map was created, due to the large possible number of date - cloud-coverage combinations.

### STAC Database
For the RGB COGs and JP2 bands of Germany, we created a STAC-Catalogue per year and pushed this into the PostGres-STAC Database. It is optimised for this type of spatial-temporal data. 
