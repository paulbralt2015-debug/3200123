# DolbyDigitalPlayer Premium

Lecteur Windows basé sur PySide6, python-mpv et le décodeur AC-3 Python fourni dans `ac3/`.

## Démarrage (Windows)

1. Installer Python 3.12 (64 bits).
2. Installer MPV/libmpv et vérifier que `mpv-2.dll` (ou la DLL attendue par python-mpv) est accessible.
3. Dans ce dossier :

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

## Fonctionnalités ajoutées

- Interface sombre Premium avec panneau bibliothèque et panneau audio.
- Playlist avec ajout, retrait, lecture, précédent et suivant.
- Égaliseur graphique 10 bandes via les filtres audio libmpv/FFmpeg.
- Chargement de sous-titres externes et désactivation.
- Sauvegarde des réglages, du volume, de la playlist, du média et de la position.
- Éditeur de raccourcis clavier.
- Options mpv de cache, prélecture et décodage matériel automatique prudent.
- Conservation du décodeur AC-3, des modes de mixage, Dialnorm et DRC existants.

## Notes

- Le décodage matériel dépend des pilotes et du GPU ; mpv peut revenir au décodage logiciel.
- L'égaliseur utilise les filtres `lavfi` de libmpv. Selon la compilation de libmpv, le filtre FFmpeg `equalizer` doit être disponible.
- Les raccourcis personnalisés s'appliquent à la fenêtre principale ; les raccourcis vidéo natifs F/Esc/L/Espace restent définis.
- Les scripts `tools_test*.py` sont des outils de test et nécessitent FFmpeg ainsi que des fichiers de test générés.
- Le paquet fourni ne contient pas la DLL libmpv : elle doit être distribuée avec l'application au moment du packaging Windows.
