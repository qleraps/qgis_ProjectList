# -*- coding: utf-8 -*-
"""ProjectList - ubegrænset historik over åbnede QGIS-projekter."""


def classFactory(iface):
    from .project_list import ProjectList
    return ProjectList(iface)
