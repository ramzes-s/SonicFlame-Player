from PySide6.QtCore import QObject, QThread, Signal
from typing import List, Optional
from pathlib import Path
import librosa
from librosa.feature.rhythm import tempo as tempo_rhythm # ADDED
import numpy as np
import os
import sys

# Import TrackInfo from db.py
# This requires a relative import, which can be tricky with QThreads.
# We'll assume the path is resolved correctly or handle it.
from musicplayer.core.db import TrackInfo, upsert_track, update_track_analysis


class AnalysisWorker(QThread):
    """
    Worker thread for analyzing audio files in the background.
    Extracts tempo, energy, and mood using librosa.
    """
    track_analyzed = Signal(str, float, float, float) # filepath, tempo, energy, mood
    analysis_finished = Signal()
    analysis_error = Signal(str)

    def __init__(self, filepaths: List[str], parent: Optional[QObject] = None):
        super().__init__(parent)
        self._filepaths = filepaths
        self._is_cancelled = False

    def run(self):
        """Perform the audio analysis for each file."""
        try:
            for filepath in self._filepaths:
                if self._is_cancelled:
                    break

                tempo, energy, mood = self._analyze_single_track(filepath)
                self.track_analyzed.emit(filepath, tempo, energy, mood)
            self.analysis_finished.emit()
        except Exception as e:
            self.analysis_error.emit(f"Error during analysis: {e}")

    def _analyze_single_track(self, filepath: str) -> tuple[float, float, float]:
        """
        Analyzes a single audio file for tempo, energy, and mood.
        Returns (tempo, energy, mood).
        """
        try:
            # Load audio file - librosa expects mono audio by default
            y, sr = librosa.load(filepath, sr=None, mono=True, duration=30) # Limit duration for faster analysis

            # 1. Tempo (BPM)
            tempo = tempo_rhythm(y=y, sr=sr)[0]

            # 2. Energy (RMS Energy) - Perceptual measure of intensity and activity
            # Higher RMS usually means more energetic.
            rms = librosa.feature.rms(y=y)
            energy = np.mean(rms) # Mean RMS over the track

            # 3. Mood (Valence proxy) - Using spectral centroid, normalized
            # Higher spectral centroid can correlate with brighter, happier sounds.
            cent = librosa.feature.spectral_centroid(y=y, sr=sr)
            mood = np.mean(cent) # Mean spectral centroid

            # Normalize energy and mood to a 0-1 range (approximate for now)
            # These normalizations might need calibration based on actual data
            energy = np.clip(energy * 10, 0, 1) # Scale RMS up and clip
            mood = np.clip(mood / (sr / 2) * 2, 0, 1) # Scale centroid and clip, max centroid is sr/2

            return float(tempo), float(energy), float(mood)
        except Exception as e:
            # Log error for this specific file, return default values
            print(f"Error analyzing {filepath}: {e}", file=sys.stderr)
            return 0.0, 0.0, 0.0

    def cancel(self):
        """Cancel the analysis operation."""
        self._is_cancelled = True


class AnalysisManager(QObject):
    """
    Manages background audio analysis.
    Starts AnalysisWorker and updates the database with results.
    """
    analysis_started = Signal()
    analysis_progress = Signal(str, int, int) # filepath, current, total
    analysis_finished = Signal()
    
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._worker: Optional[AnalysisWorker] = None
        self._tracks_to_analyze: List[TrackInfo] = []
        self._analyzed_count = 0
        self._total_to_analyze = 0

    def start_analysis(self, tracks: List[TrackInfo]):
        """
        Starts the analysis for tracks that need it.
        Expects a list of TrackInfo objects.
        """
        self._tracks_to_analyze = [t for t in tracks if t.tempo == 0.0] # Only analyze tracks not yet analyzed
        if not self._tracks_to_analyze:
            self.analysis_finished.emit()
            return

        self._analyzed_count = 0
        self._total_to_analyze = len(self._tracks_to_analyze)
        
        filepaths_to_analyze = [t.filepath for t in self._tracks_to_analyze]

        if self._worker:
            self._worker.cancel()
            self._worker.wait() # Wait for previous worker to finish cancelling

        self._worker = AnalysisWorker(filepaths_to_analyze, self)
        self._worker.track_analyzed.connect(self._on_track_analyzed)
        self._worker.analysis_finished.connect(self._on_analysis_finished)
        self._worker.analysis_error.connect(self._on_analysis_error)
        self._worker.start()
        self.analysis_started.emit()

    def _on_track_analyzed(self, filepath: str, tempo: float, energy: float, mood: float):
        """Slot to receive analysis results and update the database."""
        # Update the database
        try:
            # We need a function in db.py to update only analysis fields
            update_track_analysis(filepath, tempo, energy, mood)
        except Exception as e:
            print(f"AnalysisManager: Failed to update DB for {filepath}: {e}", file=sys.stderr)
        
        self._analyzed_count += 1
        self.analysis_progress.emit(filepath, self._analyzed_count, self._total_to_analyze)

    def _on_analysis_finished(self):
        """Slot for when the analysis worker finishes."""
        self._worker.quit()
        self._worker.wait()
        self._worker = None
        self.analysis_finished.emit()

    def _on_analysis_error(self, message: str):
        """Slot for errors from the analysis worker."""
        print(f"AnalysisManager: Analysis worker error: {message}", file=sys.stderr)
        # Optionally, emit analysis_finished or analysis_error to main_window
        self.analysis_finished.emit() # For now, just mark as finished

    def cancel_analysis(self):
        """Cancels any ongoing analysis."""
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait() # Wait for the thread to actually stop
            self._worker = None

