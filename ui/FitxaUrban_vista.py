# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'Fonts\FitxaUrban_vista.ui'
#
# Created by: PyQt5 UI code generator 5.11.3
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_FitxaUrbanVista(object):
    def setupUi(self, FitxaUrbanVista):
        FitxaUrbanVista.setObjectName("FitxaUrbanVista")
        FitxaUrbanVista.resize(976, 618)
        self.verticalLayout = QtWidgets.QVBoxLayout(FitxaUrbanVista)
        self.verticalLayout.setObjectName("verticalLayout")
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setContentsMargins(-1, 5, 5, -1)
        self.horizontalLayout.setObjectName("horizontalLayout")
        spacerItem = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout.addItem(spacerItem)
        self.Exportar = QtWidgets.QPushButton(FitxaUrbanVista)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.Exportar.sizePolicy().hasHeightForWidth())
        self.Exportar.setSizePolicy(sizePolicy)
        self.Exportar.setMinimumSize(QtCore.QSize(100, 33))
        self.Exportar.setMaximumSize(QtCore.QSize(100, 33))
        self.Exportar.setAutoDefault(False)
        self.Exportar.setObjectName("Exportar")
        self.horizontalLayout.addWidget(self.Exportar)
        self.Sortir = QtWidgets.QPushButton(FitxaUrbanVista)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.Sortir.sizePolicy().hasHeightForWidth())
        self.Sortir.setSizePolicy(sizePolicy)
        self.Sortir.setMinimumSize(QtCore.QSize(33, 33))
        self.Sortir.setMaximumSize(QtCore.QSize(33, 33))
        font = QtGui.QFont()
        font.setFamily("Arial")
        font.setPointSize(13)
        font.setBold(True)
        font.setWeight(75)
        self.Sortir.setFont(font)
        self.Sortir.setAutoDefault(False)
        self.Sortir.setObjectName("Sortir")
        self.horizontalLayout.addWidget(self.Sortir)
        self.verticalLayout.addLayout(self.horizontalLayout)
        self.webView = QtWebKitWidgets.QWebView(FitxaUrbanVista)
        self.webView.setProperty("url", QtCore.QUrl("about:blank"))
        self.webView.setObjectName("webView")
        self.verticalLayout.addWidget(self.webView)

        self.retranslateUi(FitxaUrbanVista)
        QtCore.QMetaObject.connectSlotsByName(FitxaUrbanVista)

    def retranslateUi(self, FitxaUrbanVista):
        _translate = QtCore.QCoreApplication.translate
        FitxaUrbanVista.setWindowTitle(_translate("FitxaUrbanVista", "FitxaUrban 2.0 - Visor de documents"))
        self.Exportar.setText(_translate("FitxaUrbanVista", "Exportar a PDF"))
        self.Sortir.setText(_translate("FitxaUrbanVista", "x"))

from PyQt5 import QtWebKitWidgets
