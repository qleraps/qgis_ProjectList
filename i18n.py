# -*- coding: utf-8 -*-
"""User-interface texts in English and Danish.

The language follows QGIS' own language setting (Settings > Options >
General): Danish if QGIS runs in Danish, otherwise English. QGIS only changes
language on restart, so it is decided once, the first time a text is needed.
Texts are looked up by key; a key missing in Danish falls back to English.
"""

_language = None


def _detect_language():
    try:
        from qgis.core import QgsSettings
        from qgis.PyQt.QtCore import QLocale

        settings = QgsSettings()
        if settings.value("locale/overrideFlag", False, type=bool):
            locale = str(settings.value("locale/userLocale", "") or "")
        else:
            locale = QLocale.system().name()
    except Exception:
        locale = ""
    return "da" if locale.lower().startswith("da") else "en"


def language():
    global _language
    if _language is None:
        _language = _detect_language()
    return _language


def set_language(lang):
    global _language
    _language = lang


def tr(key, *args):
    text = STRINGS.get(language(), {}).get(key)
    if text is None:
        text = STRINGS["en"].get(key, key)
    return text % args if args else text


STRINGS = {
    "en": {
        "action_status_tip": "Show history of opened QGIS projects",
        "search_placeholder": "Search by file name or path...",
        "sort_by": "Sort by:",
        "sort_last_opened": "Last opened",
        "sort_name": "Name",
        "sort_folder": "Folder",
        "sort_count": "Times opened",
        "sort_direction_tip": "Change sort direction",
        "refresh": "Refresh",
        "refresh_tip": "Reload the list (e.g. after changes to the history)",
        "col_project": "Project",
        "col_location": "Location",
        "col_last_opened": "Last opened",
        "col_count": "Count",
        "file_not_found_suffix": "  (file not found)",
        "status_count": "%d project(s)",
        "status_filtered": "%d of %d project(s)",
        "date_format": "%Y-%m-%d %H:%M",
        "warn_file_missing": "The file no longer exists at this location.",
        "menu_open": "Open project",
        "menu_pin": "Pin",
        "menu_unpin": "Unpin",
        "menu_reveal": "Show in File Explorer",
        "menu_relink": "Locate file again...",
        "menu_remove": "Remove from history",
        "relink_title": "Locate the project file again",
        "relink_filter": "QGIS projects (*.qgz *.qgs)",
    },
    "da": {
        "action_status_tip": "Vis historik over åbnede QGIS-projekter",
        "search_placeholder": "Søg på filnavn eller sti...",
        "sort_by": "Sortér efter:",
        "sort_last_opened": "Sidst åbnet",
        "sort_name": "Navn",
        "sort_folder": "Mappe",
        "sort_count": "Antal gange åbnet",
        "sort_direction_tip": "Skift sorteringsretning",
        "refresh": "Opdatér",
        "refresh_tip": "Genindlæs listen (f.eks. efter ændringer i historikken)",
        "col_project": "Projekt",
        "col_location": "Placering",
        "col_last_opened": "Sidst åbnet",
        "col_count": "Antal",
        "file_not_found_suffix": "  (fil ikke fundet)",
        "status_count": "%d projekt(er)",
        "status_filtered": "%d af %d projekt(er)",
        "date_format": "%d-%m-%Y %H:%M",
        "warn_file_missing": "Filen findes ikke længere på denne placering.",
        "menu_open": "Åbn projekt",
        "menu_pin": "Fastgør",
        "menu_unpin": "Frigør",
        "menu_reveal": "Vis i Stifinder",
        "menu_relink": "Find fil igen...",
        "menu_remove": "Fjern fra historik",
        "relink_title": "Find projektfilen igen",
        "relink_filter": "QGIS-projekter (*.qgz *.qgs)",
    },
}
