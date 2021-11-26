# -*- coding: utf-8 -*-
def classFactory(iface):

    from .main import UrbanPlanning

    plugin = UrbanPlanning(iface)
    iface.projectRead.connect(plugin.init_config)
    iface.newProjectCreated.connect(plugin.init_config)

    return plugin
    
