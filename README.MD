# Fetch.io

Ein einfacher, benutzerfreundlicher YouTube-Downloader mit einer modernen Benutzeroberfläche. Konvertiert Videos direkt in MP4- oder MP3-Format mit verschiedenen Qualitätsoptionen.


## Features

- Download von YouTube-Videos in verschiedenen Qualitäten (bis zu 1080p)
- Konvertierung in MP3 mit anpassbarer Bitrate
- Anzeige von Video-Informationen und Thumbnails
- Fortschrittsanzeige mit Download-Geschwindigkeit und verbleibender Zeit
- Dunkles und helles Thema

## Installation

### Option 1: Ausführbare Datei (Windows)

1. Laden Sie die neueste Version von der [Releases-Seite](https://github.com/xNycrofox/fetch-io/releases) herunter
2. Führen Sie `Fetch.io.exe` aus

### Option 2: Aus dem Quellcode

1. Stellen Sie sicher, dass Python 3.7 oder höher installiert ist
2. Klonen Sie das Repository: `git clone https://github.com/xNycrofox/fetch-io.git`
3. Wechseln Sie in das Verzeichnis: `cd fetch-io`
4. Installieren Sie die Abhängigkeiten: `pip install -r requirements.txt`
5. (Optional) Vorher noch ffmpeg installieren (wird ansonsten automatisch erledigt)
6. Starten Sie die Anwendung: `python fetchio.py`

## Nutzung

1. Fügen Sie die YouTube-URL ein
2. Klicken Sie auf die Lupe, um die Video-Informationen zu laden
3. Wählen Sie das gewünschte Format (MP4 oder MP3) und die Qualität
4. Wählen Sie einen Speicherort
5. Klicken Sie auf "Download starten"

## Abhängigkeiten

- Python 3.7+
- PyTubeFix (für YouTube-Downloads)
- Pillow (für Thumbnail-Anzeige)
- FFmpeg (für MP3-Konvertierung und Hochqualitäts-MP4)

## Lizenz

MIT

## Autor

- xNycrofox - [GitHub](https://github.com/xNycrofox)