# -*- coding: utf-8 -*-
from PyQt5.QtCore import QSettings, QUrl, QDir
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import QAction, QFileDialog, QMessageBox
from PyQt5.QtPrintSupport import QPrinter
from PyQt5.QtSql import *
from qgis.core import QgsFeature, QgsGeometry, QgsMessageLog, QgsProject, QgsLayoutExporter,  QgsRectangle, \
    QgsLayoutItemMap, QgsLayoutItemLegend

import os, socket, time, glob
from functools import partial
from .lib.PyPDF2 import PdfFileMerger, PdfFileReader

from .ui_manager import MainDialog
from .ui_manager import WebDialog
from .urban_planning_tool import UrbanPlanningTool
from .urban_planning_utils import open_file, center_map, move_layer, layout_item, get_print_layout, set_project_variable

global db


class UrbanPlanning:

    def __init__(self, iface):

        self.iface = iface
        self.plugin_dir = None
        self.plugin_name = None
        self.settings = None
        self.action = None
        self.dialog = None
        self.db_status = "NO"
        self.qgs_status = "NO"
        self.config_data = None
        self.dtop = 0
        self.dleft = 0
        self.sql_classificacio = None
        self.sql_general = None
        self.sql_sector = None
        self.sql_zona = None
        self.area_classi = None
        self.descr_classi = None
        self.descr_sector = None


    def initGui(self):

        self.plugin_dir = os.path.dirname(__file__)
        self.plugin_name = os.path.basename(self.plugin_dir)
        self.settings = QSettings("PSIG", "UrbanPlanning")
        self.config_data = self.read_config_file()

        filename = os.path.abspath(os.path.join(self.plugin_dir, "img", f"{self.plugin_name}_logo.png"))
        self.icon = QIcon(filename)
        self.tool = UrbanPlanningTool(self.iface.mapCanvas(), self)
        self.action = QAction(self.icon, "UrbanPlanning", self.iface.mainWindow())
        self.action.setCheckable(True)
        self.action.triggered.connect(self.activate_tool)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu("UrbanPlanning", self.action)
        self.iface.mapCanvas().mapToolSet.connect(self.deactivate_tool)


    def init_config(self):
        """ Function called when a QGIS project is loaded """

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
        
        # Get PDF report folders
        self.dir_pdfs = self.get_parameter("DIR_PDFS")
        if self.dir_pdfs == "":
            self.dir_pdfs = os.path.join(self.project_folder, 'pdfs')
        d = QDir(self.dir_pdfs)
        if d.exists() == 0:
            if d.mkdir(self.dir_pdfs) == 0:
                self.show_message("C", f"No s'ha pogut crear carpeta directori pdf's\n\n{self.dir_pdfs}")
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

        # Get HTML folders
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
        self.dir_annex = self.get_parameter("DIR_ANNEX")
        if self.dir_annex == "":
            self.dir_annex = os.path.join(self.dir_html, 'annexos_claus')
        
        # Get database queries from configuration files
        self.prepare_queries()

        # Connect to PostgreSQL database
        self.connect_db()


    def prepare_queries(self):
        """ Get database queries from configuration files """

        self.sql_classificacio = self.read_sql_file("SQL_CLASSIFICACIO")
        self.sql_general = self.read_sql_file("SQL_GENERAL")
        self.sql_sector = self.read_sql_file("SQL_SECTOR")
        self.sql_zona = self.read_sql_file("SQL_ZONA")


    def read_sql_file(self, parameter):

        sql_content = ""
        filepath = self.get_parameter(parameter)
        if filepath.strip() == "":
            filepath = str(os.path.join(self.project_folder, "config", f"{parameter.lower()}.sql"))
        if not os.path.exists(filepath):
            self.show_message("C", f"File not found:\n {filepath}")
            return None
        f = open(filepath, 'r')
        if f.closed:
            self.show_message("C", f"Error al llegir \n\n{filepath}")
            return None
        for reg in f :
            sql_content += reg
        f.close()

        return sql_content


    def connect_db(self):
        """ Connect to PostgreSQL database """

        global db

        if self.db_status == "SI" :
            db.close()
            db = QSqlDatabase()
            db.removeDatabase("UrbanPlanning")
        db = QSqlDatabase.addDatabase("QPSQL","UrbanPlanning")
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

        config_path = str(os.path.join(self.project_folder, "config", f"{self.plugin_name}.config"))
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
                if reg[0] != "#" and reg.find(" =") != -1:
                    conf += reg.strip()+"\n"
        f.close()

        return conf


    def get_parameter(self, param):
        """ Get value of parameter @param from configuration file """

        if self.config_data.find(param) == -1:
            self.log_info(f"Parameter not found: {param}")

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

        QgsMessageLog.logMessage(str(msg), None, 0)


    def unload(self):

        global db

        if self.db_status == "SI":
            db.close()
            db = QSqlDatabase()
            db.removeDatabase("UrbanPlanning")
            self.db_status = "NO"
            self.qgs_status = "NO"
        self.action.setChecked(False)
        if self.dialog:
            self.close_dialog()
        self.iface.removePluginMenu('UrbanPlanning', self.action)
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
        m.setText(str(t))
        m.setStandardButtons(QMessageBox.Ok)
        b = m.button(QMessageBox.Ok)
        b.setText("Segueix")
        m.exec_()


    def create_pdf_zones(self):

        global db

        query = QSqlQuery(db)
        sql = self.sql_zona.replace('$ID_VALUE', str(self.id_selec))
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
                if self.descr_sector != "":
                    value = f'{self.descr_sector[:-2]}'
                set_project_variable(sector_item, value)

            set_project_variable(self.get_parameter("DESCR_CLASSI_ITEM"), f'{self.descr_classi[:-2]}')
            set_project_variable(self.get_parameter("AREA_CLASSI_ITEM"), f'{self.area_classi[:-2]}')

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
        """ Open PDF file associated with code: '1a1', '3b1' """

        code = None
        if '1a1' in self.codes:
            code = '1a1'
        elif '3b1' in self.codes:
            code = '3b1'

        if code is None:
            self.log_info(f"Code not found: {code}")
            return

        filepath = os.path.join(self.dir_annex, f'annex_{code}.pdf')
        if not os.path.exists(filepath):
            self.log_info(f"File not found: {filepath}")
            return

        self.log_info(f"File opened: {filepath}")
        open_file(filepath)


    def run(self):

        if self.qgs_status == "NO":
            self.qgs_status = "SI"
            self.init_config()
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

        # Get id (field 'ninterno') of selected feature
        self.id_selec = feature[id_index]
        self.log_info(f"id_selec: {self.id_selec}")

        # Get results of query "General"
        query_general = self.get_query(self.sql_general, self.id_selec, True)
        if query_general is None:
            return

        # Get results of query "Classificacio"
        query_classificacio = self.get_query(self.sql_classificacio, self.id_selec)
        if query_classificacio is None:
            return

        # Get results of query "Sector"
        query_sector = self.get_query(self.sql_sector, self.id_selec)
        if query_sector is None:
            return

        # Set dialog and set its atributes
        self.set_dialog()

        # Fill GroupBox 'Ubicacio'
        self.fill_ubicacio(query_general)

        # Fill GroupBox 'Sector'
        self.fill_sector(query_sector)

        # Fill GroupBox 'Classificacio'
        self.fill_classificacio(query_classificacio)

        # Fill GroupBox 'Zones Planejament'
        self.fill_zones_planejament(query_general)

        # Fill GroupBox 'Annex'
        self.fill_annex()

        # Set signals
        self.set_signals(feature)

        query_general.clear()
        self.dialog.show()


    def get_query(self, sql, id_selec, check_data=False):

        if sql is None:
            return None

        global db
        query = QSqlQuery(db)
        sql = sql.replace('$ID_VALUE', str(id_selec))
        if query.exec_(sql) == 0:
            self.show_message("C", f"Error al llegir informació per fitxa\n\n{query.lastError().text()}")
            return None

        has_rows = query.next()
        if check_data:
            if has_rows == 0:
                self.show_message("C", f"No s'ha trobat informació per fitxa\n\n{query.lastError().text()}")
                return None
            if query.value(0) is None:
                self.show_message("C", "No s'ha trobat informació per la fitxa")
                return None

        return query


    def set_dialog(self):

        if self.dialog:
            try:
                self.dtop = self.dialog.geometry().top()
                self.dleft = self.dialog.geometry().left()
                self.dialog.close()
            except:
                self.dtop = 0
                self.dleft = 0

        self.dialog = MainDialog()
        self.dialog.setFixedSize(self.dialog.size())
        if self.dtop!= 0 and self.dleft != 0:
            self.dialog.setGeometry(self.dleft, self.dtop, self.dialog.width(), self.dialog.height())

        logo_file = self.get_parameter("ARXIU_LOGO")
        if logo_file.strip() == "":
            logo_file = os.path.join(self.plugin_dir, "img", "ESC0401.png")
        if not os.path.exists(logo_file):
            self.show_message("W", f"File not found: {logo_file}")
        else:
            self.dialog.lbl_logo.setPixmap(QPixmap(logo_file))


    def fill_ubicacio(self, query):
        """ Fill GroupBox 'Ubicacio' """

        self.refcat = str(query.value(int(self.get_parameter("REFCAT"))))
        self.area = float(query.value(int(self.get_parameter("AREA"))))
        self.adreca = str(query.value(int(self.get_parameter("ADRECA"))))
        self.dialog.refcat.setText(self.refcat)
        area = (u'{}'.format(round(self.area,1))).rstrip('0').rstrip('.')
        self.dialog.area.setText(area)
        self.dialog.txtAdreca.setText(self.adreca)


    def fill_sector(self, query):
        """ Fill GroupBox 'Sector' """

        # Hide all widgets
        for i in range(0, 3):
            if hasattr(self.dialog, f"lbl_sector_{i+1}"):
                widget = getattr(self.dialog, f"lbl_sector_{i+1}")
                widget.setVisible(False)
            if hasattr(self.dialog, f"lbl_sector_{i+1}_perc"):
                widget = getattr(self.dialog, f"lbl_sector_{i+1}_perc")
                widget.setVisible(False)

        # Fill widgets
        self.descr_sector = ""
        for i in range(0, query.size()):
            codi = str(query.value(0))
            desc = str(query.value(1))
            item = f"{codi} - {desc}"
            self.descr_sector += f"{item}; "
            if codi != "NULL":  # It may not be part of any sector
                file = os.path.join(self.dir_sector, '{:s}.htm'.format('{}'.format(codi)))
                link = f"<a href='file:///{file}'>{item}</a>"
                perc = query.value(3)
                if hasattr(self.dialog, f"lbl_sector_{i+1}"):
                    widget = getattr(self.dialog, f"lbl_sector_{i+1}")
                    widget.setText(link)
                    widget.linkActivated.connect(self.web_dialog)
                    widget.setVisible(True)
                if hasattr(self.dialog, f"lbl_sector_{i+1}_perc"):
                    widget = getattr(self.dialog, f"lbl_sector_{i+1}_perc")
                    if perc:
                        value = u'{:02.2f}'.format(float(perc))
                        widget.setText(f"{value} %")
                        widget.setVisible(True)

            query.next()


    def fill_classificacio(self, query):
        """ Fill GroupBox 'Classificacio' """

        # Hide all widgets
        for i in range(0, 3):
            if hasattr(self.dialog, f"lbl_class_{i+1}"):
                widget = getattr(self.dialog, f"lbl_class_{i+1}")
                widget.setVisible(False)
            if hasattr(self.dialog, f"lbl_class_{i+1}_perc"):
                widget = getattr(self.dialog, f"lbl_class_{i+1}_perc")
                widget.setVisible(False)

        # Fill widgets
        self.descr_classi = ""
        self.area_classi = ""
        for i in range(0, query.size()):
            codi = str(query.value(0))
            desc = str(query.value(1))
            item = f"{codi} - {desc}"
            self.descr_classi += f"{item}; "
            file = os.path.join(self.dir_classi, '{:s}.htm'.format('{}'.format(codi)))
            link = f"<a href='file:///{file}'>{item}</a>"
            area = query.value(2)
            perc = query.value(3)
            if hasattr(self.dialog, f"lbl_class_{i+1}"):
                widget = getattr(self.dialog, f"lbl_class_{i+1}")
                widget.setText(link)
                widget.linkActivated.connect(self.web_dialog)
                widget.setVisible(True)
            if hasattr(self.dialog, f"lbl_class_{i+1}_perc"):
                widget = getattr(self.dialog, f"lbl_class_{i+1}_perc")
                if perc:
                    area = u'{:02.2f}'.format(float(area))
                    perc = u'{:02.2f}'.format(float(perc))
                    item_area = f"{area} m2 ({perc} %)"
                    self.area_classi += f"{item_area}; "
                    widget.setText(f"{perc} %")
                    widget.setVisible(True)

            query.next()


    def fill_zones_planejament(self, query):
        """ Fill GroupBox 'Zones Planejament' """

        self.codes = str(query.value(int(self.get_parameter("CODI_ZONES")))).replace("{", "").replace("}", "")
        self.percents = str(query.value(int(self.get_parameter("PERCENT_ZONES")))).replace("{", "").replace("}", "")
        general_codes = str(query.value(int(self.get_parameter("CODI_GENERAL_ZONES")))).replace("{", "").replace("}", "")

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
                filename = f'{general_codes.split(",")[i]}.htm'
                filepath = os.path.join(self.dir_orden, filename)
                if os.path.isfile(filepath):
                    zz = f"<a href='file:///{filepath}'>{filename}</a>"
                else:
                    zz = general_codes.split(",")[i]
                lblOrd.setText(f'{zz}')
                lblOrd.linkActivated.connect(self.web_dialog)
            except IndexError:
                lblOrd.setHidden(True)

        # Enable button 'Obrir Annex' only for codes: '1a1', '3b1'
        self.dialog.btn_pdf_annex.setEnabled(False)
        if '1a1' in self.codes or '3b1' in self.codes:
            self.dialog.btn_pdf_annex.setEnabled(True)


    def fill_annex(self):
        """ Fill GroupBox 'Annex' """

        link = f"<a href='file:///{self.dir_html}/condicions_generals.htm'>Condicions Generals</a>"
        self.dialog.lblCondGenerals.setText(link)
        self.dialog.lblCondGenerals.linkActivated.connect(self.web_dialog)
        link = f"<a href='file:///{self.dir_html}/dotacio_aparcament.htm'>Dotació mínima d'aparcaments</a>"
        self.dialog.lblDotacioAparc.setText(link)
        self.dialog.lblDotacioAparc.linkActivated.connect(self.web_dialog)
        link = f"<a href='file:///{self.dir_html}/regulacio_aparcament.htm'>Regulació particular de l'ús d'aparcaments</a>"
        self.dialog.lblRegulacioAparc.setText(link)
        self.dialog.lblRegulacioAparc.linkActivated.connect(self.web_dialog)
        link = f"<a href='file:///{self.dir_html}/param_finca.htm'>Paràmetres Finca</a>"
        self.dialog.lblParamFinca.setText(link)
        self.dialog.lblParamFinca.linkActivated.connect(self.web_dialog)
        link = f"<a href='file:///{self.dir_html}/param_edificacio.htm'>Paràmetres Edificació</a>"
        self.dialog.lblParamEdificacio.setText(link)
        self.dialog.lblParamEdificacio.linkActivated.connect(self.web_dialog)


    def set_signals(self, feature):

        self.dialog.rejected.connect(self.close_dialog)
        self.dialog.btn_pdf_annex.setEnabled(False)
        self.dialog.btnParcelaPdf.clicked.connect(partial(self.make_show_ubicacio_pdf, feature))
        self.dialog.btnClauPdf_1.clicked.connect(self.create_pdf_zones)
        self.dialog.btn_pdf_annex.clicked.connect(self.open_pdf_annex)


    def make_show_ubicacio_pdf(self, feature):
        """ PDF generation functions """

        # Make temporary layer
        try:
            self.iface.removeMapLayers(self.get_parameter("SELEC_NAME"))
        except:
            a = 1

        temp_print_polygon_layer = "Polygon?crs=epsg:25831&field=id:integer&index=yes"
        vl = self.iface.addVectorLayer(temp_print_polygon_layer, "temp_print_polygon", "memory")
        qml_file = self.get_parameter("ARXIU_QML")
        if qml_file.strip() == "":
            qml_file = os.path.join(self.plugin_dir, "qml", f"{self.plugin_name}.qml")
        if not os.path.exists(qml_file):
            self.show_message(f"File not found: {qml_file}")
        else:
            vl.loadNamedStyle(qml_file)

        vl.setName(self.get_parameter("SELEC_NAME"))
        pr = vl.dataProvider()
        fet = QgsFeature()
        fet.setGeometry(QgsGeometry(feature.geometry()))
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
            main_map= layout_item(composition, self.get_parameter("MAPA_NAME"), QgsLayoutItemMap)
            center_map(main_map, feature)

            # Add temporal layer to composition
            legend = layout_item(composition, self.get_parameter("LLEGENDA_NAME"), QgsLayoutItemLegend)
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


    def web_dialog(self, url):

        self.log_info(f"Opened url: {url}")
        dialog = WebDialog()
        dialog.webView.setUrl(QUrl(url))
        dialog.webView.setWhatsThis(url)
        dialog.Exportar.clicked.connect(partial(self.export_pdf, dialog))
        dialog.exec_()


    def export_pdf(self, dialog):

        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setPaperSize(QPrinter.A4)
        printer.setOrientation(QPrinter.Portrait)
        printer.setPageMargins(15, 15, 15, 15, QPrinter.Millimeter)
        filename = str(os.path.splitext(os.path.basename(dialog.webView.whatsThis()))[0])+u".pdf"
        filename = os.path.join(self.dir_pdfs, filename)
        printer.setOutputFileName(filename)
        dialog.webView.print_(printer)
        open_file(filename)


    def get_pdf_printer(self, name):

        printer = QPrinter(QPrinter.HighResolution)
        filename = os.path.join(self.settings.value("save path", os.path.expanduser("~")), name + ".pdf")
        path = QFileDialog.getSaveFileName(None, None, filename, "PDF (*.pdf)")
        if path[0] is not None and path != "":
            self.settings.setValue("save path", os.path.dirname(path[0]))
            printer.setOutputFileName(path[0])
            return printer
        else:
            return None

