import os
import sys
import locale
from pathlib import Path

BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
os.environ["PATH"] = str(BASE) + os.pathsep + os.environ.get("PATH", "")
if hasattr(os, "add_dll_directory"):
    os.add_dll_directory(str(BASE))

from PySide6.QtCore import Qt, QTimer, Signal, QSettings
from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel,
    QMainWindow, QMessageBox, QPushButton, QSlider, QSpinBox, QVBoxLayout,
    QWidget, QListWidget, QListWidgetItem, QDockWidget, QFrame, QDialog,
    QFormLayout, QKeySequenceEdit, QDialogButtonBox, QGroupBox, QProgressBar
)

locale.setlocale(locale.LC_NUMERIC, "C")
import mpv
from ac3.source import Source
from ac3.stream import Ac3Stream

APP_NAME = "DolbyDigitalPlayer Premium"
MODES = {
    "Stéréo (LoRo)": "loro",
    "Surround virtuel": "virtual",
    "Dolby Surround (LtRt)": "ltrt",
    "5.1": "5.1",
    "Mono": "mono",
}
DRCS = {"Standard": "dynrng", "Renforcée": "compr", "Désactivée": "none"}
ASPECTS = ["Auto", "16:9", "4:3", "21:9", "1:1", "Remplir (rogner)", "Étirer"]
EQ_FREQS = [60, 120, 250, 500, 1000, 2000, 4000, 8000, 12000, 16000]
DEFAULT_KEYS = {
    "play_pause": "Space", "fullscreen": "F", "next": "Ctrl+Right",
    "previous": "Ctrl+Left", "loop": "L", "mute": "M",
}

STYLE = """
QMainWindow, QWidget { background: #101319; color: #e9edf4; font-family: Segoe UI; font-size: 10pt; }
QWidget#central { background: #101319; }
QFrame#topbar, QFrame#panel { background: #191f29; border: 1px solid #293241; border-radius: 12px; }
QLabel#brand { color: #f4f7fb; font-size: 17pt; font-weight: 700; letter-spacing: 1px; }
QLabel#muted { color: #9ba8b8; }
QPushButton { background: #252e3b; color: #edf2f8; border: 1px solid #354254; border-radius: 8px; padding: 8px 13px; }
QPushButton:hover { background: #303d4e; border-color: #64758c; }
QPushButton#accent { background: #6d4aff; border-color: #8064ff; font-weight: 600; }
QPushButton#accent:hover { background: #8064ff; }
QComboBox, QSpinBox, QKeySequenceEdit { background: #202835; border: 1px solid #354254; border-radius: 7px; padding: 6px; min-height: 22px; }
QSlider::groove:horizontal { height: 5px; background: #303b4a; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #8468ff; border-radius: 2px; }
QSlider::handle:horizontal { background: #f2f4fa; width: 13px; margin: -5px 0; border-radius: 6px; }
QListWidget { background: #151b24; border: 0; outline: 0; }
QListWidget::item { padding: 9px; border-radius: 6px; }
QListWidget::item:selected { background: #342c60; color: white; }
QCheckBox { spacing: 7px; }
QProgressBar { border: 0; background: #293241; border-radius: 3px; height: 5px; }
QProgressBar::chunk { background: #8468ff; border-radius: 3px; }
QDockWidget { color: #e9edf4; }
"""

class ShortcutDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Personnaliser les raccourcis")
        self.edits = {}
        form = QFormLayout(self)
        labels = {
            "play_pause": "Lecture / Pause", "fullscreen": "Plein écran",
            "next": "Élément suivant", "previous": "Élément précédent",
            "loop": "Boucle", "mute": "Muet",
        }
        for key, label in labels.items():
            edit = QKeySequenceEdit(QKeySequence(settings.value("keys/" + key, DEFAULT_KEYS[key])))
            self.edits[key] = edit
            form.addRow(label, edit)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def values(self):
        return {k: e.keySequence().toString() for k, e in self.edits.items()}


class Player(QMainWindow):
    req = Signal(str)

    def __init__(self):
        super().__init__()
        self.settings = QSettings("DolbyDigitalPlayer", "Premium")
        self.setWindowTitle(APP_NAME)
        self.resize(1280, 820)
        self.setMinimumSize(900, 600)
        self.path = self.ext_id = self.orig_aid = self.src = self.cfg = None
        self.n = 0
        self.dur = None
        self.playlist_paths = []
        self.current_index = -1
        self.eq_values = [0] * len(EQ_FREQS)
        self.shortcuts = {}
        self._build_ui()
        self._create_player()
        self._restore_settings()
        self._install_shortcuts()
        self.req.connect(self.on_req)
        self.p.register_message_handler("ac3", lambda *a: self.req.emit(a[0] if a else ""))
        for key, act in (("f", "fullscreen"), ("ESC", "exit"), ("l", "loop"),
                         ("SPACE", "play_pause"), ("MBTN_LEFT_DBL", "fullscreen")):
            self.p.command("keybind", key, f"script-message ac3 {act}")
        self.p.register_stream_protocol("ac3dec", self.open_stream)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(250)

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(18, 14, 18, 14)
        outer.setSpacing(12)

        top = QFrame()
        top.setObjectName("topbar")
        tl = QHBoxLayout(top)
        tl.setContentsMargins(18, 12, 18, 12)
        brand = QLabel("DOLBY DIGITAL")
        brand.setObjectName("brand")
        premium = QLabel("PREMIUM")
        premium.setStyleSheet("color:#a895ff;font-weight:700;letter-spacing:2px;")
        tl.addWidget(brand)
        tl.addWidget(premium)
        tl.addStretch(1)
        self.status = QLabel("PRÊT · Ouvrez un média pour commencer")
        self.status.setObjectName("muted")
        tl.addWidget(self.status)
        outer.addWidget(top)

        self.video = QWidget()
        self.video.setStyleSheet("background:#050608;border:1px solid #293241;border-radius:10px;")
        self.video.setAttribute(Qt.WA_NativeWindow)
        outer.addWidget(self.video, 1)

        seekrow = QHBoxLayout()
        self.time_label = QLabel("00:00")
        self.time_label.setObjectName("muted")
        self.seek = QSlider(Qt.Horizontal)
        self.seek.setRange(0, 1000)
        self.total_label = QLabel("--:--")
        self.total_label.setObjectName("muted")
        seekrow.addWidget(self.time_label)
        seekrow.addWidget(self.seek, 1)
        seekrow.addWidget(self.total_label)
        outer.addLayout(seekrow)

        controls = QFrame()
        controls.setObjectName("panel")
        c = QHBoxLayout(controls)
        c.setContentsMargins(12, 10, 12, 10)
        self.open_btn = QPushButton("＋  Ouvrir")
        self.open_btn.setObjectName("accent")
        self.play_btn = QPushButton("▶  Lecture")
        self.prev_btn = QPushButton("⏮")
        self.next_btn = QPushButton("⏭")
        self.loop = QCheckBox("Boucle")
        self.mute_btn = QPushButton("Muet")
        self.volume = QSlider(Qt.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setFixedWidth(115)
        self.volume.setValue(80)
        c.addWidget(self.open_btn)
        c.addWidget(self.prev_btn)
        c.addWidget(self.play_btn)
        c.addWidget(self.next_btn)
        c.addWidget(self.loop)
        c.addStretch(1)
        c.addWidget(QLabel("VOLUME"))
        c.addWidget(self.volume)
        c.addWidget(self.mute_btn)
        outer.addWidget(controls)

        self.open_btn.clicked.connect(self.open_files)
        self.play_btn.clicked.connect(self.toggle_pause)
        self.prev_btn.clicked.connect(self.previous_item)
        self.next_btn.clicked.connect(self.next_item)
        self.loop.toggled.connect(self.set_loop)
        self.volume.valueChanged.connect(lambda v: setattr(self.p, "volume", v) if hasattr(self, "p") else None)
        self.mute_btn.clicked.connect(self.toggle_mute)
        self.seek.sliderMoved.connect(self.seek_to)

        dock = QDockWidget("BIBLIOTHÈQUE", self)
        dock.setObjectName("playlistDock")
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        pane = QWidget()
        pl = QVBoxLayout(pane)
        pl.setContentsMargins(8, 8, 8, 8)
        self.playlist = QListWidget()
        self.playlist.itemDoubleClicked.connect(self.play_selected)
        pl.addWidget(self.playlist, 1)
        row = QHBoxLayout()
        add = QPushButton("Ajouter")
        remove = QPushButton("Retirer")
        row.addWidget(add)
        row.addWidget(remove)
        pl.addLayout(row)
        add.clicked.connect(self.add_files)
        remove.clicked.connect(self.remove_selected)
        dock.setWidget(pane)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)

        tools = QDockWidget("AUDIO & SOUS-TITRES", self)
        tools.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        toolpane = QWidget()
        tv = QVBoxLayout(toolpane)
        tv.setContentsMargins(10, 10, 10, 10)
        audio_group = QGroupBox("Décodage Dolby Digital")
        av = QVBoxLayout(audio_group)
        self.ac3_check = QCheckBox("Activer le décodeur AC-3 intégré")
        self.mode = QComboBox()
        self.mode.addItems(MODES)
        self.drc = QComboBox()
        self.drc.addItems(DRCS)
        self.dn = QCheckBox("Normalisation Dialnorm")
        self.dn.setChecked(True)
        self.target = QSpinBox()
        self.target.setRange(-40, -10)
        self.target.setValue(-27)
        self.target.setSuffix(" dBFS")
        self.aspect = QComboBox()
        self.aspect.addItems(ASPECTS)
        av.addWidget(self.ac3_check)
        av.addWidget(QLabel("Sortie audio"))
        av.addWidget(self.mode)
        av.addWidget(QLabel("Compression dynamique"))
        av.addWidget(self.drc)
        av.addWidget(self.dn)
        av.addWidget(self.target)
        av.addWidget(QLabel("Format d’image"))
        av.addWidget(self.aspect)
        tv.addWidget(audio_group)

        eq_group = QGroupBox("Égaliseur 10 bandes")
        eqv = QVBoxLayout(eq_group)
        self.eq_sliders = []
        for freq, value in zip(EQ_FREQS, self.eq_values):
            line = QHBoxLayout()
            label = QLabel(f"{freq} Hz")
            label.setFixedWidth(65)
            slider = QSlider(Qt.Horizontal)
            slider.setRange(-12, 12)
            slider.setValue(value)
            val = QLabel("0 dB")
            val.setFixedWidth(45)
            slider.valueChanged.connect(lambda x, out=val: out.setText(f"{x:+d} dB"))
            slider.valueChanged.connect(self.apply_equalizer)
            line.addWidget(label)
            line.addWidget(slider, 1)
            line.addWidget(val)
            eqv.addLayout(line)
            self.eq_sliders.append(slider)
        reset_eq = QPushButton("Réinitialiser l’égaliseur")
        reset_eq.clicked.connect(self.reset_equalizer)
        eqv.addWidget(reset_eq)
        tv.addWidget(eq_group)

        sub_group = QGroupBox("Sous-titres")
        sv = QVBoxLayout(sub_group)
        self.sub_btn = QPushButton("Charger un fichier de sous-titres…")
        self.sub_off = QPushButton("Désactiver les sous-titres")
        sv.addWidget(self.sub_btn)
        sv.addWidget(self.sub_off)
        self.sub_btn.clicked.connect(self.load_subtitle)
        self.sub_off.clicked.connect(lambda: setattr(self.p, "sid", "no"))
        tv.addWidget(sub_group)
        tv.addStretch(1)
        tools.setWidget(toolpane)
        self.addDockWidget(Qt.LeftDockWidgetArea, tools)

        for w in (self.ac3_check, self.mode, self.drc):
            (w.toggled if isinstance(w, QCheckBox) else w.currentIndexChanged).connect(self.refresh)
        self.dn.toggled.connect(self.refresh)
        self.target.valueChanged.connect(self.refresh)
        self.aspect.currentIndexChanged.connect(self.set_aspect)

        settings_btn = QPushButton("⚙  Raccourcis")
        settings_btn.clicked.connect(self.configure_shortcuts)
        self.statusBar().addPermanentWidget(settings_btn)
        self.statusBar().showMessage("Dolby Digital Player Premium")

    def _create_player(self):
        self.p = mpv.MPV(
            wid=str(int(self.video.winId())),
            input_default_bindings=False,
            input_vo_keyboard=True,
            keep_open="yes",
            ytdl=False,
            osc=False,
            osd_level=0,
            hwdec="auto-safe",
            cache="yes",
            demuxer_readahead_secs=20,
        )
        self.p.volume = 80

    def _restore_settings(self):
        self.resize(
            int(self.settings.value("window/width", 1280)),
            int(self.settings.value("window/height", 820)),
        )
        self.volume.setValue(int(self.settings.value("audio/volume", 80)))
        self.p.volume = self.volume.value()
        self.loop.setChecked(self.settings.value("playback/loop", "false") == "true")
        self.dn.setChecked(self.settings.value("ac3/dialnorm", "true") == "true")
        self.target.setValue(int(self.settings.value("ac3/target", -27)))
        self.ac3_check.setChecked(self.settings.value("ac3/enabled", "false") == "true")
        self.mode.setCurrentText(self.settings.value("ac3/mode", "Stéréo (LoRo)"))
        self.drc.setCurrentText(self.settings.value("ac3/drc", "Standard"))
        self.aspect.setCurrentText(self.settings.value("video/aspect", "Auto"))
        for i, slider in enumerate(self.eq_sliders):
            slider.setValue(int(self.settings.value(f"eq/{i}", 0)))
        self.apply_equalizer()
        saved = self.settings.value("playlist/paths", [])
        if isinstance(saved, str):
            saved = [saved] if saved else []
        self.add_paths(saved, play=False)
        last = self.settings.value("playback/last_path", "")
        if last and os.path.isfile(last):
            self._play_path(last, restore=True)

    def _save_settings(self):
        self.settings.setValue("window/width", self.width())
        self.settings.setValue("window/height", self.height())
        self.settings.setValue("audio/volume", self.volume.value())
        self.settings.setValue("playback/loop", str(self.loop.isChecked()).lower())
        self.settings.setValue("ac3/enabled", str(self.ac3_check.isChecked()).lower())
        self.settings.setValue("ac3/dialnorm", str(self.dn.isChecked()).lower())
        self.settings.setValue("ac3/target", self.target.value())
        self.settings.setValue("ac3/mode", self.mode.currentText())
        self.settings.setValue("ac3/drc", self.drc.currentText())
        self.settings.setValue("video/aspect", self.aspect.currentText())
        self.settings.setValue("playlist/paths", self.playlist_paths)
        for i, slider in enumerate(self.eq_sliders):
            self.settings.setValue(f"eq/{i}", slider.value())
        if self.path:
            self.settings.setValue("playback/last_path", self.path)
            try:
                self.settings.setValue("playback/position", float(self.p.time_pos or 0))
            except Exception:
                pass

    def _install_shortcuts(self):
        self._shortcuts = []
        for name, default in DEFAULT_KEYS.items():
            sequence = self.settings.value("keys/" + name, default)
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.activated.connect(lambda n=name: self.on_req(n))
            self._shortcuts.append(shortcut)

    def configure_shortcuts(self):
        dialog = ShortcutDialog(self.settings, self)
        if dialog.exec() == QDialog.Accepted:
            for key, value in dialog.values().items():
                if value:
                    self.settings.setValue("keys/" + key, value)
            for shortcut in self._shortcuts:
                shortcut.setParent(None)
            self._install_shortcuts()

    def on_req(self, act):
        if act in ("play_pause", "pause"):
            self.toggle_pause()
        elif act == "fullscreen":
            self.toggle_fs()
        elif act == "exit" and self.isFullScreen():
            self.toggle_fs()
        elif act == "loop":
            self.loop.setChecked(not self.loop.isChecked())
        elif act == "next":
            self.next_item()
        elif act == "previous":
            self.previous_item()
        elif act == "mute":
            self.toggle_mute()

    def toggle_pause(self):
        self.p.pause = not self.p.pause
        self.play_btn.setText("▶  Lecture" if self.p.pause else "Ⅱ  Pause")

    def toggle_fs(self):
        if self.isFullScreen():
            self.showNormal()
            self.menuBar().show()
            self.statusBar().show()
        else:
            self.menuBar().hide()
            self.statusBar().hide()
            self.showFullScreen()

    def toggle_mute(self):
        self.p.mute = not self.p.mute
        self.mute_btn.setText("Son" if self.p.mute else "Muet")

    def set_loop(self, enabled):
        self.p.loop_file = "inf" if enabled else "no"

    def set_aspect(self, index):
        name = ASPECTS[index]
        self.p.keepaspect = name != "Étirer"
        self.p.panscan = 1.0 if name.startswith("Remplir") else 0.0
        self.p.video_aspect_override = name if ":" in name else "no"

    def seek_to(self, value):
        if self.p.duration:
            self.p.seek(value / 1000 * self.p.duration, "absolute")

    def open_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Ajouter des médias", "",
            "Médias vidéo (*.mkv *.mp4 *.avi *.mov *.webm *.ts *.m2ts *.vob *.mpeg *.mpg);;Tous les fichiers (*)"
        )
        if files:
            self.add_paths(files, play=self.path is None)

    def add_files(self):
        self.open_files()

    def add_paths(self, paths, play=False):
        for path in paths:
            if os.path.isfile(path) and path not in self.playlist_paths:
                self.playlist_paths.append(path)
                self.playlist.addItem(QListWidgetItem(Path(path).name))
        if play and self.playlist_paths:
            self.playlist.setCurrentRow(max(0, len(self.playlist_paths) - len(paths)))
            self.play_selected()

    def remove_selected(self):
        row = self.playlist.currentRow()
        if row >= 0:
            self.playlist.takeItem(row)
            del self.playlist_paths[row]
            if row == self.current_index:
                self.current_index = -1

    def play_selected(self, *_):
        row = self.playlist.currentRow()
        if 0 <= row < len(self.playlist_paths):
            self.current_index = row
            self._play_path(self.playlist_paths[row])

    def next_item(self):
        if self.playlist_paths:
            self.current_index = (self.current_index + 1) % len(self.playlist_paths)
            self.playlist.setCurrentRow(self.current_index)
            self._play_path(self.playlist_paths[self.current_index])

    def previous_item(self):
        if self.playlist_paths:
            self.current_index = max(0, self.current_index - 1)
            self.playlist.setCurrentRow(self.current_index)
            self._play_path(self.playlist_paths[self.current_index])

    def _play_path(self, path, restore=False):
        self.path, self.ext_id, self.src = path, None, None
        self.ac3_check.blockSignals(True)
        self.ac3_check.setChecked(False)
        self.ac3_check.blockSignals(False)
        self.p.play(path)
        self.p.wait_until_playing()
        self.set_loop(self.loop.isChecked())
        self.set_aspect(self.aspect.currentIndex())
        tracks = [t for t in (self.p.track_list or []) if t.get("type") == "audio"]
        self.orig_aid = tracks[0]["id"] if tracks else None
        try:
            self.src = Source(path, 0)
            self.status.setText("AC-3 DISPONIBLE · Décodeur intégré prêt")
        except Exception as exc:
            self.status.setText("MÉDIA CHARGÉ · " + str(exc)[:100])
        self.play_btn.setText("Ⅱ  Pause")
        self.current_index = self.playlist_paths.index(path) if path in self.playlist_paths else self.current_index
        if self.current_index >= 0:
            self.playlist.setCurrentRow(self.current_index)
        if restore:
            pos = float(self.settings.value("playback/position", 0))
            if pos > 0:
                QTimer.singleShot(700, lambda: self.p.seek(pos, "absolute"))
        if self.ac3_check.isChecked():
            self.refresh()

    def opts(self):
        return dict(
            mode=MODES[self.mode.currentText()],
            drc=DRCS[self.drc.currentText()],
            dialnorm=self.dn.isChecked(),
            target=float(self.target.value()),
        )

    def open_stream(self, uri):
        if self.src is None:
            raise ValueError("pas de source AC-3")
        return Ac3Stream(self.src, duration_hint=self.dur, **self.cfg)

    def refresh(self, *_):
        if not self.path:
            return
        if not self.ac3_check.isChecked():
            if self.orig_aid is not None:
                self.p.aid = self.orig_aid
            return
        if self.src is None:
            self.status.setText("Aucune piste AC-3 détectée")
            self.ac3_check.blockSignals(True)
            self.ac3_check.setChecked(False)
            self.ac3_check.blockSignals(False)
            return
        self.cfg = self.opts()
        self.dur = self.p.duration
        self.n += 1
        old = self.ext_id
        try:
            self.p.audio_delay = float(self.src.t0 - (self.p.demuxer_start_time or 0.0)) if self.src.t0 else 0.0
        except Exception:
            pass
        self.p.command("audio-add", f"ac3dec://s{self.n}", "select")
        external = [t["id"] for t in self.p.track_list if t["type"] == "audio" and t.get("external")]
        self.ext_id = external[-1] if external else None
        if old is not None:
            try:
                self.p.command("audio-remove", old)
            except Exception:
                pass
        self.status.setText("DÉCODEUR AC-3 ACTIF · " + self.mode.currentText().upper())

    def apply_equalizer(self, *_):
        if not hasattr(self, "p"):
            return
        gains = [s.value() for s in self.eq_sliders]
        filters = []
        for freq, gain in zip(EQ_FREQS, gains):
            if gain:
                filters.append(
                    f"lavfi=[equalizer=f={freq}:width_type=o:width=1:g={gain}]"
                )
        try:
            self.p.command("af", "clr")
            for f in filters:
                self.p.command("af", "add", f)
        except Exception as exc:
            self.status.setText("Égaliseur indisponible : " + str(exc)[:80])

    def reset_equalizer(self):
        for slider in self.eq_sliders:
            slider.setValue(0)

    def load_subtitle(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Charger des sous-titres", "",
            "Sous-titres (*.srt *.ass *.ssa *.vtt *.sub);;Tous les fichiers (*)"
        )
        if path:
            try:
                self.p.command("sub-add", path, "select")
                self.status.setText("SOUS-TITRES CHARGÉS · " + Path(path).name)
            except Exception as exc:
                QMessageBox.warning(self, APP_NAME, f"Impossible de charger les sous-titres :\n{exc}")

    def tick(self):
        try:
            duration, position = self.p.duration, self.p.time_pos
            if duration and position is not None and not self.seek.isSliderDown():
                self.seek.setValue(int(position / duration * 1000))
                self.time_label.setText(self._time(position))
                self.total_label.setText(self._time(duration))
            if self.p.eof_reached and self.path and self.playlist_paths and not self.loop.isChecked():
                self.next_item()
        except Exception:
            pass

    @staticmethod
    def _time(seconds):
        seconds = max(0, int(seconds))
        return f"{seconds // 60:02d}:{seconds % 60:02d}"

    def closeEvent(self, event):
        self.timer.stop()
        self._save_settings()
        try:
            self.p.terminate()
        except Exception:
            pass
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyleSheet(STYLE)
    window = Player()
    window.show()
    sys.exit(app.exec())
