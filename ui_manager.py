# -*- coding: utf-8 -*-
from qgis.PyQt import uic, QtCore
from qgis.PyQt.QtWidgets import QDialog

import os


def get_ui_class(ui_file_name):
    """ Get UI Python class from @ui_file_name """

    ui_folder_path = f"{os.path.dirname(__file__)}{os.sep}ui"
    if not os.path.exists(ui_folder_path):
        print(f"Folder not found: {ui_folder_path}")
        return None

    ui_file_path = os.path.abspath(os.path.join(ui_folder_path, ui_file_name))
    if not os.path.exists(ui_file_path):
        print(f"File not found: {ui_file_path}")
        return None

    return uic.loadUiType(ui_file_path)[0]


FORM_CLASS = get_ui_class('main_dialog.ui')
class MainDialog(QDialog, FORM_CLASS):
    def __init__(self):
        super().__init__()
        self.setupUi(self)


FORM_CLASS = get_ui_class('web_dialog.ui')
class WebDialog(QDialog, FORM_CLASS):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

