# -*- coding: utf-8 -*-
from PyQt5.QtCore import QCoreApplication, QSettings, Qt, QUrl, QDir
from PyQt5.QtGui import QCursor, QIcon, QPixmap
from PyQt5.QtWidgets import QAction, QDialog, QFileDialog, QMessageBox
from PyQt5.QtPrintSupport import QPrinter
from PyQt5.QtSql import *

from qgis.core import QgsExpressionContextUtils, QgsFeature, QgsGeometry, QgsMessageLog, QgsProject, QgsLayoutExporter, \
    QgsRectangle, QgsLayoutItemMap, QgsLayoutMultiFrame, QgsLayoutFrame, QgsLayoutItemLegend
from qgis.gui import QgsMapTool

import os, sys, subprocess, socket, time, glob, sip

from .PyPDF2 import PdfFileMerger, PdfFileReader
from .ui.FitxaUrban_dialog import Ui_FitxaUrbanDialog
from .ui.FitxaUrban_vista import Ui_FitxaUrbanVista

global db


class FitxaUrban:

    def __init__(self, iface):

        self.iface = iface
        self.plugin_dir = None
        self.pluginName = None
        self.settings = None
        self.action = None
        self.dialog = None
        self.db_status = None
        self.qgs_status = None
        self.config_data = None
        self.dtop = 0
        self.dleft = 0


    def initGui(self):

        self.plugin_dir = os.path.dirname(__file__)
        self.pluginName = os.path.basename(self.plugin_dir)
        self.settings = QSettings("PSIG", "FitxaUrban")
        self.action = None
        self.dialog = None
        self.db_status = "NO"
        self.qgs_status = "NO"
        self.config_data = self.read_config_file()
        self.dtop = 0
        self.dleft = 0

        filename = os.path.abspath(os.path.join(self.plugin_dir, "img", "FitxaUrban_logo.png"))
        self.icon = QIcon(str(filename))
        self.tool = FitxaUrbanTool(self.iface.mapCanvas(), self)
        self.action = QAction(self.icon, u"FitxaUrban", self.iface.mainWindow())
        self.action.setCheckable(True)
        self.action.triggered.connect(self.activateTool)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu(u"FichaUrban", self.action)
        self.iface.mapCanvas().mapToolSet.connect(self.deactivateTool)


    def Preparar(self):
        """ Preparacio d'inici o canvi de projecte qgs """

        self.config_data = self.read_config_file()
        if self.qgs_status == "NO":
            return
        
        # Carregar paràmetres de configuració
        if not QgsProject.instance().title():
            self.Missatge("C", "No hi ha cap projecte carregat")
            return
        self.project_folder = QgsProject.instance().homePath()
        if not self.project_folder:
            self.Missatge("C", "No s'ha trobat carpeta projecte")
            return
        
        # Prepara directori informes
        self.dir_pdfs = self.Config("DIR_PDFS")
        if self.dir_pdfs == "":
            self.dir_pdfs = os.path.join(self.project_folder, 'pdfs')
        d = QDir(self.dir_pdfs)
        if d.exists() == 0 :
            if d.mkdir(self.dir_pdfs) == 0 :
                self.Missatge("C", "No s'ha pogut crear carpeta directori pdf's\n\n"+self.dir_pdfs)
                return
        if self.Config("DIR_PDFS_MULTI") == "SI":
            nl = socket.gethostname()+"("+time.strftime("%d")+")_"
            lf = glob.glob(os.path.join(self.dir_pdfs, socket.gethostname()+"(*"))
            for uf in lf: 
                if uf.find(nl) == -1 :
                    try:
                        os.remove(uf)
                    except OSError:
                        pass

        self.dir_html = self.Config("DIR_HTML")
        if self.dir_html == "":
            self.dir_html = os.path.join(self.project_folder, 'html')
        self.dir_sector = self.Config("DIR_SEC")
        if self.dir_sector == "":
            self.dir_sector = os.path.join(self.dir_html, 'sectors')
        self.dir_classi = self.Config("DIR_CLAS")
        if self.dir_classi == "":
            self.dir_classi = os.path.join(self.dir_html, 'classificacio')
        self.dir_orden = self.Config("DIR_ORD")
        if self.dir_orden == "":
            self.dir_orden = os.path.join(self.dir_html, 'ordenacions')
        
        # Get database queries from configuration files
        self.prepare_queries()

        # Connect to PostgreSQL database
        self.connect_db()


    def prepare_queries(self):
        """ Get database queries from configuration files """

        self.SQL_FITXA = ""
        ff = self.Config("ARXIU_SQL")
        if ff.strip() == "":
            ff = str(os.path.join(self.project_folder, "config", "FitxaUrban_sql.txt"))
        f = open(ff, 'r')
        if f.closed :
            self.Missatge("C", "Error al llegir \n\n"+ff)
            return
        for reg in f :
            self.SQL_FITXA += reg
        f.close()

        self.SQL_FITXA_ZONA = ""
        ff = self.Config("ARXIU_SQL_ZONA")
        if ff.strip() == "":
            ff = str(os.path.join(self.project_folder, "config", "FitxaUrban_sql_zona.txt"))
        f = open(ff, 'r')
        if f.closed :
            self.Missatge("C", "Error al llegir \n\n"+ff)
            return
        for reg in f :
            self.SQL_FITXA_ZONA += reg
        f.close()


    def connect_db(self):
        """ Connect to PostgreSQL database """

        global db

        if self.db_status == "SI" :
            db.close()
            db=QSqlDatabase()
            db.removeDatabase("FitxaUrban")
        db = QSqlDatabase.addDatabase("QPSQL","FitxaUrban")
        if self.Config("BD_SERVICE") == "" :
            db.setHostName(self.Config("BD_HOST"))
            db.setDatabaseName(self.Config("BD_DATABASE"))
            db.setUserName(self.Config("BD_USER"))
            db.setPassword(self.Config("BD_PASS"))
            db.setPort(int(self.Config("BD_PORT")))
        else:
            db.setConnectOptions(f"service={self.Config('BD_SERVICE')}")
        db.open()
        if db.isOpen() == 0 :
            self.Missatge("C", "No s'ha pogut obrir la Base de Dades\n\n'"+db.lastError().text())
            return

        self.db_status = "SI"
        self.qgs_status = "SI"


    def read_config_file(self):
        """ Read and save text of configuration file located in project folder """

        if not QgsProject.instance().title():
            return ""

        self.project_folder = QgsProject.instance().homePath()
        if not self.project_folder:
            return ""

        config_path = str(os.path.join(self.project_folder, "config", "FitxaUrban_config.txt"))
        if not os.path.exists(config_path):
            self.Missatge("C", f"File not found: {config_path}")
            return ""

        f = open(config_path, "r", encoding="ISO-8859-1")
        if f.closed:
            self.Missatge("C", f"Error al llegir arxiu configuració\n\n{ff}")
            return ""

        conf = ""
        for reg in f:
            if len(reg) > 5:
                if reg[0] != "#" and reg.find(" = ") != -1:
                    conf += reg.strip()+"\n"
        f.close()

        self.log_info(conf)
        return conf


    def Config(self, param):

        if self.config_data.find(param + " = ") == -1:
            return ""
        value = self.config_data.split(param + " = ")[1].split("\n")[0].strip()
        return value


    def close_dialog(self):

        if self.dialog:
            try:
                self.dtop = self.dialog.geometry().top()
                self.dleft = self.dialog.geometry().left()
                self.dialog.close()
            except:
                self.dtop = 0
                self.dleft = 0
        layer = self.iface.mapCanvas().currentLayer()
        if layer is not None:
            rect = QgsRectangle(1, 1, 1, 1)
            layer.selectByRect(rect)


    def activateTool(self):

        k = ""
        if self.config_data.find("LAYER_NAME" + " = ") != -1:
            k = self.config_data.split("LAYER_NAME" + " = ")[1].split("\n")[0]
        if k == "":
            self.Missatge("I", "No hi ha cap configuració de projecte qgs carregada")
            return

        self.log_info(f"Capa: {k}")
        registry = QgsProject.instance()
        layer = registry.mapLayersByName(k)[0]
        if layer is None:
            self.Missatge("C", f"Layer {k} no està carregada")
            return

        self.iface.mapCanvas().setMapTool(self.tool)
        self.action.setChecked(True)


    def deactivateTool(self):

        self.action.setChecked(False)
        self.close_dialog()


    def log_info(self, msg):

        QgsMessageLog.logMessage(msg, None, 0)


    def unload(self):

        global db

        if self.db_status == "SI":
            db.close()
            db = QSqlDatabase()
            db.removeDatabase("FitxaUrban")
            self.db_status = "NO"
            self.qgs_status = "NO"
        self.action.setChecked(False)
        if self.dialog:
            self.close_dialog()
        self.iface.removePluginMenu('FitxaUrban', self.action)
        self.iface.removeToolBarIcon(self.action)


    def Missatge(self, av, t):
        """ Finestra missatges """

        m = QMessageBox()
        if av == "W":
            m.setIcon(QMessageBox.Warning)
            z = "Atenció"
        elif av == "C":
            m.setIcon(QMessageBox.Critical)
            z = "Error"
        else :
            m.setIcon(QMessageBox.Information)
            z = "Avís"
        m.setWindowTitle(z)
        m.setText(t)
        m.setStandardButtons(QMessageBox.Ok)
        b = m.button(QMessageBox.Ok)
        b.setText("Segueix")
        m.exec_()


    def create_pdf_zones(self):

        global db
        qu = QSqlQuery(db)
        sql = f"{self.SQL_FITXA_ZONA.split('$ID_VALUE')[0]}{self.id_selec}{self.SQL_FITXA_ZONA.split('$ID_VALUE')[1]}"
        if qu.exec_(sql) == 0:
            msg = f"Error al llegir informació per fitxa zona\n\n{qu.lastError().text()}"
            self.Missatge("C", msg)
            qu.clear()
            return

        camps = self.Config("ZONES_ITEMS")
        per_int = qu.record().indexOf(self.Config("ZONA_AREA_%_NAME"))
        per_min = int(self.Config("ZONA_AREA_%_MINIM"))
        lispdfs = []
        while qu.next():
            if qu.value(per_int) >= per_min:
                composition = None
                for item in QgsProject.instance().layoutManager().printLayouts():
                    if item.name() == self.Config("PDF_ZONES") :
                        composition = item
                        break
                if composition is None :
                    self.Missatge("C", "No s'ha trobat plantilla fitxa en el projecte")
                    return

                total = qu.record().count()
                for i in range(total):
                    QgsExpressionContextUtils.setProjectVariable(QgsProject.instance(), camps.split(",")[i], qu.value(i))
                    if self.sector_codi != "NULL":
                        QgsExpressionContextUtils.setProjectVariable(QgsProject.instance(),
                            self.Config("DESCR_SECTOR_ITEM"), f'{self.sector_codi} - {self.sector_desc}')
                    else:
                        QgsExpressionContextUtils.setProjectVariable(QgsProject.instance(),
                            self.Config("DESCR_SECTOR_ITEM"), None)

                QgsExpressionContextUtils.setProjectVariable(QgsProject.instance(),
                    self.Config("DESCR_CLASSI_ITEM"), f'{self.classi_codi} - {self.classi_desc}')
                composition.refresh()
                nl = ""
                if self.Config("DIR_PDFS_MULTI") == "SI":
                    nl = socket.gethostname() + "(" + time.strftime("%d")+")_"

                filename = f'{nl}{self.refcat}_zona_{qu.value(0)}.pdf'
                filepath = os.path.join(self.dir_pdfs, filename)
                exporter = QgsLayoutExporter(composition)
                if exporter is None:
                    self.Missatge("W", "Exporter is None")
                    return

                result = exporter.exportToPdf(filepath, QgsLayoutExporter.PdfExportSettings())
                if result == QgsLayoutExporter.Success:
                    self.log_info(f"Fitxer generat correctament: {filename}")
                else:
                    self.Missatge("W", "error")
                if self.Config("PDF_ZONES_VISU") != "1":
                    openFile(filepath)
                lispdfs.append(filepath)

        qu.clear()


    def create_merged_pdf(self, lispdfs):
        """ Create a PDF that includes all 'zones' """

        merger = PdfFileMerger()
        for file in lispdfs:
            merger.append(PdfFileReader(file))
        nl = ""
        if self.Config("DIR_PDFS_MULTI") == "SI":
            nl = socket.gethostname() + "(" + time.strftime("%d") + ")_"
        filename = f'{nl}{self.refcat}_zones.pdf'
        filepath = os.path.join(self.dir_pdfs, filename)
        merger.write(filepath)
        if self.Config("PDF_ZONES_VISU") != "2":
            openFile(filepath)


    def run(self):

        if self.qgs_status == "NO":
            self.qgs_status = "SI"
            self.Preparar()
            if self.db_status == "NO" :
                self.Missatge("C", "Errors en la preparació del plugin per al projecte")
                return

        # Get the active layer (where the selected form is).
        layer = self.iface.activeLayer()
        if layer is None :
            self.Missatge("C", "No hi ha layer activat")
            return

        # single feature
        features = layer.selectedFeatures()
        if len(features) < 1:
            self.Missatge("C", "No s'ha seleccionat res")
            return

        if len(features) > 1:
            layer.selectByIds([features[0].id()])
        feature = features[0]
        id_index = feature.fieldNameIndex(self.Config("ID_NAME"))
        if id_index < 0:
            self.Missatge("C", "Manca paràmetre ID_INDEX")
            return

        self.id_selec = feature[id_index]

        global db
        qu = QSqlQuery(db) 
        sq = self.SQL_FITXA.split("$ID_VALUE")[0]+str(self.id_selec)+self.SQL_FITXA.split("$ID_VALUE")[1]
        if qu.exec_(sq) == 0:
            self.Missatge("C", "Error al llegir informació per fitxa\n\n"+qu.lastError().text())
            return
        if qu.next() == 0:
            self.Missatge("C", "No s'ha trobat informació per fitxa\n\n"+qu.lastError().text())
            return
        if qu.value(0) is None:
            self.Missatge("C", "No s'ha trobat informació per la fitxa")
            return

        # Make dialog and set its atributes
        if self.dialog:
            try:
                self.dtop = self.dialog.geometry().top()
                self.dleft = self.dialog.geometry().left()
                self.dialog.close()
            except:
                self.dtop = 0
                self.dleft = 0

        self.dialog = self.initDialog(Ui_FitxaUrbanDialog)
        self.dialog.setFixedSize(self.dialog.size())
        if self.dtop!= 0 and self.dleft != 0:
            self.dialog.setGeometry(self.dleft,self.dtop,self.dialog.width(),self.dialog.height())
        self.dialog.ui.label_5.setPixmap(QPixmap(self.Config("ARXIU_LOGO")))
        self.dialog.ui.Sortir.clicked.connect(self.close_dialog)

        # Static links
        self.dialog.ui.lblCondGenerals.setText(u"<a href='file:///{:s}/condicions_generals.htm'>Condicions Generals</a>".format(self.dir_html))
        self.dialog.ui.lblCondGenerals.linkActivated.connect(self.webDialog)
        self.dialog.ui.lblDotacioAparc.setText(u"<a href='file:///{:s}/dotacio_aparcament.htm'>Dotació mínima d'aparcaments</a>".format(self.dir_html))
        self.dialog.ui.lblDotacioAparc.linkActivated.connect(self.webDialog)
        self.dialog.ui.lblRegulacioAparc.setText(u"<a href='file:///{:s}/regulacio_aparcament.htm'>Regulació particular de l'ús d'aparcaments</a>".format(self.dir_html))
        self.dialog.ui.lblRegulacioAparc.linkActivated.connect(self.webDialog)
        self.dialog.ui.lblParamFinca.setText(u"<a href='file:///{:s}/param_finca.htm'>Paràmetres Finca</a>".format(self.dir_html))
        self.dialog.ui.lblParamFinca.linkActivated.connect(self.webDialog)
        self.dialog.ui.lblParamEdificacio.setText(u"<a href='file:///{:s}/param_edificacio.htm'>Paràmetres Edificació</a>".format(self.dir_html))
        self.dialog.ui.lblParamEdificacio.linkActivated.connect(self.webDialog)

        # Show data
        self.refcat=str(qu.value(int(self.Config("REFCAT"))))
        self.area=float(qu.value(int(self.Config("AREA"))))
        self.adreca=str(qu.value(int(self.Config("ADRECA"))))
        self.sector_codi = str(qu.value(int(self.Config("CODI_SECTOR"))))
        self.sector_desc=str(qu.value(int(self.Config("DESCR_SECTOR"))))
        self.classi_codi=str(qu.value(int(self.Config("CODI_CLASSI"))))
        self.classi_desc=str(qu.value(int(self.Config("DESCR_CLASSI"))))
        self.dialog.ui.refcat.setText(u'{}'.format(self.refcat))
        self.dialog.ui.area.setText((u'{}'.format(round(self.area,1))).rstrip('0').rstrip('.'))
        self.dialog.ui.txtAdreca.setText(u'{}'.format(self.adreca))
        if self.sector_codi != "NULL": # It may not be part of any sector
            self.dialog.ui.txtSector.setText(u'{} - {}'.format(self.sector_codi, self.sector_desc))
            self.dialog.ui.lblSector.setText(u"<a href='file:///{:s}'>Veure normativa</a>".format(os.path.join(self.dir_sector,'{:s}.htm'.format('{}'.format(self.sector_codi)))))
            self.dialog.ui.lblSector.linkActivated.connect(self.webDialog)
        else:
            self.dialog.ui.lblSector.setHidden(True)
        self.dialog.ui.txtClass.setText(u'{} - {}'.format(self.classi_codi, self.classi_desc))
        self.dialog.ui.lblClass.setText(u"<a href='file:///{:s}'>Veure normativa</a>".format(os.path.join(self.dir_classi,'{:s}.htm'.format('{}'.format(self.classi_codi)))))
        self.codes = str(qu.value(int(self.Config("CODI_ZONES")))).replace("{","").replace("}","")
        self.percents = str(qu.value(int(self.Config("PERCENT_ZONES")))).replace("{","").replace("}","")
        self.general_codes = str(qu.value(int(self.Config("CODI_GENERAL_ZONES")))).replace("{","").replace("}","")
        for i in range(0, 4):
            txtClau = getattr(self.dialog.ui, 'txtClau_{}'.format(i + 1))
            txtPer = getattr(self.dialog.ui, 'txtPer_{}'.format(i + 1))
            lblOrd = getattr(self.dialog.ui, 'lblOrd_{}'.format(i + 1))
            try:
                txtClau.setText(u'{}'.format(self.codes.split(",")[i]))
            except IndexError:
                txtClau.setHidden(True)
            try:
                txtPer.setText(u'{:02.2f}'.format(float(self.percents.split(",")[i])))
            except IndexError:
                txtPer.setHidden(True)
            try:
                filename = '{:s}.htm'.format(self.general_codes.split(",")[i])
                filepath = os.path.join(self.dir_orden, filename)
                if os.path.isfile(filepath):
                    zz = u"<a href='file:///{:s}'>{:s}</a>".format(filepath, filename)
                else:
                    zz = self.general_codes.split(",")[i]
                lblOrd.setText(u'{}'.format(zz))
                lblOrd.linkActivated.connect(self.webDialog)
            except IndexError:
                lblOrd.setHidden(True)

        qu.clear()

        self.dialog.show()


        def makeShowUbicacioPdf():
            """ PDF generation functions """

            # Make temporary layer
            try:
                self.iface.removeMapLayers(self.Config("SELEC_NAME"))
            except:
                a = 1

            vl = self.iface.addVectorLayer("Polygon?crs=epsg:25831&field=id:integer&index=yes", "temp_print_polygon", "memory")
            k = self.Config("ARXIU_QML")
            if k.strip() == "":
                k=os.path.join(self.plugin_dir,"FitxaUrban.qml")
            vl.loadNamedStyle(k)
            vl.setName(self.Config("SELEC_NAME"))
            pr = vl.dataProvider()
            fet = QgsFeature()
            fet.setGeometry(QgsGeometry(feature.geometry()))  # copy the geometry
            pr.addFeatures([fet])
            vl.updateExtents()
            moveLayer(vl, 0)

            def refreshed():

                # Disconnect signal
                self.iface.mapCanvas().mapCanvasRefreshed.disconnect(refreshed)
                composition = None
                for item in QgsProject.instance().layoutManager().printLayouts():
                    if item.name() == self.Config("PDF_UBICACIO") :
                        composition = item
                        break
                if composition is None:
                    self.Missatge("C","No s'ha trobat plantilla fitxa en el projecte")
                    return
                # Set values
                QgsExpressionContextUtils.setProjectVariable(QgsProject.instance(),self.Config("REFCAT_ITEM"), self.refcat)
                QgsExpressionContextUtils.setProjectVariable(QgsProject.instance(),self.Config("AREA_ITEM"), '{:.0f}'.format(self.area))
                QgsExpressionContextUtils.setProjectVariable(QgsProject.instance(),self.Config("ADRECA_ITEM"), self.adreca)
                # Set main map to the propper position
                #main_map = composition.itemById('Mapa principal')
                #main_map = composition.referenceMap()
                main_map=layout_item(composition,self.Config("MAPA_NAME"),QgsLayoutItemMap)
                centerMap(main_map, feature)
                # Add temporal layer to composition
                legend = layout_item(composition,self.Config("LLEGENDA_NAME"),QgsLayoutItemLegend)
                legend_root = legend.model().rootGroup()
                legend_root.insertLayer(0, vl)
                # Make PDF
                nl = ""
                if self.Config("DIR_PDFS_MULTI") == "SI":
                    nl = socket.gethostname()+"("+time.strftime("%d")+")_"
                filename = os.path.join(self.dir_pdfs, '{}{}_ubicacio.pdf'.format(nl,self.refcat))
                exporter = QgsLayoutExporter(composition)
                exporter.exportToPdf(filename,QgsLayoutExporter.PdfExportSettings())
                openFile(filename)
                # Delete temporary layer
                legend_root.removeLayer(vl)
                QgsProject.instance().removeMapLayers([vl.id()])
                # Repaint again
                self.iface.mapCanvas().refresh()

            self.iface.mapCanvas().mapCanvasRefreshed.connect(refreshed)
            self.iface.mapCanvas().refresh()


        def destroyDialog():
            self.dialog = None

        # Connect the click signal to the functions
        self.dialog.ui.lblClass.linkActivated.connect(self.webDialog)
        self.dialog.ui.btnParcelaPdf.clicked.connect(makeShowUbicacioPdf)
        self.dialog.ui.btnClauPdf_1.clicked.connect(self.create_pdf_zones)
        self.dialog.destroyed.connect(destroyDialog)

        self.dialog.exec_()


    def webDialog(self, url):

        QgsMessageLog.logMessage("Opened url: " + url)
        dialog = self.initDialog(Ui_FitxaUrbanVista, Qt.WindowSystemMenuHint | Qt.WindowTitleHint | Qt.WindowMaximizeButtonHint)
        dialog.ui.webView.setUrl(QUrl(url))
        dialog.ui.webView.setWhatsThis(url)
        
        def exportPDF():
            printer = QPrinter(QPrinter.HighResolution)
            printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setPaperSize(QPrinter.A4)
            #printer.setFullPage(True)
            printer.setOrientation(QPrinter.Portrait)
            printer.setPageMargins(15, 15, 15, 15, QPrinter.Millimeter)
            filename = str(os.path.splitext(os.path.basename(dialog.ui.webView.whatsThis()))[0])+u".pdf"
            filename = os.path.join(self.dir_pdfs,filename)
            printer.setOutputFileName(filename)
            dialog.ui.webView.print_(printer)
            openFile(filename)

        dialog.ui.Sortir.clicked.connect(dialog.close)
        dialog.ui.Exportar.clicked.connect(exportPDF)
        dialog.exec_()


    def initDialog(self, Class, flags=Qt.WindowSystemMenuHint | Qt.WindowTitleHint):
        """ Initializes a Dialog with the usual parameters of this plugin """

        # This function makes the code more pretty
        dialog = QDialog(None, flags)
        dialog.ui = Class()
        dialog.ui.setupUi(dialog)
        dialog.setAttribute(Qt.WA_DeleteOnClose)
        dialog.setWindowIcon(self.icon)
        dialog.setWindowModality(Qt.WindowModal)
        return dialog


    def getPDFPrinter(self, name):

        printer = QPrinter(QPrinter.HighResolution)
        path = QFileDialog.getSaveFileName(
            None,
            None,
            os.path.join(
                self.settings.value("save path", os.path.expanduser("~")),  # default folder
                name + ".pdf"  # default filename
            ),
            "PDF (*.pdf)"
        )
        if path[0] is not None and path != "":
            self.settings.setValue("save path", os.path.dirname(path[0]))
            printer.setOutputFileName(path[0])
            return printer
        else:
            return None


    def error(self, msg):
        self.iface.messageBar().pushCritical("Error", msg)


class FitxaUrbanTool(QgsMapTool):

    def __init__(self, canvas, plugin):

        super(QgsMapTool, self).__init__(canvas)
        self.canvas = canvas
        self.plugin = plugin
        k = ""
        if str(self.plugin.config_data).find("ARXIU_PUNTER" + " = ") != -1:
            k = str(self.plugin.config_data).split("ARXIU_PUNTER" + " = ")[1].split("\n")[0]
        if k.strip() == "":
            k=os.path.join(self.plugin.plugin_dir, "img", "FitxaUrban_punter.png")
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


# region Utilities

def openFile(path):
    """Opens a file with the default application."""

    # Multiple OS support
    if sys.platform.startswith('darwin'):
        subprocess.Popen(['open', path])
    elif os.name == 'nt':
        os.startfile(path)
    elif os.name == 'posix':
        subprocess.Popen(['xdg-open', path])


def centerMap(map, feature):

    newExtent = centerRect(map.extent(), feature.geometry().boundingBox().center())
    map.setExtent(newExtent)


def centerRect(rect, point):

    hw = rect.width() / 2
    hh = rect.height() / 2
    xMin = point.x() - hw
    xMax = point.x() + hw
    yMin = point.y() - hh
    yMax = point.y() + hh
    return type(rect)(xMin, yMin, xMax, yMax)


def moveLayer(layer, pos):

    root = QgsProject.instance().layerTreeRoot()
    node = root.findLayer(layer.id())
    clone = node.clone()
    parent = node.parent()
    parent.insertChildNode(pos, clone)
    parent.removeChildNode(node)


def askPrinter():

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

# endregion