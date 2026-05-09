"""
Track Info Widget Module

Displays album art with ambient blur backdrop and gradient mask,
along with track title and artist name.
"""

import math
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy
from PySide6.QtCore import Qt, QByteArray
from PySide6.QtGui import QPixmap, QPainter, QLinearGradient, QColor, QImage, QPainterPath
from PySide6.QtWidgets import QGraphicsScene, QGraphicsPixmapItem
from PySide6.QtWidgets import QGraphicsBlurEffect
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtCore import QByteArray
from musicplayer.core.db import TrackInfo
from musicplayer.ui.svg_icons import get_music_note_svg
from musicplayer.utils.helpers import get_color_from_features # ADDED


from musicplayer import config as cfg


class AlbumArtWidget(QWidget):
    """
    Album art display with ambient blur backdrop and gradient mask.
    
    The blurred background is most vibrant at top-left corner and fades
    out towards bottom-right using a transparency gradient mask.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(300, 300)
        self.setMaximumSize(500, 500)
        
        # Layout to stack album art and SVG placeholder
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setLayout(layout)

        # Main album art
        self.album_art = QPixmap()
        
        # SVG placeholder for tracks without cover art
        self.svg_placeholder = QSvgWidget()
        svg_data = get_music_note_svg(200).encode('utf-8')
        self.svg_placeholder.renderer().load(QByteArray(svg_data))
        self.svg_placeholder.setVisible(True)  # Visible by default
        layout.addWidget(self.svg_placeholder)

        # Star label - positioned manually on top
        self.star_label = QLabel(self)
        self.star_label.setStyleSheet("background: transparent;")
        self.star_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.star_label.setVisible(False)
        self.star_label.move(10, 10)

        # Analysis features for star icon
        self._tempo = 0.0
        self._energy = 0.0
        self._mood = 0.0
    
    def set_album_art(self, cover_data: bytes):
        """Load and display album cover from bytes."""
        if cover_data:
            self.album_art = QPixmap()
            self.album_art.loadFromData(cover_data)
            self.svg_placeholder.setVisible(False)
            self.update()
            
    def clear(self):
        """Clear the album art and show placeholder."""
        self.album_art = QPixmap()
        self.svg_placeholder.setVisible(True)
        self.set_analysis_features(0.0, 0.0, 0.0) # Clear features too
        self.update()

    def set_analysis_features(self, tempo: float, energy: float, mood: float):
        """Set analysis features for the star icon."""
        self._tempo = tempo
        self._energy = energy
        self._mood = mood

        if self._tempo > 0.0:
            star_size = 24
            pixmap = QPixmap(star_size, star_size)
            pixmap.fill(Qt.transparent)
            
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing, True)
            star_color = get_color_from_features(self._tempo, self._energy, self._mood)
            painter.setPen(Qt.NoPen)
            painter.setBrush(star_color)
            
            star_path = QPainterPath()
            num_points = 5
            outer_radius = star_size / 2
            inner_radius = outer_radius / 2.5
            center_x, center_y = outer_radius, outer_radius
            
            start_angle = -math.pi / 2
            angle_step = math.pi / num_points
            star_path.moveTo(
                center_x + outer_radius * math.cos(start_angle),
                center_y + outer_radius * math.sin(start_angle)
            )
            for i in range(num_points * 2):
                angle = start_angle + i * angle_step
                radius = inner_radius if i % 2 == 1 else outer_radius
                star_path.lineTo(
                    center_x + radius * math.cos(angle),
                    center_y + radius * math.sin(angle)
                )
            star_path.closeSubpath()
            painter.drawPath(star_path)
            painter.end()

            self.star_label.setPixmap(pixmap)
            self.star_label.setVisible(True)
        else:
            self.star_label.setVisible(False)

        self.update()
    
    def paintEvent(self, event):
        """
        Custom painting with gradient mask.
        
        Logic:
        1. Draw blurred backdrop with gradient transparency
        2. Draw sharp main album art on top
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        
        try:
            # Fill background with black
            painter.fillRect(self.rect(), Qt.black)
            
            if not self.album_art.isNull():
                # Scale album art to fit widget
                scaled_art = self.album_art.scaled(
                    self.size(),
                    Qt.KeepAspectRatioByExpanding,
                    Qt.SmoothTransformation
                )

                # Create blurred version for backdrop using QGraphicsScene
                blurred = self._create_blurred_pixmap(scaled_art)

                # Apply gradient mask to blurred backdrop
                blurred = self._apply_gradient_mask(blurred)

                # Draw blurred backdrop
                painter.drawPixmap(0, 0, blurred)

                # Draw sharp main art with slight opacity for blending
                painter.setOpacity(0.85)
                painter.drawPixmap(0, 0, scaled_art)
                painter.setOpacity(1.0)
                
                # Draw inner black gradient shadow so edges blend into background
                self._draw_inner_shadow(painter, self.rect())
        finally:
            painter.end()
    
    def _create_blurred_pixmap(self, pixmap: QPixmap) -> QPixmap:
        """Create a blurred version of a pixmap using QGraphicsScene."""
        scene = QGraphicsScene()
        item = QGraphicsPixmapItem(pixmap)
        scene.addItem(item)
        
        # Apply blur effect
        blur = QGraphicsBlurEffect()
        blur.setBlurRadius(40)
        item.setGraphicsEffect(blur)
        
        # Render to pixmap
        result = QPixmap(pixmap.size())
        result.fill(Qt.transparent)
        
        painter = QPainter(result)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        scene.render(painter)
        painter.end()
        
        return result
    
    def _apply_gradient_mask(self, pixmap: QPixmap) -> QPixmap:
        """
        Apply a gradient transparency mask to a pixmap.
        
        Top-left: fully opaque
        Bottom-right: fully transparent
        """
        size = pixmap.size()
        result = QPixmap(size)
        result.fill(Qt.transparent)
        
        # Create gradient from opaque to transparent
        gradient = QLinearGradient(0, 0, size.width(), size.height())
        gradient.setColorAt(0.0, QColor(255, 255, 255, 255))  # Opaque
        gradient.setColorAt(0.5, QColor(255, 255, 255, 180))  # Semi-transparent
        gradient.setColorAt(1.0, QColor(255, 255, 255, 0))    # Transparent
        
        # Draw pixmap through gradient using composition mode
        painter = QPainter(result)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        
        # First fill with gradient
        painter.fillRect(0, 0, size.width(), size.height(), gradient)
        
        # Then composite the pixmap using alpha mask
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.drawPixmap(0, 0, pixmap)
        
        # Finally draw the result over the original pixmap
        painter.setCompositionMode(QPainter.CompositionMode_DestinationOver)
        painter.drawPixmap(0, 0, pixmap)
        
        painter.end()
        
        return result
    
    def _draw_inner_shadow(self, painter: QPainter, rect):
        """
        Draw a black inner gradient shadow around all edges of the album art.
        This makes the edges blend seamlessly into the black background.
        """
        w = rect.width()
        h = rect.height()
        shadow_size = 60  # How far the shadow extends inward
        
        # Top edge
        top_gradient = QLinearGradient(0, 0, 0, shadow_size)
        top_gradient.setColorAt(0.0, QColor(0, 0, 0, 220))
        top_gradient.setColorAt(0.3, QColor(0, 0, 0, 110))
        top_gradient.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(0, 0, w, shadow_size, top_gradient)
        
        # Bottom edge
        bottom_gradient = QLinearGradient(0, h, 0, h - shadow_size)
        bottom_gradient.setColorAt(0.0, QColor(0, 0, 0, 220))
        bottom_gradient.setColorAt(0.3, QColor(0, 0, 0, 110))
        bottom_gradient.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(0, h - shadow_size, w, shadow_size, bottom_gradient)
        
        # Left edge
        left_gradient = QLinearGradient(0, 0, shadow_size, 0)
        left_gradient.setColorAt(0.0, QColor(0, 0, 0, 220))
        left_gradient.setColorAt(0.3, QColor(0, 0, 0, 110))
        left_gradient.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(0, 0, shadow_size, h, left_gradient)
        
        # Right edge
        right_gradient = QLinearGradient(w, 0, w - shadow_size, 0)
        right_gradient.setColorAt(0.0, QColor(0, 0, 0, 220))
        right_gradient.setColorAt(0.3, QColor(0, 0, 0, 110))
        right_gradient.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(w - shadow_size, 0, shadow_size, h, right_gradient)


class TrackInfoWidget(QWidget):
    """
    Combined widget showing album art and track information.
    """

    # Fixed width constraint — text will never expand beyond this
    FIXED_MAX_WIDTH = 440

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #000000;")
        self.setMaximumWidth(self.FIXED_MAX_WIDTH)

        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Album art - size constraints for the cover itself
        self.album_art_widget = AlbumArtWidget()
        self.album_art_widget.setMinimumSize(375, 375)
        self.album_art_widget.setMaximumSize(525, 525)
        layout.addWidget(self.album_art_widget, alignment=Qt.AlignCenter)

        # Track info - fonts reduced by 25%
        # Use size policy that prevents expanding beyond widget width
        text_policy = QSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        text_policy.setHorizontalStretch(0)

        self.title_label = QLabel("No Track Selected")
        self.title_label.setStyleSheet(
            f"color: {cfg.get_accent_color()}; font-size: 18px; font-weight: bold;"
        )
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setWordWrap(True)
        self.title_label.setSizePolicy(text_policy)
        self.title_label.setMinimumWidth(0)

        # Artist - same size as title (reduced by 25%)
        self.artist_label = QLabel("Unknown Artist")
        self.artist_label.setStyleSheet(
            "color: #FFFFFF; font-size: 18px; font-weight: bold;"
        )
        self.artist_label.setAlignment(Qt.AlignCenter)
        self.artist_label.setWordWrap(True)
        self.artist_label.setSizePolicy(text_policy)
        self.artist_label.setMinimumWidth(0)

        # Album - reduced by 25% (16 -> 12)
        self.album_label = QLabel("")
        self.album_label.setStyleSheet(
            "color: #AAAAAA; font-size: 12px;"
        )
        self.album_label.setAlignment(Qt.AlignCenter)
        self.album_label.setWordWrap(True)
        self.album_label.setSizePolicy(text_policy)
        self.album_label.setMinimumWidth(0)

        layout.addSpacing(12)
        layout.addWidget(self.title_label)
        layout.addWidget(self.artist_label)
        layout.addWidget(self.album_label)
        layout.addStretch()
    
    def update_track_info(self, track: TrackInfo):
        """Update display with track metadata."""
        if track:
            self.title_label.setText(track.title)
            self.artist_label.setText(track.artist)
            self.album_label.setText(track.album if track.album else "")
            
            if track.has_cover and track.cover_data:
                self.album_art_widget.set_album_art(track.cover_data)
            else:
                self.album_art_widget.clear()

            # Pass analysis features to the album art widget
            self.album_art_widget.set_analysis_features(
                tempo=getattr(track, 'tempo', 0.0),
                energy=getattr(track, 'energy', 0.0),
                mood=getattr(track, 'mood', 0.0)
            )
        else:
            self.title_label.setText("No Track Selected")
            self.artist_label.setText("Unknown Artist")
            self.album_label.setText("")
            self.album_art_widget.clear()
    
    def clear(self):
        """Reset to default state."""
        self.update_track_info(None)

    def apply_accent_color(self, color: str):
        """Update accent color for title label."""
        self.title_label.setStyleSheet(
            f"color: {color}; font-size: 18px; font-weight: bold;"
        )
