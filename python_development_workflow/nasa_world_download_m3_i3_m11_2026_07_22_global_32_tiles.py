#!/usr/bin/env python3
"""
Download the NASA Worldview VIIRS M3-I3-M11 composite for one date as 32
full-resolution global tiles, then stitch them into a single global PNG.

This version intentionally downloads only:
    VIIRS_SNPP_CorrectedReflectance_BandsM3-I3-M11

It omits the Reference_Features_15m overlay from the source URL.

Tile plan:
    4 latitude bands x 8 longitude bands = 32 tiles
    45 degrees x 45 degrees per tile
    5120 px x 5120 px per tile
    final output: 40960 px x 20480 px

Requirements:
    pip install requests pillow
"""

from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import requests
from PIL import Image

# The stitched output is about 840 megapixels, so disable Pillow's safety limit.
Image.MAX_IMAGE_PIXELS = None

snapshotTime = "2026-07-22T00:00:00Z"
apiUrl = "https://wvs.earthdata.nasa.gov/api/v1/snapshot"

layerName = "bandsM3I3M11"
layerIdentifier = "VIIRS_SNPP_CorrectedReflectance_BandsM3-I3-M11"
layerWrap = "day"
layerColormaps = ""

tileDegrees = 45
tilePixels = 5120
workers = 6
retries = 4
timeoutSeconds = 300

outputPath = Path("bandsM3I3M11_2026_07_22_global.png")
tilesDirectory = Path("bandsM3I3M11_2026_07_22_global_tiles")

# Latitude bands are ordered north to south so row 0 is the top of the image.
latitudeBands: List[Tuple[int, int]] = [
    (latitude - tileDegrees, latitude) for latitude in range(90, -90, -tileDegrees)
]

# Longitude bands are ordered west to east so column 0 is the left of the image.
longitudeBands: List[Tuple[int, int]] = [
    (longitude, longitude + tileDegrees) for longitude in range(-180, 180, tileDegrees)
]

rowCount = len(latitudeBands)
columnCount = len(longitudeBands)

TileJob = Dict[str, int]


def buildTilePath(minimumLatitude: int, minimumLongitude: int) -> Path:
    """Create the path for one cached tile."""
    return tilesDirectory / f"tile_lat{minimumLatitude:+04d}_lon{minimumLongitude:+04d}.png"


def buildTileJobs() -> List[TileJob]:
    """Build the 32 fixed global tile requests."""
    jobs: List[TileJob] = []

    for rowIndex, (minimumLatitude, maximumLatitude) in enumerate(latitudeBands):
        for columnIndex, (minimumLongitude, maximumLongitude) in enumerate(longitudeBands):
            jobs.append(
                {
                    "minimumLatitude": minimumLatitude,
                    "minimumLongitude": minimumLongitude,
                    "maximumLatitude": maximumLatitude,
                    "maximumLongitude": maximumLongitude,
                    "rowIndex": rowIndex,
                    "columnIndex": columnIndex,
                }
            )

    return jobs


def buildRequestParams(tileJob: TileJob) -> Dict[str, str | int]:
    """Build one NASA Worldview snapshot request for a global tile."""
    bboxValue = (
        f"{tileJob['minimumLatitude']},"
        f"{tileJob['minimumLongitude']},"
        f"{tileJob['maximumLatitude']},"
        f"{tileJob['maximumLongitude']}"
    )

    return {
        "REQUEST": "GetSnapshot",
        "TIME": snapshotTime,
        "BBOX": bboxValue,
        "CRS": "EPSG:4326",
        "LAYERS": layerIdentifier,
        "WRAP": layerWrap,
        "FORMAT": "image/png",
        "WIDTH": tilePixels,
        "HEIGHT": tilePixels,
        "colormaps": layerColormaps,
        "ts": int(time.time() * 1000),
    }


def downloadTile(tileJob: TileJob) -> Tuple[Path, str]:
    """Download one tile, skipping it when a valid cached file already exists."""
    tilePath = buildTilePath(tileJob["minimumLatitude"], tileJob["minimumLongitude"])
    if tilePath.exists() and tilePath.stat().st_size > 0:
        return tilePath, "cached"

    requestParams = buildRequestParams(tileJob)
    lastError: Exception | None = None

    for attemptNumber in range(1, retries + 1):
        try:
            with requests.get(apiUrl, params=requestParams, timeout=timeoutSeconds, stream=True) as response:
                response.raise_for_status()
                contentType = response.headers.get("Content-Type", "")

                if "image" not in contentType:
                    responsePreview = response.text[:200]
                    raise RuntimeError(f"non-image response ({contentType!r}): {responsePreview}")

                temporaryPath = tilePath.with_suffix(".png.part")
                with open(temporaryPath, "wb") as fileHandle:
                    for chunk in response.iter_content(chunk_size=1 << 16):
                        if chunk:
                            fileHandle.write(chunk)

                temporaryPath.replace(tilePath)
                return tilePath, "downloaded"

        except Exception as error:
            lastError = error
            waitSeconds = 2 ** attemptNumber
            print(
                f"  retry {attemptNumber}/{retries} for {tilePath.name} in {waitSeconds}s: {error}",
                file=sys.stderr,
            )
            time.sleep(waitSeconds)

    raise RuntimeError(f"failed to download {tilePath.name}: {lastError}")


def downloadTiles(tileJobs: Iterable[TileJob]) -> List[TileJob]:
    """Download all global tiles for the composite."""
    jobs = list(tileJobs)
    tilesDirectory.mkdir(exist_ok=True)

    print(f"[{layerName}] downloading {len(jobs)} tiles into {tilesDirectory}/ with {workers} workers...")
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(downloadTile, job): job for job in jobs}
        for completedCount, future in enumerate(as_completed(futures), 1):
            tilePath, status = future.result()
            print(f"  [{completedCount:>2}/{len(jobs)}] {status:<10} {tilePath.name}")

    return jobs


def stitchTiles(tileJobs: Iterable[TileJob]) -> Path:
    """Stitch the downloaded tiles into one full-resolution global PNG."""
    outputWidth = columnCount * tilePixels
    outputHeight = rowCount * tilePixels

    print(f"[{layerName}] stitching -> {outputPath} ({outputWidth} x {outputHeight} px)")
    canvas = Image.new("RGBA", (outputWidth, outputHeight))

    for tileJob in tileJobs:
        tilePath = buildTilePath(tileJob["minimumLatitude"], tileJob["minimumLongitude"])
        pasteX = tileJob["columnIndex"] * tilePixels
        pasteY = tileJob["rowIndex"] * tilePixels

        with Image.open(tilePath) as image:
            tileImage = image.convert("RGBA")

        canvas.paste(tileImage, (pasteX, pasteY))

    canvas.save(outputPath, format="PNG", optimize=False)
    print(f"[{layerName}] saved {outputPath}")
    return outputPath


def main() -> None:
    tileJobs = buildTileJobs()
    downloadedTileJobs = downloadTiles(tileJobs)
    stitchTiles(downloadedTileJobs)


if __name__ == "__main__":
    main()
