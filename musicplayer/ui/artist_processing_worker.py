"""
Artist Processing Worker

This module defines the QThread worker responsible for processing the music
library to generate data for the Artist View.
"""

import os
import shutil
import hashlib
import re
from pathlib import Path
from typing import List

from PySide6.QtCore import QThread, Signal
from PIL import Image

from musicplayer.core import db


class ArtistProcessingWorker(QThread):
    """
    A QThread worker that processes the library to find artists,
    generate collages, and build the cache for the artist view.
    """
    artist_ready = Signal(dict)
    finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.collages_dir = db.DB_DIR / "artist_collages"

    def run(self):
        """Main worker logic."""
        # --- Step 2.1: Cleanup ---
        if self.collages_dir.exists():
            shutil.rmtree(self.collages_dir)
        self.collages_dir.mkdir(parents=True, exist_ok=True)
        
        # Placeholder for missing covers
        placeholder_path = self._create_placeholder()

        # --- Step 2.2: DB Read ---
        with db.get_connection() as conn:
            cursor = conn.execute("SELECT artist, filepath FROM library")
            all_tracks = cursor.fetchall()

        # --- Step 2.3: Aggregation ---
        artists_agg = {}
        # Regex to split artist names
        split_pattern = r'\s*(?:,|\/|&|feat\.|ft\.|vs\.|vs)\s*'
        
        for artist_str, filepath in all_tracks:
            if not artist_str:
                continue
            
            # Split string into individual artists and only take the primary one
            names = [name.strip() for name in re.split(split_pattern, artist_str, flags=re.IGNORECASE) if name.strip()]
            if names:
                primary_artist = names[0]
                normalized_name = primary_artist.lower()
                
                if normalized_name not in artists_agg:
                    artists_agg[normalized_name] = {
                        "name": primary_artist, # Preserve original casing
                        "filepaths": []
                    }
                artists_agg[normalized_name]["filepaths"].append(filepath)

        # --- Step 2.4: Filter & Generate ---
        processed_artists = []
        for artist_data in artists_agg.values():
            filepaths = artist_data["filepaths"]
            display_name = artist_data["name"]

            if len(filepaths) < 3:
                continue

            # --- Collage Generation ---
            cover_paths = []
            for fp in filepaths:
                if len(cover_paths) >= 4:
                    break
                cover_data = db.ensure_cover_for_track(fp)
                if cover_data:
                    cover_paths.append(db._get_cover_path(fp))

            collage_path = self._create_collage(display_name, cover_paths, placeholder_path)

            output_data = {
                "name": display_name,
                "track_count": len(filepaths),
                "collage_path": str(collage_path)
            }
            processed_artists.append(output_data)
            self.artist_ready.emit(output_data)

        # --- Step 2.5: DB Write ---
        if processed_artists:
            db.update_artists_cache(processed_artists)

        # --- Step 2.6: Finish ---
        self.finished.emit()

    def _create_collage(self, artist_name: str, image_paths: List[Path], placeholder: Path) -> Path:
        """
        Creates a collage from a list of image paths with special logic for
        1, 2, or 3 images.
        """
        size = 200  # Size of each quadrant
        collage_size = size * 2
        
        # Load available images, falling back to placeholder if loading fails
        images = []
        for p in image_paths:
            try:
                images.append(Image.open(p).convert("RGBA"))
            except Exception:
                continue # Skip corrupted/unreadable images

        num_images = len(images)
        collage = Image.new('RGBA', (collage_size, collage_size))

        if num_images == 0:
            ph_img = Image.open(placeholder).resize((collage_size, collage_size), Image.Resampling.LANCZOS)
            collage.paste(ph_img, (0, 0))
        elif num_images == 1:
            img1 = images[0].resize((collage_size, collage_size), Image.Resampling.LANCZOS)
            collage.paste(img1, (0, 0))
        elif num_images == 2:
            img1 = images[0].resize((size, size), Image.Resampling.LANCZOS)
            img2 = images[1].resize((size, size), Image.Resampling.LANCZOS)
            collage.paste(img1, (0, 0))
            collage.paste(img2, (size, 0))
            collage.paste(img2, (0, size))
            collage.paste(img1, (size, size))
        elif num_images == 3:
            img1 = images[0].resize((size, size), Image.Resampling.LANCZOS)
            img2 = images[1].resize((size, size), Image.Resampling.LANCZOS)
            img3 = images[2].resize((size, size), Image.Resampling.LANCZOS)
            collage.paste(img1, (0, 0))
            collage.paste(img2, (size, 0))
            collage.paste(img3, (0, size))
            collage.paste(img1, (size, size))
        else: # 4 or more images
            resized_images = [img.resize((size, size), Image.Resampling.LANCZOS) for img in images[:4]]
            collage.paste(resized_images[0], (0, 0))
            collage.paste(resized_images[1], (size, 0))
            collage.paste(resized_images[2], (0, size))
            collage.paste(resized_images[3], (size, size))

        # Save the collage
        safe_name = hashlib.md5(artist_name.encode("utf-8")).hexdigest()
        output_path = self.collages_dir / f"{safe_name}.webp"
        collage.save(output_path, "WEBP", quality=80)
        
        return output_path

    def _create_placeholder(self) -> Path:
        """Creates a placeholder image and returns its path."""
        placeholder_path = self.collages_dir / "_placeholder.png"
        img = Image.new('RGBA', (10, 10), (20, 20, 20, 255))
        img.save(placeholder_path, "PNG")
        return placeholder_path
