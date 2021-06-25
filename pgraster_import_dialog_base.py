# -*- coding: utf-8 -*-
"""
/***************************************************************************
 PGRasterImportDialog
                                 A QGIS plugin
 Import Raster to PgRaster
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                             -------------------
        begin                : 2021-06-24
        git sha              : $Format:%H$
        copyright            : (C) 2021 by Dr. Horst Duester / Sourcepols
        email                : horst.duester@sourcepole.ch
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
import os
import psycopg2
from qgis.PyQt import uic
from qgis.core import *
from qgis.utils import OverrideCursor
from qgis.PyQt.QtCore import Qt,  pyqtSlot,  QSettings
from qgis.PyQt.QtWidgets import QDialog,  QMessageBox
from .raster.raster_upload import RasterUpload
from .about.about import About

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'pgraster_import_dialog_base.ui'))


class PGRasterImportDialog(QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(PGRasterImportDialog, self).__init__(parent)
        # Set up the user interface from Designer through FORM_CLASS.
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)
        self.getDbSettings()
        self.cmb_map_layer.setCurrentIndex(-1) 
        self.cmb_map_layer.setFilters(QgsMapLayerProxyModel.RasterLayer)        
        self.excluded_layers()
        
    def excluded_layers(self):
        excepted_layers = []
        for i in range(self.cmb_map_layer.count()):
            layer = self.cmb_map_layer.layer(i)
            if layer.dataProvider().name() == 'postgresraster':
                excepted_layers.append(layer)
                
        self.cmb_map_layer.setExceptedLayerList(excepted_layers)
        
    def enable_buttons(self):
        if self.cmb_map_layer.currentIndex() == -1 or self.cmb_db_connections.currentIndex() == 0:
            self.btn_upload.setEnabled(False)
        else:
            self.btn_upload.setEnabled(True)
            
    def table_exists(self,  conn,  schema,  table):
            
        sql = """
            SELECT exists( 
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = '%s' and table_name = '%s')
            """ % (schema,  table)
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()        

        return rows[0][0]
            

    def getDbSettings(self):
        settings = QSettings()
        settings.beginGroup('PostgreSQL/connections')
        self.cmb_db_connections.addItem('------------')
        self.cmb_db_connections.addItems(settings.childGroups())
        settings.endGroup()
        self.cmb_db_connections.setCurrentIndex(0)
        
    def init_DB(self, selectedServer):
        if self.cmb_db_connections.currentIndex() == 0:
            return None
            
        settings = QSettings()
        mySettings = '/PostgreSQL/connections/' + selectedServer
        DBNAME = settings.value(mySettings + '/database')
        DBUSER = settings.value(mySettings + '/username')
        DBHOST = settings.value(mySettings + '/host')
        DBPORT = settings.value(mySettings + '/port')
        DBPASSWD = settings.value(mySettings + '/password')

        if DBUSER == '' or DBPASSWD == '':
            connection_info = "dbname='{0}' host='{1}' port={2}".format(DBNAME,  DBHOST,  DBPORT)
            (success, user, password) = QgsCredentials.instance().get(connection_info, None, None)
            if not success:
                return None
            QgsCredentials.instance().put(connection_info, user, password)
            DBUSER = user
            DBPASSWD = password
        else:
            connection_info = "dbname='{0}' host='{1}' port={2} user='{3}' password='{4}'".format(DBNAME,  DBHOST,  DBPORT,  DBUSER,  DBPASSWD)

        try:
            conn = psycopg2.connect(connection_info)
            self.cmb_schema.addItems(self.db_schemas(conn))
        except:
            QMessageBox.information(
                None, self.tr('Error'),
                self.tr('No Database Connection Established.'))
            self.cmb_db_connections.setCurrentIndex(0)
            return None
            
        return conn
        
    def db_schemas(self,  conn):
      
        sql = """
             SELECT n.nspname AS "Name"
               FROM pg_catalog.pg_namespace n                                      
             WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'     
             ORDER BY 1;        
        """
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        
        schema_list = []
        for row in rows:
            schema_list.append(row[0])
            
        return schema_list
                    
        
#    @pyqtSlot()
#    def on_button_box_accepted(self):

    
    @pyqtSlot()
    def on_btn_close_clicked(self):
        """
        Slot documentation goes here.
        """
        self.close()
    
    
    @pyqtSlot(str)
    def on_cmb_db_connections_currentIndexChanged(self, p0):
        """
        Slot documentation goes here.
        
        @param p0 DESCRIPTION
        @type str
        """
        self.init_DB(p0)
        self.enable_buttons()
            
    
    @pyqtSlot()
    def on_btn_upload_clicked(self):
        """
        Slot documentation goes here.
        """
        conn = self.init_DB(self.cmb_db_connections.currentText())
        cursor = conn.cursor()
        
        if self.table_exists(conn,  self.cmb_schema.currentText(),  self.lne_table_name.text()):
            result = QMessageBox.question(
                None,
                self.tr("Table exists"),
                self.tr("""The selected table already exists in the database. Do you want to overwrite the table?"""),
                QMessageBox.StandardButtons(
                    QMessageBox.No |
                    QMessageBox.Yes),
                QMessageBox.No)
            
            if result == QMessageBox.Yes:
                self.raster_upload(conn)
                return
            else:
                return
                
        else:
            self.raster_upload(conn)
            return
        
    
    def raster_upload(self,  conn):
#     If schema doesn't exists in DB create a new schema        
        if self.cmb_schema.currentText() not in self.db_schemas(conn):
            sql = """
            create schema {0}
            """.format(self.cmb_schema.currentText())
            cursor = conn.cursor()
            cursor.execute(sql)
        
        
        layer = self.cmb_map_layer.currentLayer()
        if layer.dataProvider().name() == 'gdal':
            raster_to_upload = {
                        'layer': layer,
                        'data_source': layer.source(),
                        'db_name': self.cmb_db_connections.currentText(),
                        'schema_name': self.cmb_schema.currentText(), 
                        'table_name': self.lne_table_name.text(),
                        'geom_column': 'rast'
                    }
            
            with OverrideCursor(Qt.WaitCursor):
                RasterUpload(conn,  raster_to_upload,  self.progress_label,  self.progress_bar)
                
            conn.close()
        else:
            res = QMessageBox.information(
                self,
                self.tr("Warning"),
                self.tr("""Layers of type {0} are not supported!""".format(layer.dataProvider().name())),
                QMessageBox.StandardButtons(
                    QMessageBox.Ok))
            
    
    @pyqtSlot()
    def on_btn_about_clicked(self):
        """
        Slot documentation goes here.
        """
        About().exec_()
    
    @pyqtSlot(str)
    def on_cmb_map_layer_currentIndexChanged(self, p0):
        """
        Slot documentation goes here.
        
        @param p0 DESCRIPTION
        @type str
        """
        self.lne_table_name.setText(self.cmb_map_layer.currentText())
