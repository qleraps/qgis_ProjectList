# -*- coding: utf-8 -*-
"""Main plugin class for ProjectList."""

import os

from qgis.core import QgsApplication, QgsProject
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon

try:
    from qgis.PyQt.QtWidgets import QAction
except ImportError:  # Qt6 / QGIS 4
    from qgis.PyQt.QtGui import QAction

from .history_store import HistoryStore
from .i18n import tr
from .project_list_dockwidget import ProjectListDockWidget


class ProjectList:
    """QGIS Plugin Implementation."""

    MENU_NAME = "&ProjectList"

    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dockwidget = None
        self.plugin_is_active = False
        self.store = None

    def initGui(self):
        db_path = os.path.join(
            QgsApplication.qgisSettingsDirPath(), "project_list_plugin", "history.sqlite3"
        )
        self.store = HistoryStore(db_path)

        icon = QIcon(os.path.join(os.path.dirname(__file__), "icon.png"))
        self.action = QAction(icon, "ProjectList", self.iface.mainWindow())
        self.action.setCheckable(True)
        self.action.setStatusTip(tr("action_status_tip"))
        self.action.triggered.connect(self.toggle)

        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu(self.MENU_NAME, self.action)

        QgsProject.instance().readProject.connect(self.on_project_opened)
        QgsProject.instance().projectSaved.connect(self.on_project_saved)

    def unload(self):
        QgsProject.instance().readProject.disconnect(self.on_project_opened)
        QgsProject.instance().projectSaved.disconnect(self.on_project_saved)

        self.iface.removePluginMenu(self.MENU_NAME, self.action)
        self.iface.removeToolBarIcon(self.action)

        if self.dockwidget is not None:
            self.iface.removeDockWidget(self.dockwidget)
            self.dockwidget = None

        if self.store is not None:
            self.store.close()
            self.store = None

    def toggle(self, checked):
        if self.dockwidget is None:
            self.dockwidget = ProjectListDockWidget(self.iface, self.store)
            self.dockwidget.closingPlugin.connect(self.on_dockwidget_closed)
            self.iface.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dockwidget)

        self.dockwidget.setVisible(checked)
        self.plugin_is_active = checked
        if checked:
            self.dockwidget.refresh_table()

    def on_dockwidget_closed(self):
        self.action.setChecked(False)
        self.plugin_is_active = False

    def _record_current_project(self):
        project = QgsProject.instance()
        path = project.fileName()
        if not path:
            return
        is_storage = project.projectStorage() is not None
        self.store.record_open(path, is_storage=is_storage)
        if self.dockwidget is not None and self.dockwidget.isVisible():
            self.dockwidget.refresh_table()

    def on_project_opened(self, *args):
        self._record_current_project()

    def on_project_saved(self, *args):
        self._record_current_project()
