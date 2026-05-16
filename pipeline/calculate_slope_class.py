from pathlib import Path

import numpy as np
import rasterio


BASE_DIR = Path(__file__).resolve().parents[1]

input_slope = BASE_DIR / "data" / "processed" / "slope.tif"
output_class = BASE_DIR / "data" / "processed" / "slope_class.tif"

output_class.parent.mkdir(parents=True, exist_ok=True)

with rasterio.open(input_slope) as src:
    slope = src.read(1)
    profile = src.profile.copy()
    nodata = src.nodata

    # Start with NoData everywhere
    output_nodata = 0
    slope_class = np.full(slope.shape, output_nodata, dtype="uint8")

    # Valid-data mask
    if nodata is not None:
        valid = slope != nodata
    else:
        valid = np.isfinite(slope)

    # Classify percent slope
    slope_class[(slope >= 0) & (slope < 5) & valid] = 1
    slope_class[(slope >= 5) & (slope < 15) & valid] = 2
    slope_class[(slope >= 15) & (slope < 25) & valid] = 3
    slope_class[(slope >= 25) & valid] = 4

    profile.update(
        dtype="uint8",
        nodata=output_nodata,
        count=1,
        compress="lzw"
    )

    with rasterio.open(output_class, "w", **profile) as dst:
        dst.write(slope_class, 1)

print(f"Created slope class raster: {output_class}")