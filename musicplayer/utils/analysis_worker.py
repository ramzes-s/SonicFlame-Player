from PySide6.QtCore import QObject, QThread, Signal
from typing import List, Optional
from pathlib import Path
import librosa
from librosa.feature.rhythm import tempo as tempo_rhythm
import numpy as np
import os
import sys
import time

# Import TrackInfo from db.py
# This requires a relative import, which can be tricky with QThreads.
# We'll assume the path is resolved correctly or handle it.
from musicplayer.core.db import TrackInfo, upsert_track, update_track_analysis


class AnalysisWorker(QThread):
    """
    Worker thread for analyzing audio files in the background.
    Extracts tempo, energy, and mood using librosa.
    """
    track_analyzed = Signal(str, float, float, float, float, float, float) # filepath, tempo, energy, mood, zero_crossing_rate, spectral_flux, hpss_ratio
    analysis_finished = Signal()
    analysis_error = Signal(str)

    def __init__(self, filepaths: List[str], duration: int = 30, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._filepaths = filepaths
        self._duration = duration
        self._is_cancelled = False

    def run(self):
        """Perform the audio analysis for each file."""
        try:
            for filepath in self._filepaths:
                if self._is_cancelled:
                    break

                start_time = time.time()
                tempo, energy, mood, zero_crossing_rate, spectral_flux, hpss_ratio = self._analyze_single_track(filepath)
                elapsed = time.time() - start_time

                # Skip if analysis took too long (> 10 seconds)
                if elapsed > 10:
                    print(f"Skipping slow file: {filepath} ({elapsed:.1f}s)")
                    tempo, energy, mood, zero_crossing_rate, spectral_flux, hpss_ratio = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

                self.track_analyzed.emit(filepath, tempo, energy, mood, zero_crossing_rate, spectral_flux, hpss_ratio)
            self.analysis_finished.emit()
        except Exception as e:
            self.analysis_error.emit(f"Error during analysis: {e}")

    def _analyze_single_track(self, filepath: str) -> tuple[float, float, float, float, float, float]:
        """
        Analyzes a single audio file for tempo, energy, mood, and hpss_ratio.
        Returns (tempo, energy, mood, zero_crossing_rate, spectral_flux, hpss_ratio).
        """
        try:
            # Skip files larger than 500MB to avoid memory/timeout issues
            file_size = os.path.getsize(filepath)
            if file_size > 500 * 1024 * 1024:
                print(f"Skipping large file: {filepath} ({file_size // (1024*1024)}MB)")
                return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

            # Load audio file - librosa expects mono audio by default
            y, sr = librosa.load(filepath, sr=None, mono=True, duration=self._duration)

            # 1. Tempo (BPM)
            tempo = tempo_rhythm(y=y, sr=sr)[0]

            # 2. Energy (Onset strength) — rhythmic density
            onset_env = librosa.onset.onset_strength(y=y, sr=sr)
            energy = float(np.mean(onset_env))
            energy = np.clip(energy / 3.0, 0, 1)

            # 3. Mood — spectral centroid (brightness), normalized
            cent = librosa.feature.spectral_centroid(y=y, sr=sr)
            mood = float(np.mean(cent))
            mood = np.clip(mood / (sr / 2) * 2.5, 0, 1)

            # 4. Zero crossing rate — noise / distortion
            zcr = librosa.feature.zero_crossing_rate(y=y)
            zero_crossing_rate = float(np.mean(zcr)) * 2.5

            # 5. Spectral flux + harmonic ratio — reuse STFT magnitude once
            spec = np.abs(librosa.stft(y=y))
            flux = np.sqrt(np.sum(np.diff(spec, axis=1)**2, axis=0))
            spectral_flux = float(np.mean(flux))

            # Harmonic ratio from spectral flatness (fast, no extra decomposition)
            flatness = librosa.feature.spectral_flatness(S=spec)
            hpss_ratio = 1.0 - float(np.mean(flatness))

            return float(tempo), float(energy), float(mood), zero_crossing_rate, spectral_flux, hpss_ratio
        except Exception as e:
            # Log error for this specific file, return default values
            print(f"Error analyzing {filepath}: {e}", file=sys.stderr)
            return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

    def cancel(self):
        """Cancel the analysis operation."""
        self._is_cancelled = True


BATCH_SIZE = 100


class AnalysisManager(QObject):
    """
    Manages background audio analysis.

    Starts AnalysisWorker on the current playlist's unanalyzed tracks.
    When the playlist batch finishes, it automatically continues with
    unanalyzed tracks from the rest of the library (BATCH_SIZE at a time).
    Calling start_analysis() with a new playlist cancels any running batch.
    """

    analysis_started = Signal()
    analysis_progress = Signal(str, int, int)  # filepath, current, total
    analysis_finished = Signal()

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._worker: Optional[AnalysisWorker] = None
        self._analyzed_count = 0
        self._total_to_analyze = 0

    def start_analysis(self, tracks: List[TrackInfo]):
        """Start analysis on the given track list (typically a playlist).

        Cancels any running worker first.  After these tracks are done,
        the manager continues with unanalyzed library tracks automatically.
        """
        self._cancel_worker()

        pending = [t for t in tracks if t.tempo == 0.0]
        if not pending:
            self._advance_to_library()
            return

        self._analyzed_count = 0
        self._total_to_analyze = len(pending)
        filepaths = [t.filepath for t in pending]

        from musicplayer.core.settings import get_analysis_duration
        duration = get_analysis_duration()

        self._worker = AnalysisWorker(filepaths, duration, self)
        self._worker.track_analyzed.connect(self._on_track_analyzed)
        self._worker.analysis_finished.connect(self._on_analysis_finished)
        self._worker.analysis_error.connect(self._on_analysis_error)
        self._worker.start()
        self.analysis_started.emit()

    def _advance_to_library(self):
        """Query next batch of unanalyzed library tracks and start worker."""
        filepaths = self._get_unanalyzed_filepaths()
        if not filepaths:
            self.analysis_finished.emit()
            return

        self._analyzed_count = 0
        self._total_to_analyze = len(filepaths)

        from musicplayer.core.settings import get_analysis_duration
        duration = get_analysis_duration()

        self._worker = AnalysisWorker(filepaths, duration, self)
        self._worker.track_analyzed.connect(self._on_track_analyzed)
        self._worker.analysis_finished.connect(self._on_analysis_finished)
        self._worker.analysis_error.connect(self._on_analysis_error)
        self._worker.start()
        self.analysis_started.emit()

    def _get_unanalyzed_filepaths(self) -> List[str]:
        """Return up to BATCH_SIZE filepaths with tempo == 0 from the library."""
        from musicplayer.core.db import get_connection
        try:
            with get_connection() as conn:
                cur = conn.execute(
                    "SELECT filepath FROM library WHERE tempo = 0 LIMIT ?",
                    (BATCH_SIZE,)
                )
                return [row[0] for row in cur.fetchall()]
        except Exception as e:
            print(f"AnalysisManager: DB query failed: {e}", file=sys.stderr)
            return []

    def _on_track_analyzed(self, filepath: str, tempo: float, energy: float, mood: float,
                           zero_crossing_rate: float = 0.0,
                           spectral_flux: float = 0.0,
                           hpss_ratio: float = 0.0):
        """Update the database and emit progress."""
        try:
            update_track_analysis(filepath, tempo, energy, mood,
                                  zero_crossing_rate, spectral_flux, hpss_ratio)
        except Exception as e:
            print(f"AnalysisManager: Failed to update DB for {filepath}: {e}", file=sys.stderr)

        self._analyzed_count += 1
        self.analysis_progress.emit(filepath, self._analyzed_count, self._total_to_analyze)

    def _on_analysis_finished(self):
        """Playlist or library batch finished — continue with library if any left."""
        self._worker = None
        self._advance_to_library()

    def _on_analysis_error(self, message: str):
        print(f"AnalysisManager: Analysis worker error: {message}", file=sys.stderr)
        self._worker = None
        self._advance_to_library()

    def _cancel_worker(self):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(500)
            self._worker = None

    def cancel_analysis(self):
        """Cancel any ongoing analysis (called on app close)."""
        self._cancel_worker()

