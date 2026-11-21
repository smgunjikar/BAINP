"""Local voxel-axis viewer for OASIS-2 pilot derivatives."""
#We can view mri directly in the terminal using this script. It does not modify any files or QC decisions.
#also do change it malum nahi kasi work karta hea......

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, Button
import nibabel as nib
import numpy as np


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-root", type=Path,
        default=Path.home() / "BAINP_DATA",
    )
    args = parser.parse_args()
    root = args.data_root.resolve()
    manifest = root / "derived/oasis2/conversion_pilot/conversion_manifest.json"
    entries = json.loads(manifest.read_text())["acquisitions"]
    if not entries:
        raise ValueError("No acquisitions in manifest.")

    fig, axes = plt.subplots(1, 3, figsize=(15, 8))
    fig.subplots_adjust(left=0.05, right=0.97, bottom=0.35, top=0.84)
    state = {"index": 0, "data": None, "zooms": None, "artists": []}

    # The validated pilot volumes all have this shape.
    shape = (256, 256, 128)
    sliders = []
    for axis, length in enumerate(shape):
        control = fig.add_axes([0.17, 0.25 - axis * 0.055, 0.66, 0.025])
        sliders.append(Slider(
            control, f"Voxel axis {axis}",
            0, length - 1, valinit=length // 2, valstep=1,
        ))

    contrast_axis = fig.add_axes([0.17, 0.065, 0.66, 0.025])
    contrast = Slider(
        contrast_axis, "Display gain", 0.25, 4.0, valinit=1.0
    )

    def redraw(_=None):
        data = state["data"]
        if data is None:
            return
        low, high = state["limits"]
        upper = low + (high - low) / contrast.val
        for axis, artist in enumerate(state["artists"]):
            position = int(sliders[axis].val)
            artist.set_data(np.take(data, position, axis=axis).T)
            artist.set_clim(low, upper)
            axes[axis].set_title(f"Voxel axis {axis}: slice {position}")
        fig.canvas.draw_idle()

    def load(index):
        index %= len(entries)
        entry = entries[index]
        path = (root / entry["output"].replace("\\", "/")).resolve()
        if not path.is_relative_to(root):
            raise ValueError("Invalid manifest path.")

        image = nib.load(str(path), mmap=False)
        data = image.get_fdata(dtype=np.float32, caching="unchanged")
        # Remove trailing singleton dimensions for display only.
        while data.ndim > 3 and data.shape[-1] == 1:
            data = data[..., 0]
        if data.shape != shape:
            raise ValueError(f"Unexpected pilot shape: {data.shape}")

        values = data[np.isfinite(data) & (data != 0)]
        if not values.size:
            raise ValueError("No finite nonzero voxel data.")
        low, high = np.percentile(values, [1, 99])
        if high <= low:
            raise ValueError("No usable display intensity range.")

        state.update(
            index=index, data=data,
            zooms=image.header.get_zooms()[:3],
            limits=(float(low), float(high)),
        )

        if not state["artists"]:
            for axis, panel in enumerate(axes):
                others = [i for i in range(3) if i != axis]
                aspect = (
                    float(state["zooms"][others[1]])
                    / float(state["zooms"][others[0]])
                )
                position = int(sliders[axis].val)
                artist = panel.imshow(
                    np.take(data, position, axis=axis).T,
                    cmap="gray", origin="lower",
                    interpolation="nearest", aspect=aspect,
                )
                panel.axis("off")
                state["artists"].append(artist)

        fig.suptitle(
            f"{entry['session']} | {path.name} | "
            f"Acquisition {index + 1}/{len(entries)}\n"
            "Voxel-axis view; anatomical orientation UNVERIFIED\n"
            "Contrast is display-only and normalized separately per acquisition",
            fontsize=11,
        )
        redraw()

    for slider in sliders:
        slider.on_changed(redraw)
    contrast.on_changed(redraw)

    previous = Button(fig.add_axes([0.02, 0.005, 0.14, 0.04]), "Previous")
    following = Button(fig.add_axes([0.84, 0.005, 0.14, 0.04]), "Next")
    previous.on_clicked(lambda _: load(state["index"] - 1))
    following.on_clicked(lambda _: load(state["index"] + 1))

    def scroll(event):
        if event.inaxes in axes:
            axis = list(axes).index(event.inaxes)
            slider = sliders[axis]
            change = 1 if event.button == "up" else -1
            slider.set_val(np.clip(
                slider.val + change, slider.valmin, slider.valmax
            ))

    fig.canvas.mpl_connect("scroll_event", scroll)
    load(0)
    print("Viewer opened. Close its window to return to the terminal.")
    print("No MRI files or QC decisions are modified.")
    plt.show()


if __name__ == "__main__":
    main()