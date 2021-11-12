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
from functools import partial

from .PyPDF2 import PdfFileMerger, PdfFileReader
from .ui_manager import FitxaUrbanDialog
from .ui_manager import FitxaUrbanVista

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
        self.action = QAction(self.icon, "FitxaUrban", self.iface.mainWindow())
        self.action.setCheckable(True)
        self.action.triggered.connect(self.activate_tool)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu("FichaUrban", self.action)
        self.iface.mapCanvas().mapToolSet.connect(self.deactivate_tool)


    def Preparar(self):
        """ Preparacio d'inici o canvi de projecte qgs """

        self.config_data = self.read_config_file()
        if self.qgs_status == "NO":
            return
        
        # Carregar paràmetres de configuració
        if not QgsProject.instance().title():
            self.show_message("C", "No hi ha cap projecte carregat")
            return
        self.project_folder = QgsProject.instance().homePath()
        if not self.project_folder:
            self.show_message("C", "No s'ha trobat carpeta projecte")
            return
        
        # Prepara directori informes
        self.dir_pdfs = self.get_parameter("DIR_PDFS")
        if self.dir_pdfs == "":
            self.dir_pdfs = os.path.join(self.project_folder, 'pdfs')
        d = QDir(self.dir_pdfs)
        if d.exists() == 0 :
            if d.mkdir(self.dir_pdfs) == 0 :
                self.show_message("C", "No s'ha pogut crear carpeta directori pdf's\n\n" + self.dir_pdfs)
                return
        if self.get_parameter("DIR_PDFS_MULTI") == "SI":
            nl = socket.gethostname()+"("+time.strftime("%d")+")_"
            lf = glob.glob(os.path.join(self.dir_pdfs, socket.gethostname()+"(*"))
            for uf in lf: 
                if uf.find(nl) == -1 :
                    try:
                        os.remove(uf)
                    except OSError:
                        pass

        self.dir_html = self.get_parameter("DIR_HTML")
        if self.dir_html == "":
            self.dir_html = os.path.join(self.project_folder, 'html')
        self.dir_sector = self.get_parameter("DIR_SEC")
        if self.dir_sector == "":
            self.dir_sector = os.path.join(self.dir_html, 'sectors')
        self.dir_classi = self.get_parameter("DIR_CLAS")
        if self.dir_classi == "":
            self.dir_classi = os.path.join(self.dir_html, 'classificacio')
        self.dir_orden = self.get_parameter("DIR_ORD")
        if self.dir_orden == "":
            self.dir_orden = os.path.join(self.dir_html, 'ordenacions')
        
        # Get database queries from configuration files
        self.prepare_queries()

        # Connect to PostgreSQL database
        self.connect_db()


    def prepare_queries(self):
        """ Get database queries from configuration files """

        self.SQL_FITXA = ""
        ff = self.get_parameter("ARXIU_SQL")
        if ff.strip() == "":
            ff = str(os.path.join(self.project_folder, "config", "FitxaUrban_sql.txt"))
        f = open(ff, 'r')
        if f.closed :
            self.show_message("C", "Error al llegir \n\n" + ff)
            return
        for reg in f :
            self.SQL_FITXA += reg
        f.close()

        self.SQL_FITXA_ZONA = ""
        ff = self.get_parameter("ARXIU_SQL_ZONA")
        if ff.strip() == "":
            ff = str(os.path.join(self.project_folder, "config", "FitxaUrban_sql_zona.txt"))
        f = open(ff, 'r')
        if f.closed :
            self.show_message("C", "Error al llegir \n\n" + ff)
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
        if self.get_parameter("BD_SERVICE") == "" :
            db.setHostName(self.get_parameter("BD_HOST"))
            db.setDatabaseName(self.get_parameter("BD_DATABASE"))
            db.setUserName(self.get_parameter("BD_USER"))
            db.setPassword(self.get_parameter("BD_PASS"))
            db.setPort(int(self.get_parameter("BD_PORT")))
        else:
            db.setConnectOptions(f"service={self.get_parameter('BD_SERVICE')}")
        db.open()
        if db.isOpen() == 0 :
            self.show_message("C", "No s'ha pogut obrir la Base de Dades\n\n'" + db.lastError().text())
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
            self.show_message("C", f"File not found: {config_path}")
            return ""

        f = open(config_path, "r", encoding="UTF-8")
        if f.closed:
            self.show_message("C", f"Error al llegir arxiu configuració\n\n{ff}")
            return ""

        conf = ""
        for reg in f:
            if len(reg) > 5:
                if reg[0] != "#" and reg.find(" = ") != -1:
                    conf += reg.strip()+"\n"
        f.close()

        return conf


    def get_parameter(self, param):
        """ Get value of parameter @param from configuration file """

        if self.config_data.find(param + " = ") == -1:
            self.log_info(f"Parameter not found: {param}")
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


    def activate_tool(self):

        k = ""
        if self.config_data.find("LAYER_NAME" + " = ") != -1:
            k = self.config_data.split("LAYER_NAME" + " = ")[1].split("\n")[0]
        if k == "":
            self.show_message("I", "No hi ha cap configuració de projecte qgs carregada")
            return

        self.log_info(f"Capa: {k}")
        registry = QgsProject.instance()
        layer = registry.mapLayersByName(k)[0]
        if layer is None:
            self.show_message("C", f"Layer {k} no està carregada")
            return

        self.iface.mapCanvas().setMapTool(self.tool)
        self.action.setChecked(True)


    def deactivate_tool(self):

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


    def show_message(self, av, t):
        """ Show message dialog """

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

        query = QSqlQuery(db)
        sql = f"{self.SQL_FITXA_ZONA.split('$ID_VALUE')[0]}{self.id_selec}{self.SQL_FITXA_ZONA.split('$ID_VALUE')[1]}"
        if query.exec_(sql) == 0:
            msg = f"Error al llegir informació per fitxa zona\n\n{query.lastError().text()}"
            self.show_message("C", msg)
            query.clear()
            return

        camps = self.get_parameter("ZONES_ITEMS")
        per_int = query.record().indexOf(self.get_parameter("ZONA_AREA_%_NAME"))
        index_qg_tipus = query.record().indexOf('qg_tipus')
        per_min = int(self.get_parameter("ZONA_AREA_%_MINIM"))
        lispdfs = []

        # Get layouts 'PDF_ZONES' and 'PDF_SISTEMES'
        layout_zones = get_print_layout(self.get_parameter('PDF_ZONES'))
        if layout_zones is None:
            self.show_message("C", f"No s'ha trobat la plantilla: {self.get_parameter('PDF_ZONES')}")
            return

        layout_sistemes = get_print_layout(self.get_parameter('PDF_SISTEMES'))
        if layout_sistemes is None:
            self.show_message("C", f"No s'ha trobat la plantilla: {self.get_parameter('PDF_SISTEMES')}")

        # Process all records
        while query.next():
            if query.value(per_int) < per_min:
                continue

            total = query.record().count()
            for i in range(total):
                set_project_variable(camps.split(",")[i], query.value(i))
                sector_item = self.get_parameter("DESCR_SECTOR_ITEM")
                value = None
                if self.sector_codi != "NULL":
                    value = f'{self.sector_codi} - {self.sector_desc}'
                set_project_variable(sector_item, value)

            set_project_variable(self.get_parameter("DESCR_CLASSI_ITEM"), f'{self.classi_codi} - {self.classi_desc}')

            # Get layout from field 'qg_tipus': 'zones' or 'sistemes'
            layout = layout_zones
            qg_tipus = query.value(index_qg_tipus)
            self.log_info(f"Tipus de qualificació: {qg_tipus}")
            if qg_tipus == 'SISTEMES':
                layout = layout_sistemes
            layout.refresh()

            # Check if different folder per user or not
            nl = ""
            if self.get_parameter("DIR_PDFS_MULTI") == "SI":
                nl = socket.gethostname() + "(" + time.strftime("%d")+")_"

            # Export layout to PDF
            filename = f'{nl}{self.refcat}_zona_{query.value(0)}.pdf'
            filepath = os.path.join(self.dir_pdfs, filename)
            exporter = QgsLayoutExporter(layout)
            if exporter is None:
                self.show_message("W", "Exporter is None")
                return

            result = exporter.exportToPdf(filepath, QgsLayoutExporter.PdfExportSettings())
            if result == QgsLayoutExporter.Success:
                self.log_info(f"Fitxer generat correctament: {filename}")
            else:
                self.show_message("W", "error")
            if self.get_parameter("PDF_ZONES_VISU") != "1":
                open_file(filepath)
            lispdfs.append(filepath)

        query.clear()

        self.create_merged_pdf(lispdfs)


    def create_merged_pdf(self, lispdfs):
        """ Create a PDF that includes all 'zones' """

        merger = PdfFileMerger()
        for file in lispdfs:
            merger.append(PdfFileReader(file))
        nl = ""
        if self.get_parameter("DIR_PDFS_MULTI") == "SI":
            nl = socket.gethostname() + "(" + time.strftime("%d") + ")_"
        filename = f'{nl}{self.refcat}_zones.pdf'
        filepath = os.path.join(self.dir_pdfs, filename)
        merger.write(filepath)
        if self.get_parameter("PDF_ZONES_VISU") != "2":
            open_file(filepath)


    def open_pdf_annex(self):

        self.log_info("open_pdf_annex")


    def run(self):

        if self.qgs_status == "NO":
            self.qgs_status = "SI"
            self.Preparar()
            if self.db_status == "NO" :
                self.show_message("C", "Errors en la preparació del plugin per al projecte")
                return

        # Get the active layer (where the selected form is)
        layer = self.iface.activeLayer()
        if layer is None :
            self.show_message("C", "No hi ha layer activat")
            return

        # Check selected features
        features = layer.selectedFeatures()
        if len(features) < 1:
            self.show_message("C", "No s'ha seleccionat res")
            return

        # If multiple features selected, get only the first one
        if len(features) > 1:
            layer.selectByIds([features[0].id()])
        feature = features[0]

        # Check parameter 'ID_NAME'
        id_index = feature.fieldNameIndex(self.get_parameter("ID_NAME"))
        if id_index < 0:
            self.show_message("C", "Manca paràmetre ID_INDEX")
            return

        self.id_selec = feature[id_index]

        global db
        qu = QSqlQuery(db)
        sq = self.SQL_FITXA.split("$ID_VALUE")[0]+str(self.id_selec)+self.SQL_FITXA.split("$ID_VALUE")[1]
        if qu.exec_(sq) == 0:
            self.show_message("C", "Error al llegir informació per fitxa\n\n" + qu.lastError().text())
            return
        if qu.next() == 0:
            self.show_message("C", "No s'ha trobat informació per fitxa\n\n" + qu.lastError().text())
            return
        if qu.value(0) is None:
            self.show_message("C", "No s'ha trobat informació per la fitxa")
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

        self.dialog = FitxaUrbanDialog()

        self.dialog.setFixedSize(self.dialog.size())
        if self.dtop!= 0 and self.dleft != 0:
            self.dialog.setGeometry(self.dleft, self.dtop, self.dialog.width(), self.dialog.height())
        self.dialog.label_5.setPixmap(QPixmap(self.get_parameter("ARXIU_LOGO")))
        self.dialog.Sortir.clicked.connect(self.close_dialog)
        self.dialog.btn_pdf_annex.setEnabled(False)

        # Static links
        link = u"<a href='file:///{:s}/condicions_generals.htm'>Condicions Generals</a>".format(self.dir_html)
        self.dialog.lblCondGenerals.setText(link)
        self.dialog.lblCondGenerals.linkActivated.connect(self.web_dialog)
        link = u"<a href='file:///{:s}/dotacio_aparcament.htm'>Dotació mínima d'aparcaments</a>".format(self.dir_html)
        self.dialog.lblDotacioAparc.setText(link)
        self.dialog.lblDotacioAparc.linkActivated.connect(self.web_dialog)
        link = u"<a href='file:///{:s}/regulacio_aparcament.htm'>Regulació particular de l'ús d'aparcaments</a>".format(self.dir_html)
        self.dialog.lblRegulacioAparc.setText(link)
        self.dialog.lblRegulacioAparc.linkActivated.connect(self.web_dialog)
        link = u"<a href='file:///{:s}/param_finca.htm'>Paràmetres Finca</a>".format(self.dir_html)
        self.dialog.lblParamFinca.setText(link)
        self.dialog.lblParamFinca.linkActivated.connect(self.web_dialog)
        link = u"<a href='file:///{:s}/param_edificacio.htm'>Paràmetres Edificació</a>".format(self.dir_html)
        self.dialog.lblParamEdificacio.setText(link)
        self.dialog.lblParamEdificacio.linkActivated.connect(self.web_dialog)

        # Show data
        self.refcat = str(qu.value(int(self.get_parameter("REFCAT"))))
        self.area = float(qu.value(int(self.get_parameter("AREA"))))
        self.adreca = str(qu.value(int(self.get_parameter("ADRECA"))))
        self.sector_codi = str(qu.value(int(self.get_parameter("CODI_SECTOR"))))
        self.sector_desc = str(qu.value(int(self.get_parameter("DESCR_SECTOR"))))
        self.classi_codi = str(qu.value(int(self.get_parameter("CODI_CLASSI"))))
        self.classi_desc = str(qu.value(int(self.get_parameter("DESCR_CLASSI"))))
        self.dialog.refcat.setText(self.refcat)
        area = (u'{}'.format(round(self.area,1))).rstrip('0').rstrip('.')
        self.dialog.area.setText(area)
        self.dialog.txtAdreca.setText(self.adreca)
        if self.sector_codi != "NULL": # It may not be part of any sector
            self.dialog.txtSector.setText(f'{self.sector_codi} - {self.sector_desc}')
            self.dialog.lblSector.setText(u"<a href='file:///{:s}'>Veure normativa</a>".format(os.path.join(self.dir_sector,'{:s}.htm'.format('{}'.format(self.sector_codi)))))
            self.dialog.lblSector.linkActivated.connect(self.web_dialog)
        else:
            self.dialog.lblSector.setHidden(True)

        self.dialog.txtClass.setText(f'{self.classi_codi} - {self.classi_desc}')
        self.dialog.lblClass.setText(u"<a href='file:///{:s}'>Veure normativa</a>".format(os.path.join(self.dir_classi,'{:s}.htm'.format('{}'.format(self.classi_codi)))))
        self.codes = str(qu.value(int(self.get_parameter("CODI_ZONES")))).replace("{", "").replace("}", "")
        self.percents = str(qu.value(int(self.get_parameter("PERCENT_ZONES")))).replace("{", "").replace("}", "")
        self.general_codes = str(qu.value(int(self.get_parameter("CODI_GENERAL_ZONES")))).replace("{", "").replace("}", "")

        # Enable button 'Obrir Annex' only for codes: '1a1', '3b1'
        self.dialog.btn_pdf_annex.setEnabled(False)
        self.log_info(self.codes)
        if '1a1' in self.codes or '3b1' in self.codes:
            self.dialog.btn_pdf_annex.setEnabled(True)

        for i in range(0, 4):
            txtClau = getattr(self.dialog, f'txtClau_{i + 1}')
            txtPer = getattr(self.dialog, f'txtPer_{i + 1}')
            lblOrd = getattr(self.dialog, f'lblOrd_{i + 1}')
            try:
                txtClau.setText(f'{self.codes.split(",")[i]}')
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
                lblOrd.setText(f'{zz}')
                lblOrd.linkActivated.connect(self.web_dialog)
            except IndexError:
                lblOrd.setHidden(True)

        qu.clear()

        self.dialog.show()


        def make_show_ubicacio_pdf():
            """ PDF generation functions """

            # Make temporary layer
            try:
                self.iface.removeMapLayers(self.get_parameter("SELEC_NAME"))
            except:
                a = 1

            vl = self.iface.addVectorLayer("Polygon?crs=epsg:25831&field=id:integer&index=yes", "temp_print_polygon", "memory")
            k = self.get_parameter("ARXIU_QML")
            if k.strip() == "":
                k=os.path.join(self.plugin_dir,"FitxaUrban.qml")
            vl.loadNamedStyle(k)
            vl.setName(self.get_parameter("SELEC_NAME"))
            pr = vl.dataProvider()
            fet = QgsFeature()
            fet.setGeometry(QgsGeometry(feature.geometry()))  # copy the geometry
            pr.addFeatures([fet])
            vl.updateExtents()
            move_layer(vl, 0)

            def refreshed():

                # Disconnect signal
                self.iface.mapCanvas().mapCanvasRefreshed.disconnect(refreshed)
                composition = None
                for item in QgsProject.instance().layoutManager().printLayouts():
                    if item.name() == self.get_parameter("PDF_UBICACIO") :
                        composition = item
                        break
                if composition is None:
                    self.show_message("C", "No s'ha trobat plantilla fitxa en el projecte")
                    return

                # Set values
                set_project_variable(self.get_parameter("REFCAT_ITEM"), self.refcat)
                set_project_variable(self.get_parameter("AREA_ITEM"), '{:.0f}'.format(self.area))
                set_project_variable(self.get_parameter("ADRECA_ITEM"), self.adreca)

                # Set main map to the propper position
                #main_map = composition.itemById('Mapa principal')
                #main_map = composition.referenceMap()
                main_map=layout_item(composition,self.get_parameter("MAPA_NAME"),QgsLayoutItemMap)
                center_map(main_map, feature)

                # Add temporal layer to composition
                legend = layout_item(composition,self.get_parameter("LLEGENDA_NAME"),QgsLayoutItemLegend)
                legend_root = legend.model().rootGroup()
                legend_root.insertLayer(0, vl)

                # Make PDF
                nl = ""
                if self.get_parameter("DIR_PDFS_MULTI") == "SI":
                    nl = socket.gethostname()+"("+time.strftime("%d")+")_"
                filename = os.path.join(self.dir_pdfs, '{}{}_ubicacio.pdf'.format(nl,self.refcat))
                exporter = QgsLayoutExporter(composition)
                exporter.exportToPdf(filename,QgsLayoutExporter.PdfExportSettings())
                open_file(filename)

                # Delete temporary layer
                legend_root.removeLayer(vl)
                QgsProject.instance().removeMapLayers([vl.id()])

                self.iface.mapCanvas().refresh()

            self.iface.mapCanvas().mapCanvasRefreshed.connect(refreshed)
            self.iface.mapCanvas().refresh()

        # Connect the click signal to the functions
        self.dialog.lblClass.linkActivated.connect(self.web_dialog)
        self.dialog.btnParcelaPdf.clicked.connect(make_show_ubicacio_pdf)
        self.dialog.btnClauPdf_1.clicked.connect(self.create_pdf_zones)
        self.dialog.btn_pdf_annex.clicked.connect(self.open_pdf_annex)

        self.dialog.exec_()


    def web_dialog(self, url):

        QgsMessageLog.logMessage("Opened url: " + url)
        dialog = FitxaUrbanVista()
        dialog.setWindowFlags(Qt.WindowSystemMenuHint | Qt.WindowTitleHint | Qt.WindowMaximizeButtonHint)
        dialog.webView.setUrl(QUrl(url))
        dialog.webView.setWhatsThis(url)
        dialog.Sortir.clicked.connect(dialog.close)
        dialog.Exportar.clicked.connect(partial(self.export_pdf, dialog))
        dialog.exec_()


    def export_pdf(self, dialog):

        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setPaperSize(QPrinter.A4)
        printer.setOrientation(QPrinter.Portrait)
        printer.setPageMargins(15, 15, 15, 15, QPrinter.Millimeter)
        filename = str(os.path.splitext(os.path.basename(dialog.webView.whatsThis()))[0])+u".pdf"
        filename = os.path.join(self.dir_pdfs,filename)
        printer.setOutputFileName(filename)
        dialog.webView.print_(printer)
        open_file(filename)


    def get_pdf_printer(self, name):

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


# endregion