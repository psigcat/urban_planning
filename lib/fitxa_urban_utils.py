import os
import subprocess
import sys
import sip

from PyQt5.QtPrintSupport import QPrinter
from qgis._core import QgsProject, QgsLayoutMultiFrame, QgsLayoutFrame, QgsExpressionContextUtils


def open_file(path):
    """Opens a file with the default application."""

    # Multiple OS support
    if sys.platform.startswith('darwin'):
        subprocess.Popen(['open', path])
    elif os.name == 'nt':
        os.startfile(path)
    elif os.name == 'posix':
        subprocess.Popen(['xdg-open', path])


def center_map(map, feature):

    newExtent = center_rect(map.extent(), feature.geometry().boundingBox().center())
    map.setExtent(newExtent)


def center_rect(rect, point):

    hw = rect.width() / 2
    hh = rect.height() / 2
    xMin = point.x() - hw
    xMax = point.x() + hw
    yMin = point.y() - hh
    yMax = point.y() + hh
    return type(rect)(xMin, yMin, xMax, yMax)


def move_layer(layer, pos):

    root = QgsProject.instance().layerTreeRoot()
    node = root.findLayer(layer.id())
    clone = node.clone()
    parent = node.parent()
    parent.insertChildNode(pos, clone)
    parent.removeChildNode(node)


def ask_printer():

    printer = QPrinter()
    select = QPrintDialog(printer)
    if select.exec_():
        return printer
    else:
        return None


def layout_item(layout, item_id, item_class):
    """Fetch a specific item according to its type in a layout.
    There's some sip casting conversion issues with QgsLayout::itemById.
    Don't use it, and use this function instead.
    See https://github.com/inasafe/inasafe/issues/4271
    :param layout: The layout to look in.
    :type layout: QgsLayout
    :param item_id: The ID of the item to look for.
    :type item_id: basestring
    :param item_class: The expected class name.
    :type item_class: cls
    :return: The layout item, inherited class of QgsLayoutItem.
    """

    item = layout.itemById(item_id)
    if item is None:
        # no match!
        return item
    if issubclass(item_class, QgsLayoutMultiFrame):
        # finding a multiframe by frame id
        frame = sip.cast(item, QgsLayoutFrame)
        multi_frame = frame.multiFrame()
        return sip.cast(multi_frame, item_class)
    else:
        # force sip to correctly cast item to required type
        return sip.cast(item, item_class)


def get_print_layout(layout_name):
    """ Get layout with name @layout_name """

    print_layouts = QgsProject.instance().layoutManager().printLayouts()
    layout = None
    for item in print_layouts:
        if item.name() == layout_name:
            layout = item
            break

    return layout


def set_project_variable(variable, value):
    """ Set QGIS project variable """

    QgsExpressionContextUtils.setProjectVariable(QgsProject.instance(), variable, value)

