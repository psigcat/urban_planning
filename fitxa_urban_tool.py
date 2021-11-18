import os

from PyQt5.QtGui import QCursor, QPixmap
from qgis.core import QgsProject, QgsRectangle
from qgis.gui import QgsMapTool


class FitxaUrbanTool(QgsMapTool):

    def __init__(self, canvas, plugin):

        super(QgsMapTool, self).__init__(canvas)
        self.canvas = canvas
        self.plugin = plugin
        k = ""
        if str(self.plugin.config_data).find("ARXIU_PUNTER" + " = ") != -1:
            k = str(self.plugin.config_data).split("ARXIU_PUNTER" + " = ")[1].split("\n")[0]
        if k.strip() == "":
            k = os.path.join(self.plugin.plugin_dir, "img", "FitxaUrban_punter.png")
        self.setCursor(QCursor(QPixmap(k), 1, 1))


    def canvasReleaseEvent(self, e):
        """ Activate config layer """

        k = ""
        if self.plugin.config_data.find("LAYER_NAME" + " = ") != -1:
            k = self.plugin.config_data.split("LAYER_NAME" + " = ")[1].split("\n")[0]
        if k != "":
            registry = QgsProject.instance()
            layer = registry.mapLayersByName(k)[0]
            self.plugin.iface.setActiveLayer(layer)
        layer = self.canvas.currentLayer()
        if layer is None:
            return

        point = e.mapPoint()
        radius = self.canvas.mapUnitsPerPixel()
        rect = QgsRectangle(point.x(), point.y(), point.x() + radius, point.y() + radius)
        layer.selectByRect(rect)
        self.plugin.run()

