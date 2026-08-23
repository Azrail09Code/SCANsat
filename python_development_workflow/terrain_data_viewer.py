"""
Terrain Data Viewer

Load SCANsat terrain data outside of the game to let me better
debug what the hell is going on with the images.
"""

from pathlib import Path

import cv2
import numpy as np
import matplotlib.pyplot as plt

from PIL import Image
from numpy.typing import NDArray


def list_dir(folder: str | Path) -> list[Path]:
    """Scan a folder and return all folders inside."""
    folder = folder if isinstance(folder, Path) else Path(folder)
    return [f for f in folder.iterdir() if f.is_dir()]


def list_files(folder: str | Path, extension: str | None = None) -> list[Path]:
    """Scan a folder and return all files inside."""
    folder = folder if isinstance(folder, Path) else Path(folder)
    output_files = []
    for f in folder.iterdir():
        if f.is_file():
            if extension is not None:
                if f.suffix != extension:
                    continue
            output_files.append(f)
    return output_files


def generate_z_normal(x_data: NDArray, y_data: NDArray) -> NDArray:
    """Reconstruct a Z axis normal from X and Y."""
    x = x_data.astype(np.float32) / 255.0
    y = y_data.astype(np.float32) / 255.0

    # Step 2: Convert to [-1, 1]
    x_norm = 2.0 * x - 1.0
    y_norm = 2.0 * y - 1.0

    # Step 3: Reconstruct Z
    # Ensure x^2 + y^2 <= 1 to avoid NaNs due to compression artifacts
    xy_sum_sq = x_norm**2 + y_norm**2
    # Clamp to 1.0 to prevent sqrt of negative numbers
    xy_sum_sq = np.minimum(xy_sum_sq, 1.0)
    z_norm = np.sqrt(1.0 - xy_sum_sq)

    # Convert back to 0 → 255 representation
    z = (z_norm + 1.0) / 2.0
    z_data = (z * 255.0).astype(np.int8)
    return z_data


def scansat_shading(
    colour_map: NDArray, normal_map: NDArray, normal_axis: int = 2
) -> NDArray:
    """Replicate the SCANsat shading code to see what it does."""
    hls_colours = cv2.cvtColor(colour_map, cv2.COLOR_RGB2HLS)

    opacity = 0.8

    lumOver = normal_map[:, :, normal_axis].astype(np.float32) / 255.0
    lum = hls_colours[:, :, 1].astype(np.float32) / 255.0

    new_lum = np.where(
        lum > 0.5,
        (opacity * (1 - (1 - (2 * (lumOver - 0.5))) * (1 - lum))) + (1 - opacity) * lum,
        (opacity * (2 * lumOver * lum)) + (1 - opacity) * lum,
    )

    hls_colours[:, :, 1] = (new_lum * 255.0).astype(np.int8)
    return cv2.cvtColor(hls_colours, cv2.COLOR_HLS2RGB)


def detect_bodies(folder: Path) -> dict[str, Path]:
    """Find body information for values within the folder."""
    bodies = {}

    def iter_search(fpath: Path):
        dirs = list_dir(fpath)
        if "Kopernicus" in [d.stem for d in dirs]:
            bodies[fpath.stem.rsplit("_", 1)[1]] = fpath
            return
        for d in dirs:
            iter_search(d)

    iter_search(folder)
    return bodies


def main():
    sol_dir = r"C:\Users\rweld\Documents\Kerbal Space Program 1\KSP Stock RSS\GameData\Sol-Textures\PluginData"

    bodies = {}
    for f in list_dir(sol_dir):
        if f.name[0].isdigit():
            if int(f.name.split("_", 1)[0]):
                bodies.update(detect_bodies(f))

    image_fdir = r"C:\Users\rweld\Documents\Kerbal Space Program 1\KSP Stock RSS\GameData\Sol-Textures\PluginData\03_Earth-System\03-01_Luna"
    body_name = image_fdir.rsplit("_", 1)[1]

    images = {
        f.stem: f for f in list_files(Path(image_fdir) / Path("Kopernicus"), ".dds")
    }
    for i in images:
        print(f"Detected {i}")

    # Height Map
    # height_image = Image.open(images[f"{body_name}_Height"])
    # height = np.asarray(height_image)
    # print(f"Shape is {height.shape}")
    # print(f"Height Pixel values between {np.min(height)} to {np.max(height)}")

    # Normal Map
    normal_image = Image.open(images[f"{body_name}_Normal"])
    normals = np.asarray(normal_image, copy=True)
    normals[:, :, 2] = generate_z_normal(normals[:, :, 0], normals[:, :, 1])
    print(f"Normal Array is size {normals.shape}")
    print(
        f"Normal Z values between {np.min(normals[:, :, 2])} and {np.max(normals[:, :, 2])}"
    )

    # Colour Map
    colour_image = Image.open(images[f"{body_name}_Color"])
    colour = np.asarray(colour_image, copy=True)
    colour[:, :, 3] = 255  # Make image fully opaque
    print(f"Colour Array is size {colour.shape}")

    # save_data = colour
    save_data = scansat_shading(colour, normals, normal_axis=1)

    # Stock Planet Comparison

    # minmus_colour_image = Image.open(Path("images/MinmusColourDiffuse.png"))
    # minmus_colour = np.asarray(minmus_colour_image, copy=True)
    # minmus_colour[:, :, 3] = 255  # Make image fully opaque
    # print(f"Minmus Colour Map is {minmus_colour.shape[0]} x {minmus_colour.shape[1]}")

    # minmus_normal_image = Image.open(Path("images/MinmusNormalMap.png"))
    # minmus_normals = np.asarray(minmus_normal_image.resize((4096, 2048)))
    # print(f"Minmus Normal Map is {minmus_normals.shape[0]} x {minmus_normals.shape[1]}")

    # save_data = scansat_shading(minmus_colour, minmus_normals, normal_axis=1)

    # Rotate and shift to standard map projection
    save_data = np.rot90(save_data, k=2)
    term = int(save_data.shape[1] / 4)
    save_data = np.concat([save_data[:, term:, :], save_data[:, :term, :]], axis=1)
    # save_data = np.flip(save_data, 0)  # Stock Planets Only

    # Display Image
    plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
    plt.axis("off")
    Image.fromarray(save_data).save("image.png")
    plt.imshow(save_data)
    plt.show()
