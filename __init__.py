# -*- coding: utf-8 -*-
def classFactory(iface):

    from .fitxa_urban import FitxaUrban

    plugin = FitxaUrban(iface)
    iface.projectRead.connect(plugin.init_config)
    iface.newProjectCreated.connect(plugin.init_config)

    return plugin
    
