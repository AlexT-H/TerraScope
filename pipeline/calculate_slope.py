import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]

GDALDEM = r"C:\Program Files\QGIS 3.44.9\bin\gdaldem.exe"

input_dem = BASE_DIR / "data" / "interim" / "franklin_county_dem_cut.tif"
output_slope = BASE_DIR / "data" / "processed" / "slope.tif"

output_slope.parent.mkdir(parents=True, exist_ok=True)

cmd = [
    GDALDEM,
    "slope",
    str(input_dem),
    str(output_slope),
    "-p",
    "-compute_edges"
]

subprocess.run(cmd, check=True)

print(f"Created slope raster: {output_slope}")