from datetime import datetime, timedelta
import os, pandas as pd
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
import imageio.v3 as iio

from dotenv import load_dotenv
from sentinelhub import (
    SHConfig,
    DataCollection,
    SentinelHubRequest,
    BBox,
    bbox_to_dimensions,
    CRS,
    MimeType,
    MosaickingOrder,
    SentinelHubCatalog,
)
from pathlib import Path


class CopernicusService:
    def __init__(self, profile_name: str = "cdse"):
        self.config = self._create_config(profile_name)
        self.data_collection = DataCollection.SENTINEL2_L2A.define_from(
            name="s2_l2a_cdse",
            service_url="https://sh.dataspace.copernicus.eu",
        )

    def _create_config(self, profile_name: str) -> SHConfig:
        env_path = Path("data_access/copernicus_creds.env")

        if not env_path.exists():
            print("Error: copernicus_creds.env not found. Please add copernicus_creds.env with credentials.")
            raise FileNotFoundError(env_path)

        load_dotenv(env_path)
        
        config = SHConfig()

        config.sh_client_id = os.getenv("SH_CLIENT_ID")
        config.sh_client_secret = os.getenv("SH_CLIENT_SECRET")
        config.sh_token_url = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
        config.sh_base_url = "https://sh.dataspace.copernicus.eu"
        config.save("cdse")
        # Saved config can be later accessed with config = SHConfig("cdse")

        config = SHConfig("cdse")
        return config




    def fetch_sentinel2_true_color_tile(
        self,
        bbox_coordinates: list[float],
        scene_name = None,
        scene_datetime = None,
        output_dir: str | Path = "tiff_data",
        resolution: int = 10,
        mosaicking_order: Literal["leastCC", "mostRecent", "leastRecent"] = "leastCC",
    ) -> list:
        """
        Fetches a Sentinel-2 L2A true-color tile for a given bounding box.

        provide:
        - scene_datetime

        Args:
            bbox_coordinates:
                Bounding box in WGS84 format:
                [min_lon, min_lat, max_lon, max_lat]
            begin_date:

            scene_datetime:
                exact scene datetime from the Catalog API.
                narrow time interval around this timestamp is used.
            output_dir:
                Directory where the TIFF response is stored.
            resolution:
                Spatial resolution in meters.
            mosaicking_order:
                Strategy for selecting imagery within the time interval.

        Returns:
            The downloaded data as returned by SentinelHubRequest.get_data().
            Also saves the TIFF file to output_dir.
        """

        self._validate_bbox(bbox_coordinates)

        if scene_datetime is None:
            scene_datetime = input(
                "Please enter the scene datetime, e.g. 2026-04-25T10:36:54.893Z: "
            )



        if scene_datetime is not None:
            begin_date, end_date = self._time_interval_from_scene_datetime(
                scene_datetime
            )

        if begin_date is None or end_date is None:
            raise ValueError(
                "Either provide begin_date and end_date, or provide scene_datetime."
            )

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        aoi_bbox = BBox(bbox=bbox_coordinates, crs=CRS.WGS84)
        aoi_size = bbox_to_dimensions(aoi_bbox, resolution=resolution)

        evalscript_true_color = """
        //VERSION=3

        function setup() {
            return {
                input: [{
                    bands: ["B02", "B03", "B04"]
                }],
                output: {
                    bands: 3
                }
            };
        }

        function evaluatePixel(sample) {
            let factor = 3.5;
            return [
                Math.min(255, sample.B04 * factor),
                Math.min(255, sample.B03 * factor),
                Math.min(255, sample.B02 * factor)
            ];
        }
        """

        mosaicking_order_mapping = {
            "leastCC": MosaickingOrder.LEAST_CC,
            "mostRecent": MosaickingOrder.MOST_RECENT,
            "leastRecent": MosaickingOrder.LEAST_RECENT,
        }

        request = SentinelHubRequest(
            evalscript=evalscript_true_color,
            input_data=[
                SentinelHubRequest.input_data(
                    data_collection=self.data_collection,
                    time_interval=(begin_date, end_date),
                    mosaicking_order=mosaicking_order_mapping[mosaicking_order],
                )
            ],
            responses=[
                SentinelHubRequest.output_response("default", MimeType.TIFF)
            ],
            data_folder=str(output_dir),
            bbox=aoi_bbox,
            size=aoi_size,
            config=self.config,
        )

        data = request.get_data(save_data=False)
        Path("data_access/data").mkdir(parents=True, exist_ok=True)
        if scene_name:
            output_path = f'data_access/data/s2_tc_{scene_name}_{scene_datetime}.tif'
        else:
            output_path = f'data_access/data/s2_tc_{aoi_bbox}_{scene_datetime}.tif'

        iio.imwrite(output_path, data[0])

        print(f"Saved tile to: {output_path}")

        return data





    def list_available_sentinel2_scenes(
        self,
        bbox_coordinates: list[float],
        begin_date: str,
        end_date: str,
        max_cloud_cover: float | None = None,
        limit: int = 20,
    ) -> list[dict]:


        self._validate_bbox(bbox_coordinates)

        aoi_bbox = BBox(bbox=bbox_coordinates, crs=CRS.WGS84)
        catalog = SentinelHubCatalog(config=self.config)

        search_iterator = catalog.search(
            collection=self.data_collection,
            bbox=aoi_bbox,
            time=(begin_date, end_date),
            filter=(
                f"eo:cloud_cover < {max_cloud_cover}"
                if max_cloud_cover is not None
                else None
            ),
            fields={
                "include": [
                    "id",
                    "properties.datetime",
                    "properties.eo:cloud_cover",
                    "properties.platform",
                    "properties.constellation",
                ],
                "exclude": [],
            },
        )

        scenes_list = []

        for item in search_iterator:
            scenes_list.append(
                {
                    "id": item["id"],
                    "datetime": item["properties"].get("datetime"),
                    "cloud_cover": item["properties"].get("eo:cloud_cover"),
                    "platform": item["properties"].get("platform"),
                    "constellation": item["properties"].get("constellation"),
                }
            )

            if len(scenes_list) >= limit:
                break

        scenes_list.sort(
            key=lambda scene: (
                scene["cloud_cover"] is None,
                scene["cloud_cover"] if scene["cloud_cover"] is not None else 999,
            )
        )

        scenes_df = pd.DataFrame(scenes_list)

        return scenes_df


    @staticmethod
    def _validate_bbox(bbox_coordinates: list[float]) -> None:
        if len(bbox_coordinates) != 4:
            raise ValueError(
                "bbox_coordinates must be [min_lon, min_lat, max_lon, max_lat]."
            )

        min_lon, min_lat, max_lon, max_lat = bbox_coordinates

        if min_lon >= max_lon or min_lat >= max_lat:
            raise ValueError(
                "Invalid bbox: expected [min_lon, min_lat, max_lon, max_lat]."
            )

    @staticmethod
    def _time_interval_from_scene_datetime(
        scene_datetime: str,
        minutes_before: int = 2,
        minutes_after: int = 2,
    ) -> tuple[str, str]:
        """
        Converts a scene datetime into a small time interval around that timestamp.

        Example:
        2026-04-25T10:36:54.893Z
        -> 2026-04-25T10:34:54Z to 2026-04-25T10:38:54Z
        """

        dt = datetime.fromisoformat(scene_datetime.replace("Z", "+00:00"))

        start = dt - timedelta(minutes=minutes_before)
        end = dt + timedelta(minutes=minutes_after)

        return (
            start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            end.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        )
        



if __name__ == "__main__":
    from data_access import CopernicusService


    service = CopernicusService()

    bbox = [7.563229, 51.935905, 7.679443, 51.978431]
    bbox_description = "Münster"

    scenes = service.list_available_sentinel2_scenes(
        bbox_coordinates=bbox,
        begin_date="2026-04-01",
        end_date="2026-04-30",
        max_cloud_cover=30,
        limit=10,
    )

    print(scenes[["datetime", "cloud_cover", "id"]])

    service.fetch_sentinel2_true_color_tile(
        bbox_coordinates=bbox,
        #scene_datetime="2026-04-25T10:36:54.893Z",
        scene_name=bbox_description,
    )
