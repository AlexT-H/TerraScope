from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterstats import zonal_stats


BASE_DIR = Path(__file__).resolve().parents[1]

# ------------------------------------------------------------
# Input paths
# ------------------------------------------------------------

PARCELS_PATH = BASE_DIR / "data" / "processed" / "parcel_access_metrics.gpkg"

RED_PATH = BASE_DIR / "data" / "interim" / "s2_b04_red_franklin_26916.tif"
NIR_PATH = BASE_DIR / "data" / "interim" / "s2_b08_nir_franklin_26916.tif"

# ------------------------------------------------------------
# Output paths
# ------------------------------------------------------------

OUTPUT_DIR = BASE_DIR / "data" / "processed"
TEMP_DIR = BASE_DIR / "data" / "interim" / "temp_ndvi"

ALIGNED_RED_PATH = TEMP_DIR / "red_aligned_to_parcels.tif"
ALIGNED_NIR_PATH = TEMP_DIR / "nir_aligned_to_parcels.tif"

NDVI_PATH = OUTPUT_DIR / "ndvi_current.tif"
OUTPUT_GPKG = OUTPUT_DIR / "parcel_ndvi_metrics.gpkg"
OUTPUT_GEOJSON = OUTPUT_DIR / "parcel_ndvi_metrics.geojson"


def check_file_exists(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Missing {label}: {path}")


def clean_geometries(gdf: gpd.GeoDataFrame, label: str) -> gpd.GeoDataFrame:
    print(f"Cleaning geometries for {label}...")

    original_count = len(gdf)

    gdf = gdf[gdf.geometry.notnull()].copy()
    gdf = gdf[~gdf.geometry.is_empty].copy()

    try:
        gdf["geometry"] = gdf.geometry.make_valid()
    except Exception:
        gdf["geometry"] = gdf.buffer(0)

    gdf = gdf[gdf.geometry.notnull()].copy()
    gdf = gdf[~gdf.geometry.is_empty].copy()

    removed = original_count - len(gdf)
    if removed > 0:
        print(f"Removed {removed} invalid/empty geometries from {label}.")

    if gdf.empty:
        raise ValueError(f"{label} has no usable geometries after cleaning.")

    return gdf


def reproject_raster_to_match_reference(
    source_path: Path,
    reference_path: Path,
    output_path: Path,
    label: str,
) -> None:
    """
    Reprojects/resamples source raster so it matches the reference raster's:
    - CRS
    - transform
    - width
    - height
    """
    print(f"Aligning {label} raster to reference grid...")

    with rasterio.open(reference_path) as ref:
        dst_crs = ref.crs
        dst_transform = ref.transform
        dst_width = ref.width
        dst_height = ref.height

    with rasterio.open(source_path) as src:
        src_array = src.read(1)

        profile = src.profile.copy()
        profile.update(
            crs=dst_crs,
            transform=dst_transform,
            width=dst_width,
            height=dst_height,
            dtype="float32",
            count=1,
            compress="lzw",
        )

        if src.nodata is not None:
            dst_nodata = src.nodata
        else:
            dst_nodata = -9999

        profile.update(nodata=dst_nodata)

        destination = np.full(
            shape=(dst_height, dst_width),
            fill_value=dst_nodata,
            dtype="float32",
        )

        reproject(
            source=src_array,
            destination=destination,
            src_transform=src.transform,
            src_crs=src.crs,
            src_nodata=src.nodata,
            dst_transform=dst_transform,
            dst_crs=dst_crs,
            dst_nodata=dst_nodata,
            resampling=Resampling.bilinear,
        )

        if output_path.exists():
            output_path.unlink()

        with rasterio.open(output_path, "w", **profile) as dst:
            dst.write(destination, 1)

    print(f"Created aligned {label}: {output_path}")


def create_reference_red_raster(
    red_path: Path,
    parcels_crs,
    output_path: Path,
) -> None:
    """
    Reprojects the red raster to the parcel CRS.
    This becomes the reference grid for the NIR raster.
    """
    print("Creating reference red raster aligned to parcel CRS...")

    with rasterio.open(red_path) as src:
        if src.crs is None:
            raise ValueError("Red raster has no CRS.")

        transform, width, height = calculate_default_transform(
            src.crs,
            parcels_crs,
            src.width,
            src.height,
            *src.bounds,
        )

        src_nodata = src.nodata
        dst_nodata = src_nodata if src_nodata is not None else -9999

        profile = src.profile.copy()
        profile.update(
            crs=parcels_crs,
            transform=transform,
            width=width,
            height=height,
            dtype="float32",
            count=1,
            nodata=dst_nodata,
            compress="lzw",
        )

        destination = np.full(
            shape=(height, width),
            fill_value=dst_nodata,
            dtype="float32",
        )

        reproject(
            source=src.read(1),
            destination=destination,
            src_transform=src.transform,
            src_crs=src.crs,
            src_nodata=src_nodata,
            dst_transform=transform,
            dst_crs=parcels_crs,
            dst_nodata=dst_nodata,
            resampling=Resampling.bilinear,
        )

        if output_path.exists():
            output_path.unlink()

        with rasterio.open(output_path, "w", **profile) as dst:
            dst.write(destination, 1)

    print(f"Created reference red raster: {output_path}")


def create_ndvi_raster(red_path: Path, nir_path: Path, output_path: Path) -> None:
    """
    Creates NDVI raster from aligned red and NIR rasters.

    NDVI = (NIR - Red) / (NIR + Red)
    """
    print("Creating NDVI raster...")

    with rasterio.open(red_path) as red_src, rasterio.open(nir_path) as nir_src:
        if red_src.crs != nir_src.crs:
            raise ValueError("Aligned Red and NIR rasters do not have the same CRS.")

        if red_src.transform != nir_src.transform:
            raise ValueError("Aligned Red and NIR rasters do not have the same transform.")

        if red_src.width != nir_src.width or red_src.height != nir_src.height:
            raise ValueError("Aligned Red and NIR rasters do not have the same dimensions.")

        red = red_src.read(1).astype("float32")
        nir = nir_src.read(1).astype("float32")

        red_nodata = red_src.nodata
        nir_nodata = nir_src.nodata

        valid = np.ones(red.shape, dtype=bool)

        if red_nodata is not None:
            valid &= red != red_nodata

        if nir_nodata is not None:
            valid &= nir != nir_nodata

        denominator = nir + red
        valid &= denominator != 0

        ndvi = np.full(red.shape, -9999, dtype="float32")
        ndvi[valid] = (nir[valid] - red[valid]) / denominator[valid]

        # Clamp numerical artifacts
        ndvi = np.where((ndvi < -1) & (ndvi != -9999), -1, ndvi)
        ndvi = np.where(ndvi > 1, 1, ndvi)

        profile = red_src.profile.copy()
        profile.update(
            dtype="float32",
            nodata=-9999,
            count=1,
            compress="lzw",
        )

        if output_path.exists():
            output_path.unlink()

        with rasterio.open(output_path, "w", **profile) as dst:
            dst.write(ndvi, 1)

    print(f"Created NDVI raster: {output_path}")


def ndvi_to_score(avg_ndvi):
    """
    Converts average NDVI to a 0-100 vegetation score.
    """
    if avg_ndvi is None or pd.isna(avg_ndvi):
        return None

    score = ((avg_ndvi - 0.1) / (0.75 - 0.1)) * 100
    score = max(0, min(score, 100))

    return round(score, 2)


def classify_vegetation(avg_ndvi):
    if avg_ndvi is None or pd.isna(avg_ndvi):
        return "Unknown"

    if avg_ndvi < 0.2:
        return "Sparse / Bare"
    elif avg_ndvi < 0.5:
        return "Moderate"
    elif avg_ndvi < 0.7:
        return "Healthy"
    else:
        return "Dense / Very Healthy"


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    print("Starting TerraScope NDVI metrics...")

    check_file_exists(PARCELS_PATH, "parcel access metrics layer")
    check_file_exists(RED_PATH, "red band raster")
    check_file_exists(NIR_PATH, "NIR band raster")

    print(f"Parcels: {PARCELS_PATH}")
    print(f"Red band: {RED_PATH}")
    print(f"NIR band: {NIR_PATH}")

    # ------------------------------------------------------------
    # Load parcels
    # ------------------------------------------------------------
    print("Loading parcels...")
    parcels = gpd.read_file(PARCELS_PATH)

    if parcels.empty:
        raise ValueError("Parcel layer is empty.")

    if parcels.crs is None:
        raise ValueError("Parcel layer has no CRS. It should be EPSG:26915.")

    parcels = clean_geometries(parcels, "parcels")

    target_crs = parcels.crs
    print(f"Target parcel CRS: {target_crs}")

    # ------------------------------------------------------------
    # Reproject/align rasters to parcel CRS
    # ------------------------------------------------------------
    create_reference_red_raster(
        red_path=RED_PATH,
        parcels_crs=target_crs,
        output_path=ALIGNED_RED_PATH,
    )

    reproject_raster_to_match_reference(
        source_path=NIR_PATH,
        reference_path=ALIGNED_RED_PATH,
        output_path=ALIGNED_NIR_PATH,
        label="NIR",
    )

    # ------------------------------------------------------------
    # Create NDVI raster
    # ------------------------------------------------------------
    create_ndvi_raster(
        red_path=ALIGNED_RED_PATH,
        nir_path=ALIGNED_NIR_PATH,
        output_path=NDVI_PATH,
    )

    # ------------------------------------------------------------
    # Calculate parcel-level NDVI stats
    # ------------------------------------------------------------
    print("Calculating parcel NDVI statistics...")

    with rasterio.open(NDVI_PATH) as src:
        ndvi_crs = src.crs
        ndvi_nodata = src.nodata

    if parcels.crs != ndvi_crs:
        print(f"Reprojecting parcels from {parcels.crs} to {ndvi_crs}...")
        parcels = parcels.to_crs(ndvi_crs)
    else:
        print("Parcel CRS matches NDVI raster CRS.")

    stats = zonal_stats(
        vectors=parcels,
        raster=str(NDVI_PATH),
        stats=["mean", "median"],
        nodata=ndvi_nodata,
        all_touched=False,
        geojson_out=False,
    )

    parcels["avg_ndvi"] = [
        round(item["mean"], 4) if item.get("mean") is not None else None
        for item in stats
    ]

    parcels["median_ndvi"] = [
        round(item["median"], 4) if item.get("median") is not None else None
        for item in stats
    ]

    # ------------------------------------------------------------
    # Vegetation score/class
    # ------------------------------------------------------------
    print("Calculating vegetation score and class...")

    parcels["vegetation_score"] = parcels["avg_ndvi"].apply(ndvi_to_score)
    parcels["vegetation_class"] = parcels["avg_ndvi"].apply(classify_vegetation)

    # ------------------------------------------------------------
    # Save outputs
    # ------------------------------------------------------------
    print("Saving outputs...")

    if OUTPUT_GPKG.exists():
        OUTPUT_GPKG.unlink()

    if OUTPUT_GEOJSON.exists():
        OUTPUT_GEOJSON.unlink()

    parcels.to_file(
        OUTPUT_GPKG,
        driver="GPKG",
        layer="parcel_ndvi_metrics",
    )

    parcels.to_file(
        OUTPUT_GEOJSON,
        driver="GeoJSON",
    )

    print("")
    print("Done.")
    print(f"Created: {NDVI_PATH}")
    print(f"Created: {OUTPUT_GPKG}")
    print(f"Created: {OUTPUT_GEOJSON}")
    print("")
    print("Temporary aligned rasters:")
    print(f"- {ALIGNED_RED_PATH}")
    print(f"- {ALIGNED_NIR_PATH}")
    print("")
    print("Fields added:")
    print("- avg_ndvi")
    print("- median_ndvi")
    print("- vegetation_score")
    print("- vegetation_class")
    print("")


if __name__ == "__main__":
    main()