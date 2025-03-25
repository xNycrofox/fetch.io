import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import re
import subprocess
import sys
import time
import requests
from io import BytesIO
from datetime import datetime
import tempfile
import shutil

# PyTubeFix für YouTube-Downloads
try:
    from pytubefix import YouTube
except ImportError:
    print("PyTubeFix nicht gefunden! Installiere mit: pip install pytubefix")
    import sys
    sys.exit(1)

# PIL für Thumbnails
try:
    from PIL import Image, ImageTk
except ImportError:
    print("Pillow nicht gefunden! Installiere mit: pip install pillow")
    import sys
    sys.exit(1)

class FetchioDownloader:
    def __init__(self, root):
        self.root = root
        self.root.title("Fetch.io")
        self.root.geometry("600x550")
        self.root.resizable(True, True)
        
        # Icon setzen
        icon_path = self.find_resource_path("icon.ico")
        if icon_path and os.path.exists(icon_path):
            self.root.iconbitmap(icon_path)
            # Zusätzlich als Titel-Icon setzen für bessere Sichtbarkeit
            try:
                # Für Windows: Setzt das Icon auch in der Taskleiste
                self.root.iconbitmap(default=icon_path)
            except:
                pass
        
        # Für Zeitmessungen
        self.download_start_time = None
        self.last_update_time = None
        self.last_bytes_downloaded = 0
        
        # Thumbnail 
        self.thumbnail_image = None
        
        # Menüleiste erstellen
        self.create_menu()
        
        # Standard-Download-Verzeichnis
        self.download_path = os.path.join(os.path.expanduser("~"), "Downloads")
        
        # YouTube-Objekt - MUSS vor create_widgets initialisiert werden
        self.yt = None
        
        # Verfügbare Streams speichern - MUSS vor create_widgets initialisiert werden
        self.available_video_streams = {}
        self.best_audio_stream = None
        
        # FFmpeg-Pfad suchen - MUSS vor create_widgets aufgerufen werden
        self.ffmpeg_path = self.find_ffmpeg()
        print(f"FFmpeg-Pfad: {self.ffmpeg_path}")
        
        # UI-Elemente erstellen
        self.create_widgets()
        
        # Falls FFmpeg nicht gefunden wurde, automatisch herunterladen
        if not self.ffmpeg_path:
            self.status_var.set("FFmpeg nicht gefunden. Starte automatischen Download...")
            self.root.after(100, self.download_ffmpeg)
        
        # Download-Status
        self.download_in_progress = False
        self.abort_requested = False
        self.download_thread = None
        self.last_audio_file = None  # Speichert Pfad zur letzten heruntergeladenen Audio-Datei
    
    def find_resource_path(self, filename):
        """Findet den Pfad zu einer Ressourcendatei"""
        # Prüfen, ob die Anwendung als exe ausgeführt wird
        if getattr(sys, 'frozen', False):
            # Im ausführbaren Verzeichnis suchen
            base_dir = os.path.dirname(sys.executable)
        else:
            # Im Skriptverzeichnis suchen
            base_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Verschiedene mögliche Pfade ausprobieren
        paths = [
            os.path.join(base_dir, filename),
            os.path.join(base_dir, "resources", filename),
        ]
        
        for path in paths:
            if os.path.exists(path):
                return path
        
        return None
    
    def find_ffmpeg(self):
        """FFmpeg im System finden"""
        # Definiere potenzielle FFmpeg-Pfade
        ffmpeg_paths = []
        
        # Betriebssystemspezifische Pfade hinzufügen
        if os.name == "nt":  # Windows
            ffmpeg_paths = [
                "resources/windows/bin/ffmpeg.exe",
                "resources/ffmpeg.exe",
                "ffmpeg.exe",
                os.path.join(os.path.dirname(sys.executable), "ffmpeg.exe"),
                self.find_resource_path("resources/windows/bin/ffmpeg.exe"),
                self.find_resource_path("resources/ffmpeg.exe")
            ]
        else:  # macOS/Linux
            ffmpeg_paths = [
                "resources/ffmpeg/mac/ffmpeg",
                "resources/ffmpeg",
                "ffmpeg",
                "/usr/bin/ffmpeg",
                "/usr/local/bin/ffmpeg",
                "/opt/local/bin/ffmpeg",
                "/opt/homebrew/bin/ffmpeg",
                os.path.join(os.path.dirname(sys.executable), "ffmpeg"),
                self.find_resource_path("resources/ffmpeg/mac/ffmpeg"),
                self.find_resource_path("resources/ffmpeg")
            ]
        
        # Filtere None-Werte aus der Liste
        ffmpeg_paths = [path for path in ffmpeg_paths if path]
        
        # Prüfe, ob FFmpeg an einem der Pfade verfügbar ist
        for path in ffmpeg_paths:
            try:
                # Wenn es ein relativer Pfad ist, wandle ihn in einen absoluten um
                if not os.path.isabs(path):
                    abs_path = os.path.abspath(path)
                else:
                    abs_path = path
                
                # Prüfe, ob die Datei existiert
                if os.path.exists(abs_path):
                    print(f"FFmpeg gefunden unter: {abs_path}")
                    # Teste, ob FFmpeg funktioniert
                    result = subprocess.run(
                        [abs_path, "-version"], 
                        stdout=subprocess.PIPE, 
                        stderr=subprocess.PIPE, 
                        check=False
                    )
                    if result.returncode == 0:
                        print(f"FFmpeg funktioniert: {abs_path}")
                        return abs_path
            except Exception as e:
                print(f"Fehler beim Testen von FFmpeg unter {path}: {e}")
                continue
        
        # Versuche System-FFmpeg (ohne Pfad)
        try:
            subprocess.run(
                ["ffmpeg", "-version"], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                check=False
            )
            print("System-FFmpeg gefunden")
            return "ffmpeg"
        except Exception:
            pass
        
        # FFmpeg nicht gefunden
        print("Warnung: FFmpeg nicht gefunden. MP3-Konvertierung nicht möglich.")
        return None
    
    def create_menu(self):
        """Menüleiste erstellen"""
        self.menubar = tk.Menu(self.root)
        
        # Datei-Menü
        file_menu = tk.Menu(self.menubar, tearoff=0)
        file_menu.add_command(label="Beenden", command=self.root.quit)
        self.menubar.add_cascade(label="Datei", menu=file_menu)
        
        # Ansicht-Menü
        view_menu = tk.Menu(self.menubar, tearoff=0)
        self.theme_var = tk.StringVar(value="system")
        view_menu.add_radiobutton(label="Helles Design", variable=self.theme_var, value="light", command=self.apply_theme)
        view_menu.add_radiobutton(label="Dunkles Design", variable=self.theme_var, value="dark", command=self.apply_theme)
        view_menu.add_radiobutton(label="System-Design", variable=self.theme_var, value="system", command=self.apply_theme)
        self.menubar.add_cascade(label="Ansicht", menu=view_menu)
        
        # Hilfe-Menü
        help_menu = tk.Menu(self.menubar, tearoff=0)
        help_menu.add_command(label="GitHub-Projekt", command=self.open_github)
        self.menubar.add_cascade(label="Hilfe", menu=help_menu)
        
        # Menüleiste an Root-Fenster anhängen
        self.root.config(menu=self.menubar)
    
    def open_github(self):
        """Öffnet die GitHub-Projektseite im Standardbrowser"""
        import webbrowser
        webbrowser.open("https://github.com/xNycrofox/fetch.io")
    
    def apply_theme(self):
        """Design anwenden"""
        theme = self.theme_var.get()
        
        if theme == "system":
            # Systemtheme ermitteln (Windows)
            if os.name == 'nt':
                try:
                    import winreg
                    registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
                    key = winreg.OpenKey(registry, r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize')
                    value, _ = winreg.QueryValueEx(key, 'AppsUseLightTheme')
                    theme = "light" if value == 1 else "dark"
                except Exception:
                    theme = "light"  # Fallback
            else:
                theme = "light"  # Fallback für andere Betriebssysteme
        
        try:
            import sv_ttk
            sv_ttk.set_theme(theme)
        except ImportError:
            # Fallback auf ttk-Themes
            style = ttk.Style()
            if theme == "dark":
                # Dark Mode mit Standard-ttk
                style.theme_use("clam")
                style.configure(".", 
                    background="#2E2E2E",
                    foreground="#FFFFFF",
                    fieldbackground="#3E3E3E")
                style.map("TEntry", 
                    fieldbackground=[("disabled", "#3E3E3E")])
                style.configure("TButton", 
                    background="#505050",
                    foreground="#FFFFFF")
                style.map("TButton",
                    background=[("active", "#606060")])
            else:
                # Light Mode mit Standard-ttk
                style.theme_use("clam")
                style.configure(".", 
                    background="#F0F0F0",
                    foreground="#000000",
                    fieldbackground="#FFFFFF")
                style.map("TEntry", 
                    fieldbackground=[("disabled", "#F5F5F5")])
                style.configure("TButton", 
                    background="#E0E0E0",
                    foreground="#000000")
                style.map("TButton",
                    background=[("active", "#D0D0D0")])
    
    def create_widgets(self):
        """UI-Elemente erstellen"""
        # Frame mit Padding
        main_frame = ttk.Frame(self.root, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # URL-Eingabe
        ttk.Label(main_frame, text="YouTube URL:").pack(anchor=tk.W, pady=(0, 5))
        
        url_frame = ttk.Frame(main_frame)
        url_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.url_var = tk.StringVar()
        self.url_entry = ttk.Entry(url_frame, textvariable=self.url_var, width=50)
        self.url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        fetch_button = ttk.Button(url_frame, text="🔍", width=3, command=self.fetch_video_info)
        fetch_button.pack(side=tk.LEFT, padx=(5, 0))
        
        # Format-Auswahl und Qualitätsauswahl
        format_frame = ttk.Frame(main_frame)
        format_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Linke Seite - Format-Auswahl
        format_left = ttk.Frame(format_frame)
        format_left.pack(side=tk.LEFT, padx=(0, 20))
        
        ttk.Label(format_left, text="Format:").pack(side=tk.LEFT, padx=(0, 10))
        
        self.format_var = tk.StringVar(value="mp4")
        ttk.Radiobutton(format_left, text="MP4 Video", variable=self.format_var, 
                       value="mp4", command=self.update_quality_options).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Radiobutton(format_left, text="MP3 Audio", variable=self.format_var, 
                       value="mp3", command=self.update_quality_options).pack(side=tk.LEFT)
        
        # Rechte Seite - Qualitätsauswahl
        quality_frame = ttk.Frame(format_frame)
        quality_frame.pack(side=tk.RIGHT)
        
        ttk.Label(quality_frame, text="Qualität:").pack(side=tk.LEFT, padx=(0, 10))
        
        self.quality_var = tk.StringVar(value="highest")
        self.quality_combo = ttk.Combobox(quality_frame, textvariable=self.quality_var, width=15)
        self.quality_combo["values"] = ["highest", "1080p", "720p", "480p", "360p", "240p", "144p"]
        self.quality_combo.pack(side=tk.LEFT)
        
        # Binde einen Callback an Änderungen der Qualitätsauswahl
        self.quality_combo.bind("<<ComboboxSelected>>", self.on_quality_change)
        
        # Ausgabepfad
        path_frame = ttk.Frame(main_frame)
        path_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(path_frame, text="Speicherort:").pack(side=tk.LEFT, padx=(0, 10))
        
        self.path_var = tk.StringVar(value=self.download_path)
        ttk.Entry(path_frame, textvariable=self.path_var, width=40).pack(side=tk.LEFT, 
                                                                        fill=tk.X, expand=True)
        
        ttk.Button(path_frame, text="...", width=3, 
                  command=self.browse_directory).pack(side=tk.LEFT, padx=(5, 0))
        
        # Download-Button und Abbrechen-Button
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.download_button = ttk.Button(buttons_frame, text="Download starten", 
                                         command=self.start_download)
        self.download_button.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.abort_button = ttk.Button(buttons_frame, text="✕", width=3, 
                                      command=self.abort_download)
        self.abort_button.pack(side=tk.LEFT, padx=(5, 0))
        self.abort_button["state"] = "disabled"
        
        # Status und Fortschritt
        progress_container = ttk.Frame(main_frame)
        progress_container.pack(fill=tk.X, pady=(0, 10))
        
        # Status-Label
        self.status_var = tk.StringVar(value="Bereit")
        ttk.Label(progress_container, textvariable=self.status_var).pack(anchor=tk.W, pady=(0, 5))
        
        # Fortschrittsbalken
        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_bar = ttk.Progressbar(progress_container, variable=self.progress_var, 
                                          maximum=100, mode="determinate")
        self.progress_bar.pack(fill=tk.X, pady=(0, 5))
        
        # Zeit- und Größeninformationen
        timing_frame = ttk.Frame(progress_container)
        timing_frame.pack(fill=tk.X)
        
        # Linke Spalte - Vergangene Zeit und Dateigröße
        left_info = ttk.Frame(timing_frame)
        left_info.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.elapsed_var = tk.StringVar(value="")
        ttk.Label(left_info, text="Vergangene Zeit:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Label(left_info, textvariable=self.elapsed_var).grid(row=0, column=1, sticky=tk.W)
        
        self.filesize_var = tk.StringVar(value="")
        ttk.Label(left_info, text="Dateigröße:").grid(row=1, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Label(left_info, textvariable=self.filesize_var).grid(row=1, column=1, sticky=tk.W)
        
        # Rechte Spalte - Verbleibende Zeit und Download-Geschwindigkeit
        right_info = ttk.Frame(timing_frame)
        right_info.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        
        self.remaining_var = tk.StringVar(value="")
        ttk.Label(right_info, text="Verbleibende Zeit:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Label(right_info, textvariable=self.remaining_var).grid(row=0, column=1, sticky=tk.W)
        
        self.speed_var = tk.StringVar(value="")
        ttk.Label(right_info, text="Geschwindigkeit:").grid(row=1, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Label(right_info, textvariable=self.speed_var).grid(row=1, column=1, sticky=tk.W)
        
        # Video-Info-Frame
        info_frame = ttk.LabelFrame(main_frame, text="Video-Informationen", padding=10)
        info_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        # Aufteilung in zwei Spalten: Links Infos, rechts Thumbnail
        info_columns = ttk.Frame(info_frame)
        info_columns.pack(fill=tk.BOTH, expand=True)
        
        # Linke Spalte - Textinfos
        left_column = ttk.Frame(info_columns)
        left_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # Video-Titel
        ttk.Label(left_column, text="Titel:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5), pady=(0, 5))
        self.title_var = tk.StringVar(value="-")
        ttk.Label(left_column, textvariable=self.title_var, wraplength=250).grid(row=0, column=1, sticky=tk.W)
        
        # Video-Länge
        ttk.Label(left_column, text="Länge:").grid(row=1, column=0, sticky=tk.W, padx=(0, 5), pady=(0, 5))
        self.length_var = tk.StringVar(value="-")
        ttk.Label(left_column, textvariable=self.length_var).grid(row=1, column=1, sticky=tk.W)
        
        # Video-Auflösung
        ttk.Label(left_column, text="Max. Auflösung:").grid(row=2, column=0, sticky=tk.W, padx=(0, 5))
        self.resolution_var = tk.StringVar(value="-")
        ttk.Label(left_column, textvariable=self.resolution_var).grid(row=2, column=1, sticky=tk.W)
        
        # Dateigröße
        ttk.Label(left_column, text="Größe:").grid(row=3, column=0, sticky=tk.W, padx=(0, 5), pady=(5, 0))
        self.size_var = tk.StringVar(value="-")
        ttk.Label(left_column, textvariable=self.size_var).grid(row=3, column=1, sticky=tk.W, pady=(5, 0))
        
        # Grid-Konfiguration
        left_column.columnconfigure(1, weight=1)
        
        # Rechte Spalte - Thumbnail
        right_column = ttk.Frame(info_columns)
        right_column.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        self.thumbnail_label = ttk.Label(right_column)
        self.thumbnail_label.pack(fill=tk.BOTH, expand=True)
        
        # Platzhalter-Thumbnail
        placeholder = Image.new('RGB', (240, 135), color='#f0f0f0')
        self.thumbnail_image = ImageTk.PhotoImage(placeholder)
        self.thumbnail_label.configure(image=self.thumbnail_image)
        
        # FFmpeg Status anzeigen, falls nicht gefunden
        if not self.ffmpeg_path:
            self.status_var.set("Hinweis: FFmpeg nicht gefunden. MP3-Konvertierung nicht möglich.")
            
        # Qualitätsoptionen aktualisieren
        self.update_quality_options()
        
        # Footer mit Version und Copyright
        footer_frame = ttk.Frame(main_frame)
        footer_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Version links in Arial 9
        version_label = ttk.Label(footer_frame, text="v1.0.0", font=("Arial", 9))
        version_label.pack(side=tk.LEFT)
        
        # Copyright rechts in Arial 9
        copyright_label = ttk.Label(footer_frame, text="© xNycrofox (@github.com/xNycrofox)", font=("Arial", 9))
        copyright_label.pack(side=tk.RIGHT)
        
        # GitHub-Link bei Klick auf Copyright öffnen
        def open_github(event):
            import webbrowser
            webbrowser.open("https://github.com/xNycrofox")
        
        copyright_label.bind("<Button-1>", open_github)
        copyright_label.configure(cursor="hand2")  # Hand-Cursor für Klickbarkeit anzeigen
    
    def set_progress_indeterminate(self, active=True):
        """Setzt die Fortschrittsanzeige auf unbestimmten Fortschritt (Ladeanimation)"""
        if active:
            # Auf unbestimmten Modus umstellen und Animation starten
            self.progress_bar["mode"] = "indeterminate"
            # Größere Schrittweite und längerer Balken für bessere Animation
            self.progress_bar["length"] = 300
            style = ttk.Style()
            # Breiter Balken (ca. 30% der Gesamtbreite)
            style.configure("TProgressbar", thickness=20, pulsethickness=100)
            # Schnellere Animation
            self.progress_bar.start(15)
        else:
            # Animation stoppen und auf normalen Modus zurückstellen
            self.progress_bar.stop()
            self.progress_bar["mode"] = "determinate"
            # Standard-Stil wiederherstellen
            style = ttk.Style()
            style.configure("TProgressbar", thickness=20, pulsethickness=10)
            self.progress_var.set(0)  # Fortschritt zurücksetzen
        
    def update_quality_options(self):
        """Aktualisiert die Qualitätsoptionen je nach Format"""
        format_type = self.format_var.get()
        
        if format_type == "mp4":
            # Standard-Optionen beibehalten, aber später mit tatsächlichen Auflösungen aktualisieren
            self.quality_combo["values"] = ["highest", "1080p", "720p", "480p", "360p", "240p", "144p"]
            self.quality_var.set("highest")
            
            # Wenn Video-Info bereits abgerufen wurde, zeige verfügbare Qualitäten an
            if self.yt and self.available_video_streams:
                # Verfügbare Qualitätsoptionen aus den gespeicherten Streams erstellen
                quality_options = ["highest"]
                # Sortiere die Auflösungen absteigend
                resolutions = sorted(self.available_video_streams.keys(),
                                    key=lambda x: int(x.replace('p', '')),
                                    reverse=True)
                
                # In Qualitätsoptionen umwandeln
                for res in resolutions:
                    # Zeige an, ob adaptiver Stream (benötigt Muxing)
                    stream = self.available_video_streams[res]
                    if not stream.is_progressive:
                        quality_options.append(f"{res}* (beste)")
                    else:
                        quality_options.append(res)
                
                self.quality_combo["values"] = quality_options
                
                # Hinweis für "highest" anzeigen
                if resolutions:
                    highest_res = resolutions[0]
                    highest_stream = self.available_video_streams[highest_res]
                    if not highest_stream.is_progressive:
                        self.status_var.set("'Highest' = " + highest_res + "* (beste Qualität mit Audio-Kombination)")
                
                # Infotext hinzufügen, wenn adaptive Streams vorhanden sind
                elif any(not stream.is_progressive for stream in self.available_video_streams.values()):
                    self.status_var.set("* = Beste Qualität (separate Audio/Video-Streams werden kombiniert)")
        
        elif format_type == "mp3":
            self.quality_combo["values"] = ["highest", "192kbps", "128kbps", "96kbps", "64kbps"]
            self.quality_var.set("highest")
        
        # Aktualisiere die Video-Informationen für die aktuelle Qualitätsauswahl
        if self.yt:
            self.update_selected_quality_info()
    
    def on_quality_change(self, event=None):
        """Wird aufgerufen, wenn der Benutzer eine andere Qualität auswählt"""
        # Nur fortfahren, wenn bereits Video-Informationen geladen wurden
        if not self.yt:
            return
            
        # Video-Informationen für die ausgewählte Qualität aktualisieren
        self.update_selected_quality_info()
    
    def update_selected_quality_info(self):
        """Aktualisiert die Video-Informationen basierend auf der ausgewählten Qualität"""
        selected_format = self.format_var.get()
        selected_quality = self.quality_var.get()
        
        # Nur für MP4-Videos relevant
        if selected_format == "mp4":
            # Standardwerte
            size_str = "Unbekannt"
            best_resolution = self.resolution_var.get()
            
            try:
                if selected_quality == "highest":
                    # Höchste verfügbare Qualität - bereits angezeigt
                    if self.available_video_streams:
                        resolutions = sorted(self.available_video_streams.keys(), 
                                          key=lambda x: int(x.replace('p', '')), 
                                          reverse=True)
                        if resolutions:
                            highest_res = resolutions[0]
                            self.resolution_var.set(highest_res)
                            best_stream = self.available_video_streams[highest_res]
                            
                            if hasattr(best_stream, 'filesize'):
                                size_str = self.format_size(best_stream.filesize)
                                
                                # Wenn es sich um einen adaptiven Stream handelt, zeige auch die Audio-Größe an
                                if not best_stream.is_progressive and self.best_audio_stream:
                                    size_str += f" + {self.format_size(self.best_audio_stream.filesize)} (Audio)"
                elif "* (beste)" in selected_quality:
                    # Adaptive Stream (benötigt Muxing)
                    # Auflösung aus dem String extrahieren (z.B. "1080p* (beste)" -> "1080p")
                    resolution = selected_quality.split("*")[0].strip()
                    
                    # Stream aus dem Cache holen
                    if resolution in self.available_video_streams:
                        self.resolution_var.set(resolution)
                        stream = self.available_video_streams[resolution]
                        
                        if hasattr(stream, 'filesize'):
                            size_str = self.format_size(stream.filesize)
                            
                            # Wenn es sich um einen adaptiven Stream handelt, zeige auch die Audio-Größe an
                            if not stream.is_progressive and self.best_audio_stream:
                                size_str += f" + {self.format_size(self.best_audio_stream.filesize)} (Audio)"
                else:
                    # Spezifische Qualität (z.B. 1080p, 720p, etc.)
                    self.resolution_var.set(selected_quality)
                    
                    # Suche nach dem entsprechenden Stream
                    if self.yt:
                        # Zuerst progressive Streams prüfen (besser für die Anzeige)
                        stream = self.yt.streams.filter(progressive=True, file_extension="mp4", resolution=selected_quality).first()
                        
                        # Wenn kein progressiver Stream gefunden wurde, prüfe adaptive Streams
                        if not stream:
                            stream = self.yt.streams.filter(adaptive=True, file_extension="mp4", resolution=selected_quality).first()
                        
                        if stream and hasattr(stream, 'filesize'):
                            size_str = self.format_size(stream.filesize)
                            
                            # Wenn es sich um einen adaptiven Stream handelt, zeige auch die Audio-Größe an
                            if not stream.is_progressive and self.best_audio_stream:
                                size_str += f" + {self.format_size(self.best_audio_stream.filesize)} (Audio)"
                
                # Größe aktualisieren
                self.size_var.set(size_str)
                
            except Exception as e:
                print(f"Fehler beim Aktualisieren der Qualitätsinformationen: {e}")
                # Bei Fehler keine Änderung vornehmen
        
        elif selected_format == "mp3":
            # Bei MP3 die Bitrate anzeigen
            bitrate = "192kbps"  # Standardwert
            if selected_quality != "highest":
                bitrate = selected_quality
            
            # Finde den besten Audio-Stream
            if self.yt and self.best_audio_stream and hasattr(self.best_audio_stream, 'filesize'):
                size_str = self.format_size(self.best_audio_stream.filesize)
                self.size_var.set(f"{size_str} (vor Konvertierung, {bitrate})")
            else:
                self.size_var.set(f"Unbekannt ({bitrate})")
    
    def browse_directory(self):
        """Download-Verzeichnis auswählen"""
        directory = filedialog.askdirectory(
            initialdir=self.path_var.get(),
            title="Speicherort auswählen"
        )
        if directory:
            self.path_var.set(directory)
    
    def fetch_video_info(self):
        """Video-Informationen abrufen"""
        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("Fehler", "Bitte geben Sie eine YouTube-URL ein")
            return
        
        # Prüfen, ob URL gültig ist
        if not re.match(r'^(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+$', url):
            messagebox.showerror("Fehler", "Bitte geben Sie eine gültige YouTube-URL ein")
            return
        
        # Status aktualisieren
        self.status_var.set("Lade Video-Informationen...")
        
        # Stream-Cache zurücksetzen
        self.available_video_streams = {}
        self.best_audio_stream = None
        
        # Info-Thread starten
        threading.Thread(
            target=self._fetch_video_info_thread,
            args=(url,),
            daemon=True
        ).start()
    
    def _fetch_video_info_thread(self, url):
        """Video-Informationen in einem separaten Thread abrufen"""
        try:
            self.yt = YouTube(url)
            
            # Alle verfügbaren Video-Streams ermitteln und nach Auflösung gruppieren
            mp4_streams = self.yt.streams.filter(file_extension="mp4", type="video").order_by('resolution').desc()
            webm_streams = self.yt.streams.filter(file_extension="webm", type="video").order_by('resolution').desc()
            
            # Streams nach Auflösungen gruppieren (pro Auflösung den besten Stream speichern)
            video_streams_by_resolution = {}
            
            # MP4-Streams bevorzugen
            for stream in mp4_streams:
                resolution = stream.resolution
                if resolution:
                    # Wenn die Auflösung noch nicht vorhanden ist, oder ein progressiver Stream verfügbar ist
                    if resolution not in video_streams_by_resolution or stream.is_progressive:
                        video_streams_by_resolution[resolution] = stream
            
            # WebM-Streams nur hinzufügen, wenn die Auflösung noch nicht vorhanden ist
            for stream in webm_streams:
                resolution = stream.resolution
                if resolution and resolution not in video_streams_by_resolution:
                    video_streams_by_resolution[resolution] = stream
            
            # Besten Audio-Stream finden
            audio_streams = self.yt.streams.filter(only_audio=True).order_by('abr').desc()
            self.best_audio_stream = audio_streams.first() if audio_streams else None
            
            # Speichere die Streams für späteren Zugriff
            self.available_video_streams = video_streams_by_resolution
            
            # Informationen im Hauptthread anzeigen
            self.root.after(0, lambda: self.update_video_info(self.yt))
            
            # Qualitätsoptionen aktualisieren
            self.root.after(0, lambda: self.update_quality_options())
            
            # Thumbnail im Hintergrund laden
            self.load_thumbnail(self.yt.thumbnail_url)
            
        except Exception as e:
            error_message = str(e)
            self.root.after(0, lambda: messagebox.showerror("Fehler", f"Beim Abrufen der Video-Informationen ist ein Fehler aufgetreten:\n\n{error_message}"))
            self.root.after(0, lambda: self.status_var.set("Bereit"))
    
    def load_thumbnail(self, thumbnail_url):
        """Thumbnail laden und anzeigen"""
        try:
            response = requests.get(thumbnail_url)
            image_data = BytesIO(response.content)
            image = Image.open(image_data)
            
            # Auf passende Größe skalieren
            image = image.resize((240, 135), Image.LANCZOS)
            
            # In Tkinter-PhotoImage umwandeln
            photo = ImageTk.PhotoImage(image)
            
            # Bild im Hauptthread anzeigen
            self.root.after(0, lambda: self.update_thumbnail(photo))
        except Exception as e:
            print(f"Fehler beim Laden des Thumbnails: {e}")
    
    def update_thumbnail(self, photo):
        """Thumbnail in der UI aktualisieren"""
        self.thumbnail_image = photo  # Wichtig: Referenz behalten!
        self.thumbnail_label.configure(image=self.thumbnail_image)
    
    def update_video_info(self, yt):
        """Video-Informationen anzeigen"""
        # Titel
        self.title_var.set(yt.title)
        
        # Länge formatieren
        length_seconds = yt.length
        minutes, seconds = divmod(length_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        
        if hours > 0:
            self.length_var.set(f"{hours}:{minutes:02d}:{seconds:02d}")
        else:
            self.length_var.set(f"{minutes}:{seconds:02d}")
        
        # Beste verfügbare Auflösung ermitteln
        highest_resolution = "?"
        if self.available_video_streams:
            # Sortiere nach numerischer Auflösung
            resolutions = sorted(self.available_video_streams.keys(), 
                               key=lambda x: int(x.replace('p', '')), 
                               reverse=True)
            highest_resolution = resolutions[0] if resolutions else "?"
        
        self.resolution_var.set(highest_resolution)
        
        # Dateigröße
        try:
            best_stream = None
            if self.available_video_streams:
                # Nehme den Stream mit der höchsten Auflösung
                resolutions = sorted(self.available_video_streams.keys(), 
                                   key=lambda x: int(x.replace('p', '')), 
                                   reverse=True)
                best_stream = self.available_video_streams[resolutions[0]] if resolutions else None
            
            if best_stream and hasattr(best_stream, 'filesize'):
                size_str = self.format_size(best_stream.filesize)
                
                # Wenn es sich um einen adaptiven Stream handelt, zeige auch die Audio-Größe an
                if not best_stream.is_progressive and self.best_audio_stream:
                    size_str += f" + {self.format_size(self.best_audio_stream.filesize)} (Audio)"
                
                self.size_var.set(size_str)
            else:
                self.size_var.set("Unbekannt")
        except:
            self.size_var.set("Unbekannt")
        
        # Status zurücksetzen
        self.status_var.set("Bereit")
    
    def abort_download(self):
        """Download-Vorgang abbrechen"""
        if not self.download_in_progress:
            return
            
        self.abort_requested = True
        self.status_var.set("Breche Download ab...")
    
    def start_download(self):
        """Download in einem separaten Thread starten"""
        # Wenn bereits ein Download läuft, nicht erneut starten
        if self.download_in_progress:
            return
            
        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("Fehler", "Bitte geben Sie eine YouTube-URL ein")
            return
        
        # Prüfen, ob URL gültig ist
        if not re.match(r'^(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+$', url):
            messagebox.showerror("Fehler", "Bitte geben Sie eine gültige YouTube-URL ein")
            return
        
        # Download-Pfad prüfen
        output_path = self.path_var.get()
        if not os.path.isdir(output_path):
            try:
                os.makedirs(output_path)
            except Exception as e:
                messagebox.showerror("Fehler", f"Ausgabeverzeichnis konnte nicht erstellt werden: {str(e)}")
                return
        
        # Prüfen, ob MP3 gewählt wurde, aber kein FFmpeg verfügbar ist
        if self.format_var.get() == "mp3" and not self.ffmpeg_path:
            # Nachfragen, ob ohne MP3-Konvertierung fortgesetzt werden soll
            result = messagebox.askyesno(
                "Keine MP3-Konvertierung möglich",
                "FFmpeg wurde nicht gefunden, daher ist die Konvertierung zu MP3 nicht möglich.\n\n"
                "Möchten Sie stattdessen die Audiodatei im Originalformat (m4a) herunterladen?",
                icon="warning"
            )
            if not result:
                return
        
        # Prüfen ob ein adaptive Stream gewählt wurde aber kein FFmpeg vorhanden ist
        selected_quality = self.quality_var.get()
        if self.format_var.get() == "mp4" and "* (beste)" in selected_quality and not self.ffmpeg_path:
            messagebox.showerror(
                "Fehler",
                "FFmpeg wurde nicht gefunden, daher ist das Kombinieren von Video und Audio nicht möglich.\n\n"
                "Bitte wählen Sie eine andere Qualität oder installieren Sie FFmpeg."
            )
            return
        
        # UI während Download anpassen
        self.download_button["state"] = "disabled"
        self.abort_button["state"] = "normal"
        self.progress_var.set(0)
        self.status_var.set("Lade Video-Informationen...")
        
        # Zeitvariablen zurücksetzen
        self.elapsed_var.set("")
        self.remaining_var.set("")
        self.filesize_var.set("")
        self.speed_var.set("")
        
        # Videoformat und Qualität
        format_type = self.format_var.get()
        quality = self.quality_var.get()
        
        # Download-Status setzen
        self.download_in_progress = True
        self.abort_requested = False
        
        # Download-Thread starten
        self.download_thread = threading.Thread(
            target=self.download_video,
            args=(url, output_path, format_type, quality)
        )
        self.download_thread.daemon = True
        self.download_thread.start()
    
    def download_video(self, url, output_path, format_type, quality):
        """Video herunterladen (läuft in separatem Thread)"""
        try:
            # Zeitvariablen initialisieren
            self.download_start_time = time.time()
            self.last_update_time = self.download_start_time
            self.last_bytes_downloaded = 0
            
            # Fortschritts-Callback
            def progress_callback(stream, chunk, bytes_remaining):
                # Abbruch prüfen
                if self.abort_requested:
                    # PyTubefix hat keine integrierte Möglichkeit, den Download zu stoppen,
                    # daher lösen wir eine Exception aus, um den Prozess zu beenden
                    raise Exception("Download abgebrochen")
                
                total_size = stream.filesize
                bytes_downloaded = total_size - bytes_remaining
                percentage = bytes_downloaded / total_size * 100
                
                # Zeitberechnungen
                current_time = time.time()
                elapsed_time = current_time - self.download_start_time
                
                # Nur alle 0.5 Sekunden aktualisieren, um UI-Überlastung zu vermeiden
                if current_time - self.last_update_time >= 0.5:
                    # Download-Geschwindigkeit (Bytes pro Sekunde)
                    download_speed = (bytes_downloaded - self.last_bytes_downloaded) / (current_time - self.last_update_time)
                    
                    # Verbleibende Zeit schätzen
                    if download_speed > 0:
                        remaining_time = bytes_remaining / download_speed
                    else:
                        remaining_time = 0
                    
                    # UI im Hauptthread aktualisieren
                    self.root.after(0, lambda: self.update_download_progress(
                        percentage, 
                        elapsed_time, 
                        remaining_time,
                        bytes_downloaded,
                        download_speed
                    ))
                    
                    # Werte für nächste Berechnung aktualisieren
                    self.last_bytes_downloaded = bytes_downloaded
                    self.last_update_time = current_time
                else:
                    # Nur den Fortschrittsbalken aktualisieren
                    self.root.after(0, lambda: self.progress_var.set(percentage))
            
            # YouTube-Objekt erstellen
            yt = self.yt if self.yt else YouTube(url, on_progress_callback=progress_callback)
            
            # Video-Informationen im Hauptthread anzeigen, wenn noch nicht geschehen
            if not self.yt:
                self.root.after(0, lambda: self.update_video_info(yt))
            
            # Video herunterladen
            if format_type == "mp4":
                self.root.after(0, lambda: self.status_var.set("Lade Video herunter..."))
                
                # Stream basierend auf der gewählten Qualität finden
                stream = None
                requires_muxing = False
                
                if quality == "highest":
                    # Höchste verfügbare Qualität (auch adaptive Streams)
                    # Wenn wir bereits Video-Info haben, nutze die gespeicherten Streams
                    if self.available_video_streams:
                        # Nach numerischer Auflösung sortieren
                        resolutions = sorted(self.available_video_streams.keys(), 
                                          key=lambda x: int(x.replace('p', '')), 
                                          reverse=True)
                        if resolutions:
                            highest_res = resolutions[0]
                            stream = self.available_video_streams[highest_res]
                            requires_muxing = not stream.is_progressive
                        else:
                            # Fallback zur Standard-Methode
                            stream = yt.streams.get_highest_resolution()
                    else:
                        # Wenn wir noch keine Streams geladen haben, hole alle verfügbaren Streams
                        mp4_streams = yt.streams.filter(file_extension="mp4", type="video").order_by('resolution').desc()
                        webm_streams = yt.streams.filter(file_extension="webm", type="video").order_by('resolution').desc()
                        
                        all_streams = list(mp4_streams) + list(webm_streams)
                        highest_res_stream = None
                        highest_resolution_value = 0
                        
                        # Finde Stream mit höchster Auflösung
                        for stream_item in all_streams:
                            if stream_item.resolution:
                                resolution_value = int(stream_item.resolution.replace('p', ''))
                                if resolution_value > highest_resolution_value:
                                    highest_resolution_value = resolution_value
                                    highest_res_stream = stream_item
                        
                        if highest_res_stream:
                            stream = highest_res_stream
                            requires_muxing = not stream.is_progressive
                            
                            # Besten Audio-Stream finden, wenn er noch nicht gefunden wurde
                            if not self.best_audio_stream and requires_muxing:
                                audio_streams = yt.streams.filter(only_audio=True).order_by('abr').desc()
                                self.best_audio_stream = audio_streams.first() if audio_streams else None
                        else:
                            # Fallback zur Standard-Methode
                            stream = yt.streams.get_highest_resolution()
                elif "* (beste)" in quality:
                    # Adaptive Stream (benötigt Muxing)
                    # Auflösung aus dem String extrahieren (z.B. "1080p* (beste)" -> "1080p")
                    resolution = quality.split("*")[0].strip()
                    
                    # Stream aus dem Cache holen
                    if resolution in self.available_video_streams:
                        stream = self.available_video_streams[resolution]
                        requires_muxing = not stream.is_progressive
                else:
                    # Spezifische Qualität (z.B. 1080p, 720p, etc.)
                    # Zuerst versuchen wir progressive Streams (Video + Audio zusammen)
                    stream = yt.streams.filter(progressive=True, file_extension="mp4", resolution=quality).first()
                    
                    # Wenn kein passender Stream gefunden wurde, versuchen wir adaptive Streams
                    if not stream:
                        print(f"Kein progressiver Stream für {quality} gefunden, verwende adaptiven Stream...")
                        stream = yt.streams.filter(adaptive=True, file_extension="mp4", resolution=quality).first()
                        if stream:
                            requires_muxing = True
                    
                    # Wenn immer noch kein Stream gefunden wurde, fallback zur höchsten Auflösung
                    if not stream:
                        print(f"Keine {quality} Auflösung verfügbar, verwende höchste verfügbare Auflösung")
                        stream = yt.streams.get_highest_resolution()
                
                if not stream:
                    raise Exception("Kein passender Video-Stream gefunden")
                
                print(f"Ausgewählter Stream: {stream.resolution}, {stream.fps} fps, {self.format_size(stream.filesize)}")
                
                if requires_muxing and self.ffmpeg_path:
                    self.root.after(0, lambda: self.status_var.set("Lade Video herunter (Phase 1/3)..."))
                    
                    # Temporäre Dateinamen generieren
                    temp_video_file = os.path.join(tempfile.gettempdir(), f"video_{int(time.time())}.{stream.subtype}")
                    
                    # Video-Stream herunterladen
                    stream.download(output_path=tempfile.gettempdir(), filename=os.path.basename(temp_video_file))
                    
                    # Nach dem ersten Download Abbruch prüfen
                    if self.abort_requested:
                        raise Exception("Download abgebrochen")
                    
                    # Audio-Stream herunterladen
                    if self.best_audio_stream:
                        self.root.after(0, lambda: self.status_var.set("Lade Audio herunter (Phase 2/3)..."))
                        self.root.after(0, lambda: self.progress_var.set(0))  # Fortschritt zurücksetzen
                        
                        # Zeitvariablen für Audio-Download zurücksetzen
                        self.download_start_time = time.time()
                        self.last_update_time = self.download_start_time
                        self.last_bytes_downloaded = 0
                        
                        temp_audio_file = os.path.join(tempfile.gettempdir(), f"audio_{int(time.time())}.{self.best_audio_stream.subtype}")
                        self.best_audio_stream.download(output_path=tempfile.gettempdir(), filename=os.path.basename(temp_audio_file))
                        
                        # Noch einmal Abbruch prüfen
                        if self.abort_requested:
                            raise Exception("Download abgebrochen")
                            
                        # Zieldateiname generieren
                        sanitized_title = re.sub(r'[\\/*?:"<>|]', "_", yt.title)  # Ungültige Zeichen entfernen
                        output_file = os.path.join(output_path, f"{sanitized_title}.mp4")
                        
                        # Mit FFmpeg kombinieren
                        self.root.after(0, lambda: self.status_var.set("Kombiniere Video und Audio (Phase 3/3)..."))
                        self.root.after(0, lambda: self.set_progress_indeterminate(True))  # Animation starten
                        
                        combine_success = self.combine_video_audio(temp_video_file, temp_audio_file, output_file)
                        
                        # Temporäre Dateien löschen
                        try:
                            os.remove(temp_video_file)
                            os.remove(temp_audio_file)
                        except:
                            pass
                        
                        if combine_success:
                            # Animation stoppen
                            self.root.after(0, lambda: self.set_progress_indeterminate(False))
                            
                            # Download abgeschlossen
                            self.root.after(0, lambda: self.download_completed(output_file))
                        else:
                            # Animation stoppen
                            self.root.after(0, lambda: self.set_progress_indeterminate(False))
                            
                            # Fehler beim Kombinieren - Nur Video behalten
                            error_msg = "Kombinieren von Video und Audio fehlgeschlagen. Nur Video-Stream wird gespeichert."
                            # Kopiere das Video in das Ausgabeverzeichnis
                            fallback_file = os.path.join(output_path, f"{sanitized_title}_video_only.{stream.subtype}")
                            shutil.copy2(temp_video_file, fallback_file)
                            self.root.after(0, lambda: self.download_completed(fallback_file, error_msg))
                    else:
                        # Kein Audio-Stream gefunden - Nur Video speichern
                        sanitized_title = re.sub(r'[\\/*?:"<>|]', "_", yt.title)
                        fallback_file = os.path.join(output_path, f"{sanitized_title}_video_only.{stream.subtype}")
                        shutil.copy2(temp_video_file, fallback_file)
                        self.root.after(0, lambda: self.download_completed(
                            fallback_file, 
                            "Kein Audio-Stream gefunden. Nur Video wird gespeichert."
                        ))
                else:
                    # Normaler Download ohne Muxing
                    file_path = stream.download(output_path=output_path)
                    
                    # Download abgeschlossen
                    self.root.after(0, lambda: self.download_completed(file_path))
                
            elif format_type == "mp3":
                self.root.after(0, lambda: self.status_var.set("Lade Audio herunter..."))
                
                # Audio-Stream basierend auf Qualität auswählen
                stream = None
                
                if quality == "highest":
                    # Höchste Audioqualität
                    stream = yt.streams.filter(only_audio=True).order_by("abr").desc().first()
                else:
                    # Versuchen, die angegebene Audioqualität zu finden (z.B. 192kbps)
                    # Entferne "kbps" vom String für den Vergleich
                    target_abr = quality.replace("kbps", "")
                    
                    # Suche nach einem Stream mit passender Bitrate
                    audio_streams = yt.streams.filter(only_audio=True).order_by("abr").desc()
                    
                    for audio_stream in audio_streams:
                        # Extrahiere Bitrate für Vergleich (z.B. "128kbps" -> "128")
                        if hasattr(audio_stream, 'abr') and audio_stream.abr:
                            stream_abr = audio_stream.abr.replace("kbps", "")
                            if stream_abr == target_abr:
                                stream = audio_stream
                                break
                    
                    # Wenn keine exakte Übereinstimmung gefunden wurde, nimm den nächstbesten Stream
                    if not stream:
                        stream = yt.streams.filter(only_audio=True).order_by("abr").desc().first()
                
                if not stream:
                    raise Exception("Kein Audio-Stream gefunden")
                
                print(f"Ausgewählter Audio-Stream: {stream.abr if hasattr(stream, 'abr') else 'unbekannte Bitrate'}")
                
                # Audio herunterladen
                temp_file = stream.download(output_path=output_path)
                
                # Merke dir die original Audio-Datei für möglichen Abbruch
                self.last_audio_file = temp_file
                
                # Zu MP3 konvertieren wenn FFmpeg verfügbar
                if self.ffmpeg_path:
                    # MP3-Konvertierung starten
                    self.root.after(0, lambda: self.status_var.set("Konvertiere zu MP3..."))
                    
                    # Ladeanimation für Progressbar starten
                    self.root.after(0, lambda: self.set_progress_indeterminate(True))
                    
                    # Zeit- und Geschwindigkeitsanzeige während Konvertierung anpassen
                    self.root.after(0, lambda: self.elapsed_var.set("Konvertierung läuft..."))
                    self.root.after(0, lambda: self.remaining_var.set(""))
                    self.root.after(0, lambda: self.filesize_var.set(""))
                    self.root.after(0, lambda: self.speed_var.set(""))
                    
                    # Basisname für MP3-Datei
                    base_file = os.path.splitext(temp_file)[0]  # Ohne Erweiterung
                    mp3_file = base_file + ".mp3"
                    
                    # Bitrate für MP3-Konvertierung festlegen
                    bitrate = "192k"  # Standardwert
                    if quality == "192kbps":
                        bitrate = "192k"
                    elif quality == "128kbps":
                        bitrate = "128k"
                    elif quality == "96kbps":
                        bitrate = "96k"
                    elif quality == "64kbps":
                        bitrate = "64k"
                    
                    # FFmpeg-Konvertierung starten
                    conversion_success = self.convert_to_mp3(temp_file, mp3_file, bitrate)
                    
                    # Animation stoppen
                    self.root.after(0, lambda: self.set_progress_indeterminate(False))
                    
                    # Prüfen, ob Abbruch angefordert wurde
                    if self.abort_requested:
                        # Keine Fehlermeldung, stattdessen direkt den Abbruch-Prozess ausführen
                        self.root.after(0, lambda: self.download_aborted())
                    elif conversion_success:
                        # Temporäre Datei löschen
                        try:
                            os.remove(temp_file)
                            self.last_audio_file = None  # Referenz zurücksetzen
                        except:
                            pass
                        
                        # Download abgeschlossen
                        self.root.after(0, lambda: self.download_completed(mp3_file))
                    else:
                        # Echter Fehler bei der Konvertierung - Original behalten
                        error_msg = "Konvertierung zu MP3 fehlgeschlagen. Datei bleibt im Originalformat."
                        self.root.after(0, lambda: self.download_completed(temp_file, error_msg))
                else:
                    # Kein FFmpeg verfügbar, Audio im Originalformat behalten
                    self.root.after(0, lambda: self.download_completed(
                        temp_file, 
                        "FFmpeg nicht gefunden. Audio bleibt im Originalformat."
                    ))
            else:
                raise Exception(f"Unbekanntes Format: {format_type}")
                
        except Exception as e:
            # Wenn es ein Abbruch war, zeige keine Fehlermeldung
            if self.abort_requested:
                self.root.after(0, lambda: self.download_aborted())
            else:
                # Fehler im Hauptthread anzeigen
                error_message = str(e)
                self.root.after(0, lambda: self.download_error(error_message))
    
    def combine_video_audio(self, video_file, audio_file, output_file):
        """Video und Audio mit FFmpeg kombinieren"""
        if not self.ffmpeg_path:
            return False
        
        try:
            print(f"Kombiniere {video_file} und {audio_file} zu {output_file}")
            
            # Abbruch überprüfen
            if self.abort_requested:
                return False
            
            # Sicherstellen, dass die Ausgabedatei nicht schon existiert
            if os.path.exists(output_file):
                try:
                    os.remove(output_file)
                except:
                    pass
                
            # FFmpeg-Prozess starten - Windows-spezifische Flags zur Verhinderung des Konsolenfensters
            startupinfo = None
            if os.name == 'nt':
                # Importiere subprocess.STARTUPINFO in Windows
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0  # SW_HIDE

            process = subprocess.Popen(
                [
                    self.ffmpeg_path,
                    "-i", video_file,     # Video-Eingabe
                    "-i", audio_file,     # Audio-Eingabe
                    "-c:v", "copy",       # Video-Codec kopieren (keine Neucodierung)
                    "-c:a", "aac",        # Audio zu AAC konvertieren (MP4-kompatibel)
                    "-strict", "experimental",
                    "-y",                 # Überschreiben ohne Nachfrage
                    output_file
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                startupinfo=startupinfo,  # Windows-spezifisch für verstecktes Fenster
                bufsize=10**8  # Großer Buffer, um Blockieren zu vermeiden
            )
            
            # Thread zur Überwachung des Abbruch-Status
            abort_thread_active = True
            
            def check_abort():
                while abort_thread_active and process.poll() is None:
                    if self.abort_requested:
                        try:
                            process.terminate()
                            # Zeit zum Beenden geben
                            time.sleep(0.5)
                            if process.poll() is None:
                                process.kill()
                                
                            # Unvollständige Datei löschen
                            if os.path.exists(output_file):
                                os.remove(output_file)
                        except:
                            pass
                    time.sleep(0.2)
            
            # Thread starten für Abbruchüberwachung
            abort_thread = threading.Thread(target=check_abort)
            abort_thread.daemon = True
            abort_thread.start()
            
            try:
                # Auf Prozessende warten
                stdout, stderr = process.communicate()
                
                # Thread-Überwachung beenden
                abort_thread_active = False
                
                # Ergebnis überprüfen
                muxing_success = process.returncode == 0 and os.path.exists(output_file)
                
                # Bei Abbruch oder Fehler: Datei löschen
                if (not muxing_success or self.abort_requested) and os.path.exists(output_file):
                    try:
                        os.remove(output_file)
                        print(f"Fehlerhafte oder abgebrochene MP4-Datei gelöscht: {output_file}")
                    except Exception as e:
                        print(f"Fehler beim Löschen der Datei: {e}")
                
                if self.abort_requested:
                    return False
                
                print(f"Muxing erfolgreich: {muxing_success}")
                return muxing_success
            finally:
                # Sicherstellen, dass der Thread beendet wird
                abort_thread_active = False
                
        except Exception as e:
            print(f"Fehler beim Kombinieren: {e}")
            
            # Bei Ausnahme: Versuche die Datei zu löschen
            if os.path.exists(output_file):
                try:
                    os.remove(output_file)
                except:
                    pass
                
            return False
    
    def convert_to_mp3(self, input_file, output_file, bitrate="192k"):
        """MP3-Konvertierung mit FFmpeg"""
        if not self.ffmpeg_path:
            return False
        
        try:
            print(f"Konvertiere {input_file} zu MP3 mit Bitrate {bitrate}")
            
            # Abbruch prüfen
            if self.abort_requested:
                return False
                
            # Sicherstellen, dass die Ausgabedatei nicht schon existiert
            if os.path.exists(output_file):
                try:
                    os.remove(output_file)
                except:
                    pass
            
            # Windows-spezifische Flags zur Verhinderung des Konsolenfensters
            startupinfo = None
            if os.name == 'nt':
                # Importiere subprocess.STARTUPINFO in Windows
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0  # SW_HIDE
            
            # FFmpeg-Prozess starten mit optimierter Pipe-Kommunikation
            process = subprocess.Popen(
                [
                    self.ffmpeg_path,
                    "-i", input_file,     # Eingabedatei
                    "-vn",                # Keine Videospur
                    "-ab", bitrate,       # Audiobitrate
                    "-ar", "44100",       # Sample Rate
                    "-y",                 # Überschreiben ohne Nachfrage
                    output_file
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                startupinfo=startupinfo,  # Windows-spezifisch für verstecktes Fenster
                bufsize=10**8  # Großer Buffer, um Blockieren zu vermeiden
            )
            
            # Thread zur Überwachung des Abbruch-Status
            abort_thread_active = True
            
            def check_abort():
                while abort_thread_active and process.poll() is None:
                    if self.abort_requested:
                        try:
                            process.terminate()
                            # Zeit zum Beenden geben
                            time.sleep(0.5)
                            if process.poll() is None:
                                process.kill()
                                
                            # Unvollständige Datei löschen
                            if os.path.exists(output_file):
                                os.remove(output_file)
                        except:
                            pass
                    time.sleep(0.2)
            
            # Thread starten für Abbruchüberwachung
            abort_thread = threading.Thread(target=check_abort)
            abort_thread.daemon = True
            abort_thread.start()
            
            try:
                # Auf Prozessende warten
                stdout, stderr = process.communicate()
                
                # Thread-Überwachung beenden
                abort_thread_active = False
                
                # Ergebnis überprüfen
                conversion_success = process.returncode == 0 and os.path.exists(output_file)
                
                # Bei Abbruch oder Fehler: Datei löschen
                if (not conversion_success or self.abort_requested) and os.path.exists(output_file):
                    try:
                        os.remove(output_file)
                        print(f"Fehlerhafte oder abgebrochene MP3-Datei gelöscht: {output_file}")
                    except Exception as e:
                        print(f"Fehler beim Löschen der Datei: {e}")
                
                if self.abort_requested:
                    return False
                
                print(f"Konvertierung erfolgreich: {conversion_success}")
                return conversion_success
            finally:
                # Sicherstellen, dass der Thread beendet wird
                abort_thread_active = False
                
        except Exception as e:
            print(f"Fehler bei der Konvertierung: {e}")
            
            # Bei Ausnahme: Versuche die Datei zu löschen
            if os.path.exists(output_file):
                try:
                    os.remove(output_file)
                except:
                    pass
                
            return False
    
    def update_download_progress(self, percentage, elapsed_time, remaining_time, bytes_downloaded, download_speed):
        """Downloadfortschritt aktualisieren"""
        # Fortschrittsbalken
        self.progress_var.set(percentage)
        
        # Status mit Prozent
        self.status_var.set(f"Download: {percentage:.1f}%")
        
        # Zeit formatieren
        self.elapsed_var.set(self.format_time(elapsed_time))
        self.remaining_var.set(self.format_time(remaining_time))
        
        # Dateigröße und Geschwindigkeit
        self.filesize_var.set(self.format_size(bytes_downloaded))
        self.speed_var.set(f"{self.format_size(download_speed)}/s")
    
    def format_time(self, seconds):
        """Zeit formatieren"""
        if seconds < 0:
            return "--:--"
            
        minutes, seconds = divmod(int(seconds), 60)
        hours, minutes = divmod(minutes, 60)
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes}:{seconds:02d}"
    
    def format_size(self, size_bytes):
        """Dateigröße formatieren"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"
    
    def download_completed(self, file_path, message=None):
        """Download abgeschlossen"""
        self.progress_var.set(100)
        
        if message:
            self.status_var.set(message)
        else:
            self.status_var.set("Download abgeschlossen!")
        
        # Zeit- und Größen-Infos zurücksetzen
        self.elapsed_var.set("")
        self.remaining_var.set("")
        self.filesize_var.set("")
        self.speed_var.set("")
        
        # UI-Status zurücksetzen
        self.download_button["state"] = "normal"
        self.abort_button["state"] = "disabled"
        self.download_in_progress = False
        self.abort_requested = False
        self.last_audio_file = None  # Audio-Datei-Referenz zurücksetzen
        
        # Ergebnis anzeigen
        result = messagebox.askquestion(
            "Download abgeschlossen",
            f"Download abgeschlossen!\n\nDatei: {os.path.basename(file_path)}\n\nMöchten Sie den Ordner öffnen?",
            icon="info"
        )
        
        if result == "yes":
            # Ordner im Datei-Explorer öffnen
            if os.name == "nt":  # Windows
                os.startfile(os.path.dirname(file_path))
            elif os.name == "posix":  # macOS and Linux
                try:
                    subprocess.run(["open", os.path.dirname(file_path)])
                except:
                    try:
                        subprocess.run(["xdg-open", os.path.dirname(file_path)])
                    except:
                        pass
    
    def download_aborted(self):
        """Download wurde abgebrochen"""
        # Animation stoppen falls aktiv
        self.set_progress_indeterminate(False)
        
        self.progress_var.set(0)
        self.status_var.set("Download abgebrochen")
        self.download_button["state"] = "normal"
        self.abort_button["state"] = "disabled"
        
        # Bei MP3-Konvertierung auch die ursprüngliche Audiodatei löschen
        if self.last_audio_file and os.path.exists(self.last_audio_file):
            try:
                os.remove(self.last_audio_file)
                print(f"Ursprüngliche Audio-Datei nach Abbruch gelöscht: {self.last_audio_file}")
            except Exception as e:
                print(f"Fehler beim Löschen der ursprünglichen Audio-Datei: {e}")
        
        # Download-Status zurücksetzen
        self.download_in_progress = False
        self.abort_requested = False
        self.last_audio_file = None
        
        # Zeit- und Größen-Infos zurücksetzen
        self.elapsed_var.set("")
        self.remaining_var.set("")
        self.filesize_var.set("")
        self.speed_var.set("")
        
        # Temporäre Dateien und unvollständige Ausgabedateien löschen
        self.cleanup_temp_files()
        
        # Prüfen, ob es unvollständige MP4-Dateien im Zielverzeichnis gibt und diese auch löschen
        try:
            target_dir = self.path_var.get()
            for filename in os.listdir(target_dir):
                # Suche nach kürzlich erstellten MP4-Dateien, die möglicherweise unvollständig sind
                filepath = os.path.join(target_dir, filename)
                # Nur Dateien prüfen, die in den letzten 30 Sekunden erstellt/modifiziert wurden
                file_mod_time = os.path.getmtime(filepath)
                if time.time() - file_mod_time < 30 and filename.endswith('.mp4'):
                    try:
                        file_size = os.path.getsize(filepath)
                        # Wenn Datei kleiner als 1 MB ist, ist sie wahrscheinlich unvollständig
                        if file_size < 1024 * 1024:
                            os.remove(filepath)
                            print(f"Unvollständige MP4-Datei im Zielverzeichnis gelöscht: {filepath}")
                    except Exception as e:
                        print(f"Fehler beim Prüfen/Löschen der möglicherweise unvollständigen Datei: {e}")
        except Exception as e:
            print(f"Fehler beim Aufräumen des Zielverzeichnisses: {e}")
    
    def download_error(self, error_message):
        """Fehler anzeigen"""
        # Animation stoppen falls aktiv
        self.set_progress_indeterminate(False)
        
        self.progress_var.set(0)
        self.status_var.set(f"Fehler: {error_message}")
        self.download_button["state"] = "normal"
        self.abort_button["state"] = "disabled"
        
        # Bei MP3-Konvertierungsfehlern auch die ursprüngliche Audiodatei löschen, wenn gewünscht
        if self.last_audio_file and os.path.exists(self.last_audio_file):
            result = messagebox.askyesno(
                "Ursprüngliche Audio-Datei",
                f"Möchten Sie die ursprüngliche Audio-Datei behalten?\n\n{os.path.basename(self.last_audio_file)}",
                icon="question"
            )
            if not result:  # Wenn nein (nicht behalten)
                try:
                    os.remove(self.last_audio_file)
                    print(f"Ursprüngliche Audio-Datei nach Fehler gelöscht: {self.last_audio_file}")
                except Exception as e:
                    print(f"Fehler beim Löschen der ursprünglichen Audio-Datei: {e}")
        
        # Download-Status zurücksetzen
        self.download_in_progress = False
        self.abort_requested = False
        self.last_audio_file = None
        
        # Zeit- und Größen-Infos zurücksetzen
        self.elapsed_var.set("")
        self.remaining_var.set("")
        self.filesize_var.set("")
        self.speed_var.set("")
        
        # Temporäre Dateien löschen (falls vorhanden)
        self.cleanup_temp_files()
        
        messagebox.showerror("Download-Fehler", f"Beim Download ist ein Fehler aufgetreten:\n\n{error_message}")
    
    def cleanup_temp_files(self):
        """Temporäre Dateien löschen"""
        try:
            temp_dir = tempfile.gettempdir()
            removed_files = 0
            failed_files = 0
            
            # Lösche alle temporären Dateien, die von Fetch.io erstellt wurden
            for filename in os.listdir(temp_dir):
                # Video, Audio oder teilweise fertige Ausgabedateien
                if (filename.startswith(("video_", "audio_")) and 
                    any(filename.endswith(ext) for ext in ['.mp4', '.webm', '.mp3', '.m4a', '.part'])):
                    try:
                        filepath = os.path.join(temp_dir, filename)
                        
                        # Versuche bis zu 3 Mal zu löschen (für den Fall, dass die Datei noch verwendet wird)
                        for attempt in range(3):
                            try:
                                os.remove(filepath)
                                print(f"Temporäre Datei gelöscht: {filepath}")
                                removed_files += 1
                                break
                            except PermissionError:
                                # Datei ist noch in Verwendung, kurz warten und erneut versuchen
                                time.sleep(0.5)
                            except Exception as e:
                                print(f"Fehler beim Löschen von {filename}: {e}")
                                failed_files += 1
                                break
                    except Exception as e:
                        print(f"Fehler beim Zugriff auf {filename}: {e}")
                        failed_files += 1
            
            if removed_files > 0:
                print(f"{removed_files} temporäre Dateien wurden erfolgreich gelöscht.")
            if failed_files > 0:
                print(f"Bei {failed_files} temporären Dateien trat ein Fehler beim Löschen auf.")
                
        except Exception as e:
            print(f"Fehler beim Aufräumen temporärer Dateien: {e}")

    def download_ffmpeg(self):
        """Lädt FFmpeg automatisch herunter, wenn es nicht gefunden wurde"""
        # Fortschrittsanzeige anzeigen
        self.set_progress_indeterminate(True)
        
        # Zielverzeichnis für FFmpeg erstellen
        target_dir = "resources"
        os.makedirs(target_dir, exist_ok=True)
        
        if os.name == "nt":  # Windows
            target_subdir = os.path.join(target_dir, "windows", "bin")
            os.makedirs(target_subdir, exist_ok=True)
            target_file = os.path.join(target_subdir, "ffmpeg.exe")
            ffmpeg_url = "https://github.com/GyanD/codexffmpeg/releases/download/5.1.2/ffmpeg-5.1.2-essentials_build.zip"
        else:  # macOS/Linux
            if sys.platform == "darwin":  # macOS
                target_subdir = os.path.join(target_dir, "ffmpeg", "mac")
                os.makedirs(target_subdir, exist_ok=True)
                target_file = os.path.join(target_subdir, "ffmpeg")
                ffmpeg_url = "https://evermeet.cx/ffmpeg/getrelease/ffmpeg/zip"
            else:  # Linux - etwas komplizierter wegen verschiedener Architekturen
                target_subdir = os.path.join(target_dir, "ffmpeg", "linux")
                os.makedirs(target_subdir, exist_ok=True)
                target_file = os.path.join(target_subdir, "ffmpeg")
                # Für Linux empfehlen wir dem Benutzer, FFmpeg über den Paketmanager zu installieren
                ffmpeg_url = None
                self.status_var.set("Für Linux bitte FFmpeg über den Paketmanager installieren!")
                self.set_progress_indeterminate(False)
                return
        
        # Statusanzeige aktualisieren
        self.status_var.set("Lade FFmpeg herunter...")
        
        # Download-Thread starten
        threading.Thread(
            target=self._download_ffmpeg_thread,
            args=(ffmpeg_url, target_file, target_subdir),
            daemon=True
        ).start()
    
    def _download_ffmpeg_thread(self, url, target_file, target_dir):
        """Lädt FFmpeg in einem separaten Thread herunter"""
        try:
            import zipfile
            import io
            
            # FFmpeg-Archiv herunterladen
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            # Größe des Downloads ermitteln
            total_size = int(response.headers.get('content-length', 0))
            
            # Daten in Blöcken herunterladen und Fortschritt anzeigen
            zip_data = io.BytesIO()
            downloaded = 0
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    zip_data.write(chunk)
                    downloaded += len(chunk)
                    # Fortschritt berechnen und anzeigen
                    if total_size > 0:
                        percent = downloaded / total_size * 100
                        self.root.after(0, lambda p=percent: self.progress_var.set(p))
                        self.root.after(0, lambda d=downloaded: self.status_var.set(
                            f"Lade FFmpeg herunter... {self.format_size(d)} von {self.format_size(total_size)} ({percent:.1f}%)"
                        ))
            
            # Zurück zum Anfang der BytesIO-Datei
            zip_data.seek(0)
            
            # Statusanzeige aktualisieren
            self.root.after(0, lambda: self.status_var.set("Extrahiere FFmpeg..."))
            self.root.after(0, lambda: self.set_progress_indeterminate(True))
            
            # ZIP-Datei extrahieren
            with zipfile.ZipFile(zip_data) as zipf:
                # FFmpeg-Exe-Datei im ZIP suchen
                ffmpeg_exe = None
                for file in zipf.namelist():
                    if os.name == "nt":  # Windows
                        if file.endswith("ffmpeg.exe"):
                            ffmpeg_exe = file
                            break
                    else:  # macOS/Linux
                        if file.endswith("ffmpeg") and not file.endswith(".exe"):
                            ffmpeg_exe = file
                            break
                
                if ffmpeg_exe:
                    # FFmpeg-Datei extrahieren
                    with open(target_file, 'wb') as f:
                        f.write(zipf.read(ffmpeg_exe))
                    
                    # Ausführungsrechte unter macOS/Linux setzen
                    if os.name != "nt":
                        os.chmod(target_file, 0o755)
                    
                    # FFmpeg-Pfad aktualisieren
                    self.ffmpeg_path = target_file
                    
                    # Statusanzeige zurücksetzen
                    self.root.after(0, lambda: self.status_var.set("FFmpeg wurde erfolgreich installiert!"))
                    self.root.after(0, lambda: self.progress_var.set(100))
                    
                    # Nach 3 Sekunden auf "Bereit" zurücksetzen
                    self.root.after(3000, lambda: self.status_var.set("Bereit"))
                    self.root.after(3000, lambda: self.progress_var.set(0))
                else:
                    # Keine FFmpeg-Datei im ZIP gefunden
                    self.root.after(0, lambda: self.status_var.set("Fehler: FFmpeg-Datei nicht im Archiv gefunden."))
        
        except Exception as e:
            # Bei Fehler Statusanzeige aktualisieren
            self.root.after(0, lambda: self.status_var.set(f"Fehler beim Herunterladen von FFmpeg: {str(e)}"))
            print(f"Fehler beim Herunterladen von FFmpeg: {e}")
        
        finally:
            # Animation stoppen
            self.root.after(0, lambda: self.set_progress_indeterminate(False))

# Main-Funktion
def main():
    root = tk.Tk()
    app = FetchioDownloader(root)
    
    # Sun Valley Theme falls verfügbar
    try:
        import sv_ttk
        sv_ttk.set_theme("dark")
    except ImportError:
        pass
    
    root.mainloop()

if __name__ == "__main__":
    main()