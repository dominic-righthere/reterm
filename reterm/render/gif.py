"""GIF and video generation."""

from pathlib import Path

import imageio.v3 as iio
import numpy as np
from PIL import Image


class GIFWriter:
    """Assembles frames into animated GIF."""

    def __init__(
        self,
        output_path: Path | str,
        fps: int = 30,
        loop: int = 0,  # 0 = infinite loop
    ) -> None:
        self.output_path = Path(output_path)
        self.fps = fps
        self.loop = loop
        self.frames: list[Image.Image] = []
        self.frame_durations: list[int] = []  # ms per frame

    def add_frame(self, frame: Image.Image, duration_ms: int | None = None) -> None:
        """Add a frame to the GIF.

        Args:
            frame: PIL Image frame
            duration_ms: Duration for this frame in milliseconds (default: based on fps)
        """
        self.frames.append(frame)
        self.frame_durations.append(duration_ms or int(1000 / self.fps))

    def save(self) -> None:
        """Write GIF to disk."""
        if not self.frames:
            raise ValueError("No frames to save")

        # Convert PIL images to numpy arrays
        arrays = [np.array(f) for f in self.frames]

        # Save using imageio (duration is in milliseconds)
        iio.imwrite(
            self.output_path,
            arrays,
            extension=".gif",
            duration=self.frame_durations,
            loop=self.loop,
        )

    def save_optimized(self) -> None:
        """Save GIF with optimization (removes duplicate frames)."""
        if not self.frames:
            raise ValueError("No frames to save")

        # Deduplicate consecutive identical frames
        optimized_frames: list[Image.Image] = []
        optimized_durations: list[int] = []

        for i, frame in enumerate(self.frames):
            if i == 0:
                optimized_frames.append(frame)
                optimized_durations.append(self.frame_durations[i])
            else:
                # Compare with previous frame
                prev_frame = optimized_frames[-1]
                if self._frames_equal(frame, prev_frame):
                    # Extend previous frame duration
                    optimized_durations[-1] += self.frame_durations[i]
                else:
                    optimized_frames.append(frame)
                    optimized_durations.append(self.frame_durations[i])

        # Save optimized version
        arrays = [np.array(f) for f in optimized_frames]

        iio.imwrite(
            self.output_path,
            arrays,
            extension=".gif",
            duration=optimized_durations,
            loop=self.loop,
        )

    @staticmethod
    def _frames_equal(frame1: Image.Image, frame2: Image.Image) -> bool:
        """Check if two frames are identical."""
        if frame1.size != frame2.size:
            return False

        # Compare pixel data
        arr1 = np.array(frame1)
        arr2 = np.array(frame2)
        return np.array_equal(arr1, arr2)

    def get_total_duration(self) -> int:
        """Get total duration in milliseconds."""
        return sum(self.frame_durations)

    def get_frame_count(self) -> int:
        """Get number of frames."""
        return len(self.frames)

    def clear(self) -> None:
        """Clear all frames."""
        self.frames.clear()
        self.frame_durations.clear()


class VideoWriter:
    """Writes frames to video format (MP4, WebM)."""

    def __init__(
        self,
        output_path: Path | str,
        fps: int = 30,
        codec: str | None = None,
    ) -> None:
        self.output_path = Path(output_path)
        self.fps = fps

        # Determine codec from extension
        ext = self.output_path.suffix.lower()
        if codec:
            self.codec = codec
        elif ext == ".mp4":
            self.codec = "libx264"
        elif ext == ".webm":
            self.codec = "libvpx"
        else:
            self.codec = "libx264"

        self.frames: list[Image.Image] = []

    def add_frame(self, frame: Image.Image) -> None:
        """Add a frame to the video."""
        self.frames.append(frame)

    def save(self) -> None:
        """Write video to disk."""
        if not self.frames:
            raise ValueError("No frames to save")

        # Convert PIL images to numpy arrays
        arrays = [np.array(f) for f in self.frames]

        # Save using imageio
        iio.imwrite(
            self.output_path,
            arrays,
            fps=self.fps,
            codec=self.codec,
        )

    def clear(self) -> None:
        """Clear all frames."""
        self.frames.clear()
