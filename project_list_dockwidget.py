# -*- coding: utf-8 -*-
"""Dockwidget with all ProjectList UI: liste, søgning, sortering og
kontekstmenu (pin, åbn, vis i Stifinder, find fil igen, fjern)."""

import os
import re
import subprocess
import sys
from datetime import datetime

from qgis.core import Qgis
from qgis.PyQt.QtCore import Qt, QUrl, pyqtSignal
from qgis.PyQt.QtGui import QColor, QDesktopServices
from qgis.PyQt.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel,
    QComboBox, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QMenu, QFileDialog,
)

from .i18n import tr

COL_PIN, COL_NAME, COL_FOLDER, COL_DATE, COL_COUNT = range(5)


class ProjectListDockWidget(QDockWidget):
    closingPlugin = pyqtSignal()
    PLUGIN_NAME = "ProjectList"

    def __init__(self, iface, store, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.store = store

        self._build_ui()
        self._connect_signals()
        self.refresh_table()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self):
        self.setWindowTitle(self.PLUGIN_NAME)

        container = QWidget(self)
        self.setWidget(container)
        layout = QVBoxLayout(container)

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText(tr("search_placeholder"))
        self.txt_search.setClearButtonEnabled(True)
        layout.addWidget(self.txt_search)

        sort_row = QHBoxLayout()
        sort_row.addWidget(QLabel(tr("sort_by")))
        self.cbo_sort = QComboBox()
        self.cbo_sort.addItem(tr("sort_last_opened"), "last_opened")
        self.cbo_sort.addItem(tr("sort_name"), "filename")
        self.cbo_sort.addItem(tr("sort_folder"), "folder")
        self.cbo_sort.addItem(tr("sort_count"), "opened_count")
        sort_row.addWidget(self.cbo_sort)

        self.btn_sort_order = QPushButton("▼")
        self.btn_sort_order.setCheckable(True)
        self.btn_sort_order.setToolTip(tr("sort_direction_tip"))
        self.btn_sort_order.setFixedWidth(28)
        sort_row.addWidget(self.btn_sort_order)

        sort_row.addStretch()

        self.btn_refresh = QPushButton(tr("refresh"))
        self.btn_refresh.setToolTip(tr("refresh_tip"))
        sort_row.addWidget(self.btn_refresh)
        layout.addLayout(sort_row)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels([
            "", tr("col_project"), tr("col_location"), tr("col_last_opened"), tr("col_count"),
        ])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(COL_PIN, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_NAME, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_FOLDER, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_DATE, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_COUNT, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table)

        self.lbl_status = QLabel("")
        layout.addWidget(self.lbl_status)

    def _connect_signals(self):
        self.txt_search.textChanged.connect(self.refresh_table)
        self.cbo_sort.currentIndexChanged.connect(self.refresh_table)
        self.btn_sort_order.toggled.connect(self.on_sort_order_toggled)
        self.btn_refresh.clicked.connect(self.refresh_table)
        self.table.doubleClicked.connect(self.open_selected)
        self.table.customContextMenuRequested.connect(self.show_context_menu)

    def on_sort_order_toggled(self, checked):
        self.btn_sort_order.setText("▲" if checked else "▼")
        self.refresh_table()

    # ------------------------------------------------------------------
    # Listeopbygning
    # ------------------------------------------------------------------
    def refresh_table(self):
        query = self.txt_search.text().strip().lower()
        sort_key = self.cbo_sort.currentData()
        ascending = self.btn_sort_order.isChecked()

        all_rows = self.store.get_all()
        rows = all_rows
        if query:
            rows = [r for r in rows if query in r["filename"].lower() or query in r["path"].lower()]

        def sort_fn(r):
            value = r[sort_key]
            return value.lower() if isinstance(value, str) else value

        pinned_rows = sorted((r for r in rows if r["pinned"]), key=sort_fn, reverse=not ascending)
        other_rows = sorted((r for r in rows if not r["pinned"]), key=sort_fn, reverse=not ascending)
        ordered = pinned_rows + other_rows

        self.table.setRowCount(len(ordered))
        for i, record in enumerate(ordered):
            self._set_row(i, record)

        if query:
            self.lbl_status.setText(tr("status_filtered", len(ordered), len(all_rows)))
        else:
            self.lbl_status.setText(tr("status_count", len(ordered)))

    def _set_row(self, row, record):
        is_storage = bool(record["is_storage"])
        # Storage-URI'er (f.eks. PostGIS-projekter) findes ikke på disk, så
        # eksistens-tjekket giver kun mening for almindelige filer.
        missing = (not is_storage) and (not os.path.exists(record["path"]))

        pin_item = QTableWidgetItem("★" if record["pinned"] else "")
        pin_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        name_text = record["filename"] + (tr("file_not_found_suffix") if missing else "")
        name_item = QTableWidgetItem(name_text)

        folder_item = QTableWidgetItem(record["folder"])
        date_item = QTableWidgetItem(self._format_date(record["last_opened"]))

        count_item = QTableWidgetItem(str(record["opened_count"]))
        count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        tooltip = self._mask_secret(record["path"]) if is_storage else record["path"]

        items = [pin_item, name_item, folder_item, date_item, count_item]
        for item in items:
            item.setData(Qt.ItemDataRole.UserRole, record["path"])
            item.setData(Qt.ItemDataRole.UserRole + 1, is_storage)
            item.setToolTip(tooltip)
            if missing:
                item.setForeground(QColor(150, 150, 150))

        for col, item in enumerate(items):
            self.table.setItem(row, col, item)

    @staticmethod
    def _format_date(iso_text):
        try:
            return datetime.fromisoformat(iso_text).strftime(tr("date_format"))
        except ValueError:
            return iso_text

    @staticmethod
    def _mask_secret(uri):
        """Skjuler et evt. kodeord i en connection-URI (bruges kun i tooltip -
        den rigtige, ikke-maskerede sti er stadig den der åbnes med)."""
        return re.sub(r"(://[^:@/]+:)[^@]+(@)", r"\1***\2", uri)

    # ------------------------------------------------------------------
    # Handlinger
    # ------------------------------------------------------------------
    def _selected_row_data(self):
        row = self.table.currentRow()
        if row < 0:
            return None, None
        item = self.table.item(row, COL_PIN)
        return item.data(Qt.ItemDataRole.UserRole), bool(item.data(Qt.ItemDataRole.UserRole + 1))

    def open_selected(self):
        path, is_storage = self._selected_row_data()
        if not path:
            return
        if not is_storage and not os.path.exists(path):
            self.warn(tr("warn_file_missing"))
            return
        self.iface.addProject(path)

    def show_context_menu(self, pos):
        item = self.table.itemAt(pos)
        if item is None:
            return
        row = item.row()
        self.table.selectRow(row)

        path = self.table.item(row, COL_PIN).data(Qt.ItemDataRole.UserRole)
        is_storage = bool(self.table.item(row, COL_PIN).data(Qt.ItemDataRole.UserRole + 1))
        pinned = self.table.item(row, COL_PIN).text() == "★"
        missing = (not is_storage) and (not os.path.exists(path))

        menu = QMenu(self)
        if not missing:
            menu.addAction(tr("menu_open"), self.open_selected)
        menu.addAction(tr("menu_unpin") if pinned else tr("menu_pin"), lambda: self.toggle_pin(path, pinned))
        if not is_storage:
            if not missing:
                menu.addAction(tr("menu_reveal"), lambda: self.reveal_in_explorer(path))
            else:
                menu.addAction(tr("menu_relink"), lambda: self.relink(path))
        menu.addSeparator()
        menu.addAction(tr("menu_remove"), lambda: self.remove_entry(path))
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def toggle_pin(self, path, currently_pinned):
        self.store.set_pinned(path, not currently_pinned)
        self.refresh_table()

    def reveal_in_explorer(self, path):
        norm = os.path.normpath(path)
        if sys.platform == "win32":
            # Markerer filen i Stifinder.
            subprocess.Popen(["explorer", "/select,", norm])
        else:
            # Linux/macOS: åbn den omgivende mappe i standard-filhåndtering.
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(norm)))

    def relink(self, old_path):
        start_dir = os.path.dirname(old_path)
        if not os.path.isdir(start_dir):
            start_dir = ""
        new_path, _ = QFileDialog.getOpenFileName(
            self, tr("relink_title"), start_dir, tr("relink_filter")
        )
        if new_path:
            self.store.update_path(old_path, new_path)
            self.refresh_table()

    def remove_entry(self, path):
        self.store.remove(path)
        self.refresh_table()

    def warn(self, message):
        self.iface.messageBar().pushMessage(self.PLUGIN_NAME, message, Qgis.MessageLevel.Warning)

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()
