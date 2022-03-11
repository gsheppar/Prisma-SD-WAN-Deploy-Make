#!/usr/bin/env python3
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import sys
import io
from contextlib import redirect_stdout
import jinja2
import os
import requests
import csv
from cloudgenix_config.pull import pull
from cloudgenix_config.do import dosite
from cloudgenix_config.GetSite import get, tenant
from cloudgenix_config.cg_site_health_check_prisma import verify
import time
import subprocess
import logging
import ipcalc
from csv import DictReader


output_directory = "Configs"

######################### Thread Commands ###################################

class EmittingStream(QObject):

    textWritten = pyqtSignal(str)

    def write(self, text):
        self.textWritten.emit(str(text))

class WorkerSignals(QObject):
    '''
    Defines the signals available from a running worker thread.

    Supported signals are:

    finished
        No data

    error
        tuple (exctype, value, traceback.format_exc() )

    result
        object data returned from processing, anything

    progress
        int indicating % progress

    '''
    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)
    progress = pyqtSignal(int)
        

class WorkerPull(QRunnable):
    '''
    Worker thread
    '''
    def __init__(self, name, destroy_site, filename):
        super(WorkerPull, self).__init__()
        
        self.name = name
        self.destroy_site = destroy_site
        self.filename = filename
        self.signals = WorkerSignals()
    
    @pyqtSlot()
    def run(self):
        '''
        Your code goes in this function
        '''
        try:
            print("Starting backup please wait....")
            pull(self.name)
            result = "Site: " + self.name + " has now been backed up"
            self.signals.result.emit(result)
            try:
                if self.destroy_site == "destroy":
                    result = "Starting delete of " + self.name + " . Please wait..."
                    self.signals.result.emit(result)
                    dosite(self.filename, self.destroy_site)
                    result = "Site: " + self.name + " is now gone\n"
                    self.signals.result.emit(result)
                self.signals.finished.emit()
            except:
                result = "Site " + self.name + " destroy failed"
                self.signals.result.emit(result)
        except:
            result = "Backup failed for " + self.name
            self.signals.result.emit(result)

class WorkerDo(QRunnable):
    '''
    Worker thread
    '''
    def __init__(self, filename, destroy_site):
        super(WorkerDo, self).__init__()
        
        self.destroy_site = destroy_site
        self.filename = filename
        self.signals = WorkerSignals()
    
    @pyqtSlot()
    def run(self):
        '''
        Your code goes in this function
        '''
        try:
            print("Start push please wait....")
            result = "Starting push of " + self.filename + " . Please wait..."
            self.signals.result.emit(result)
            dosite(self.filename, self.destroy_site)
            result = "File " + self.filename + " has now been pushed\n"
            self.signals.result.emit(result)
            self.signals.finished.emit()
        except:
            result = "Deployment failed for " + self.filename
            self.signals.result.emit(result)
            

class WorkerVerify(QRunnable):
    '''
    Worker thread
    '''
    def __init__(self, name):
        super(WorkerVerify, self).__init__()
        
        self.name = name
        self.signals = WorkerSignals()
    
    @pyqtSlot()
    def run(self):
        '''
        Your code goes in this function
        '''
        try:
            result = "Start verification please wait...."
            self.signals.result.emit(result)
            verify(self.name)
            result = "Verification is complete\n"
            self.signals.result.emit(result)
            self.signals.finished.emit()
        except:
            result = "Verification failed"
            self.signals.result.emit(result)

######################### Main PyQt Window ###################################

class lineEditDemo(QWidget):
        def __init__(self,parent=None):
                super().__init__(parent)    
                
                self.csv_file = None
                self.jinja_file = None
                self.jinja_path = None
                self.site_push_check = None
                self.site_main_verify = None
                self.site_main_file = None
                self.sitefile = QComboBox()
                
                mac = "DS_Store"
                for dirname, dirnames, filenames in os.walk('./Configs'):
                    for filename in filenames:
                        if mac not in filename:
                            self.sitefile.addItem(filename)
                
                btn1 = QPushButton("Build Site")
                btn1.clicked.connect(self.pullCSV)
                btn2 = QPushButton("Deploy Site")
                btn2.clicked.connect(self.pushSite)
                btn3 = QPushButton("Clear Log")
                btn3.clicked.connect(self.clearLog)
                btn4 = QPushButton("Delete Site")
                btn4.clicked.connect(self.deleteSite)
                btn5 = QPushButton("Site Validation")
                btn5.clicked.connect(self.verify)
                btn8 = QPushButton("Choose")
                btn8.clicked.connect(self.getFiles)
                btn9 = QPushButton("Choose")
                btn9.clicked.connect(self.getJinja)
                btn10 = QPushButton("Open Site File")
                btn10.clicked.connect(self.openSite)
                
                layout = QFormLayout()
                self.site_db = QComboBox()
                layout.setLabelAlignment(Qt.AlignLeft)
                labelname = QLabel('Please select DB or IPAM source:')
                ipam_qhbox = QHBoxLayout()
                ipam_qhbox.addWidget(labelname)
                ipam_qhbox.addWidget(btn8)
                layout.addRow(ipam_qhbox)
                labelname = QLabel('Please select Jinja Template file:')
                jinja_qhbox = QHBoxLayout()
                jinja_qhbox.addWidget(labelname)
                jinja_qhbox.addWidget(btn9)
                layout.addRow(jinja_qhbox)
                labelname = QLabel('Select Site:')
                ipam_qhbox = QHBoxLayout()
                ipam_qhbox.addWidget(labelname)
                ipam_qhbox.addWidget(self.site_db)
                layout.addRow(ipam_qhbox)
                layout.addRow(btn1)
                
                layout_console = QFormLayout()
                self.text_output = QTextEdit()
                self.text_output.setReadOnly(True)
                self.text_output.setMinimumHeight(500)
                self.text_output.setMinimumWidth(400)
                layout_console.addRow(self.text_output)
                self.text_status = QTextEdit()
                self.text_status.setReadOnly(True)
                self.text_status.setStyleSheet("background-color: rgb(94, 255, 0);")
                self.text_status.setFixedSize(300,20)
                self.text_status.setText("Currently idle")
                process_qhbox = QHBoxLayout()
                labelup = QLabel('Current Task Status:')
                process_qhbox.addWidget(labelup)
                process_qhbox.addWidget(self.text_status)
                process_qhbox.addWidget(btn3)
                layout_console.addRow(process_qhbox)
                
                
                layout_push_site = QFormLayout()
                labelpush = QLabel('Select File:')
                push_qhbox = QHBoxLayout()
                push_qhbox.addWidget(labelpush)
                push_qhbox.addWidget(self.sitefile)
                layout_push_site.addRow(push_qhbox)
                layout_push_site.addRow(btn2, btn10)
                
                layout_site_verify = QFormLayout()
                layout_site_verify.addRow(btn5)
                
                        
                layout_delete = QFormLayout()
                self.site = QComboBox()
                                     
                labelname = QLabel('Select Site:')
                delete_qhbox = QHBoxLayout()
                delete_qhbox.addWidget(labelname)
                delete_qhbox.addWidget(self.site)
                layout_delete.addRow(delete_qhbox)
                layout_delete.addRow(btn4)                
                
                layout_site_verify.setFormAlignment(Qt.AlignCenter)
                layout_push_site.setFormAlignment(Qt.AlignCenter)
                layout_delete.setFormAlignment(Qt.AlignCenter)
                
                self.input_left_first = QGroupBox("Build Site")
                self.input_left_first.setLayout(layout)
                
                self.input_left_second = QGroupBox("Deploy Site")
                self.input_left_second.setLayout(layout_push_site)
                
                self.input_left_third = QGroupBox("Site Validation")
                self.input_left_third.setLayout(layout_site_verify)
                
                self.input_left_forth = QGroupBox("Delete Site")
                self.input_left_forth.setLayout(layout_delete)
                
                self.input_right = QGroupBox("Console Output")
                self.input_right.setLayout(layout_console)
                
                self.input_left_first.setStyleSheet('QGroupBox:title {'
                                 'subcontrol-origin: margin;'
                                 'padding-left: 10px;'
                                 'font: bold;'
                                 'padding-right: 10px; }')
                self.input_right.setStyleSheet('QGroupBox:title {'
                                 'subcontrol-origin: margin;'
                                 'padding-left: 10px;'
                                 'font: bold;'
                                 'padding-right: 10px; }')
                self.input_left_second.setStyleSheet('QGroupBox:title {'
                                 'subcontrol-origin: margin;'
                                 'padding-left: 10px;'
                                 'font: bold;'
                                 'padding-right: 10px; }')
                self.input_left_forth.setStyleSheet('QGroupBox:title {'
                                 'subcontrol-origin: margin;'
                                 'padding-left: 10px;'
                                 'font: bold;'
                                 'padding-right: 10px; }')
                self.input_left_third.setStyleSheet('QGroupBox:title {'
                                 'subcontrol-origin: margin;'
                                 'padding-left: 10px;'
                                 'font: bold;'
                                 'padding-right: 10px; }')
                
                mainLayout = QGridLayout()
                mainLayout.addWidget(self.input_left_first, 1, 0, 1, 1)                
                mainLayout.addWidget(self.input_left_second, 2, 0, 1, 1)
                mainLayout.addWidget(self.input_left_third, 3, 0, 1, 1) 
                mainLayout.addWidget(self.input_left_forth, 4, 0, 1, 1) 
                mainLayout.addWidget(self.input_right, 1, 1, 4, 1)
                
                # Write-Overwrites
                self.log = open("log.txt", "w")  # write mode
                self.log.write("Start Log File \n")
                
                if not os.path.exists(output_directory):
                    os.mkdir(output_directory)
                if not os.path.exists('Backup'):
                    os.makedirs('Backup')
                
                self.setLayout(mainLayout)
                self.setWindowTitle("Prisma SD-WAN Site Build")
                self.threadpool = QThreadPool()
                sys.stdout = EmittingStream(textWritten=self.output_terminal_written)
                sys.stderr = EmittingStream(textWritten=self.output_terminal_written)
                
                sites = get()
                if sites != None:
                    tenant()
                    for site_name in sites:
                        self.site.addItem(site_name)

######################### Console Output ###################################
               
        def output_terminal_written(self, text):
            text = os.linesep.join([s for s in text.splitlines() if s])
            self.log.write(text + "\n")
            if "mapquest" not in text:
                if text.find("STATUS: DOWN") != -1:
                    self.text_output.setTextColor(QColor( "red" ))
                    self.text_output.append(text)
                elif text.find("STATUS: GOOD") != -1:
                    self.text_output.setTextColor(QColor( "green" ))
                    self.text_output.append(text)
                elif text.find("STATUS: OFFLINE") != -1:
                    self.text_output.setTextColor(QColor( "red" ))
                    self.text_output.append(text)
                elif text.find("ION Status: CONNECTED") != -1:
                    self.text_output.setTextColor(QColor( "green" ))
                    self.text_output.append(text)
                elif text.find("ION Status: OFFLINE (!!!)") != -1:
                    self.text_output.setTextColor(QColor( "red" ))
                    self.text_output.append(text)
                elif text.find("No Alarm summaries") != -1:
                    self.text_output.setTextColor(QColor( "green" ))
                    self.text_output.append(text)
                elif text.find("No Alarms found") != -1:
                    self.text_output.setTextColor(QColor( "green" ))
                    self.text_output.append(text)
                elif text.find("No Alerts found") != -1:
                    self.text_output.setTextColor(QColor( "green" ))
                    self.text_output.append(text)
                elif text.find("STATUS: Operational") != -1:
                    self.text_output.setTextColor(QColor( "green" ))
                    self.text_output.append(text)
                elif text.find("ALARM: ") != -1:
                    self.text_output.setTextColor(QColor( "red" ))
                    self.text_output.append(text)
                elif text.find("ALERT CODE: ") != -1:
                    self.text_output.setTextColor(QColor( "red" ))
                    self.text_output.append(text)
                elif text.find("No unresolved google cloud issues detected") != -1:
                    self.text_output.setTextColor(QColor( "green" ))
                    self.text_output.append(text)
                else:
                    self.text_output.setTextColor(QColor( "black" ))
                    self.text_output.append(text)    
            
            

######################### Build CSV to YAML File ###########################
        
        def buildSite(self, site_csv_dict):
            try:              
                parameter_dict = dict()
                for key,value in site_csv_dict.items():
                    parameter_dict[key] = value[0]
                address_concat = ""
                if "street" in parameter_dict:
                    address_concat = parameter_dict['street']
                if "city" in parameter_dict:
                    address_concat += ", " + parameter_dict['city']
                if "state" in parameter_dict:   
                    address_concat += ", " + parameter_dict['state'] 
                if "post_code" in parameter_dict:
                    address_concat += ", " + parameter_dict['post_code'] 
                if "country" in parameter_dict:    
                    address_concat += ", " + parameter_dict['country']
                
                if address_concat != "":
                    address_concat = address_concat.strip()
                    latlon_request = self.getLATLONG(address_concat)
                    parameter_dict["site_lat"] = latlon_request[0]
                    parameter_dict["site_long"] = latlon_request[1]   
                self.createSITE(parameter_dict)
                print("\nConfiguration is now complete. When ready you can hit the Deploy Site to send site " + parameter_dict['site_name'] + " to the controller \n")
                self.thread_complete()
            except:
                print("Build failed. Please check your CSV headers")
                self.thread_complete()    

######################### Open File ###################################

        def getFiles(self):
            filename = QFileDialog.getOpenFileName(self, 'Single File', os.getcwd(), '*.csv')            
            self.csv_file = filename[0]            
            self.site_db.clear()
            if self.csv_file == "":
                print("Cancelled file selection")
            else:
                with open(self.csv_file, 'r') as read_obj:
                    csv_dict_reader = DictReader(read_obj)
                    for row in csv_dict_reader:
                        name = row['site_name']
                        self.site_db.addItem(name)
                print("Imported files from: " + filename[0])
            
######################### Open File ###################################
            
        def getJinja(self):
            filename = QFileDialog.getOpenFileName(self, 'Single File', os.getcwd(), '*.jinja *.yml')            
            head_tail = os.path.split(filename[0])
            self.jinja_file = head_tail[1]
            self.jinja_path = head_tail[0]
            print(os.path.basename(self.jinja_file))
            if self.jinja_file == "":
                print("Cancelled file selection")
            else:
                print("Jinja template selected: " + filename[0]) 

######################### View File ###################################
        
        def openSite(self):
            try:
                filename = os.path.join("./Configs/", self.sitefile.currentText())
                subprocess.run(['open', filename], check=True)
            except:
                print("Failed top open file " + self.sitefile.currentText())
                      

######################### Build Dic ###################################
        
        def pullCSV(self):
            print("Building site: " + self.site_db.currentText())
            self.text_status.setText("Building a site")
            self.text_status.setStyleSheet("background-color: rgb(251, 18, 0);")
            self.site_main_file = self.site_db.currentText()
            site_csv_dict = {}
            if self.jinja_file == None:
                print("Please choose Jinja file")
                self.text_status.setStyleSheet("background-color: rgb(94, 255, 0);")
                self.text_status.setText("Currently idle")
            else:
                if self.site_db.currentText() == "":
                    print("Please choose a site")
                    self.text_status.setStyleSheet("background-color: rgb(94, 255, 0);")
                    self.text_status.setText("Currently idle")
                else:
                    with open(self.csv_file, 'r') as read_obj:
                        csv_dict_reader = DictReader(read_obj)
                        for row in csv_dict_reader:
                            name = row['site_name']
                            if name == self.site_db.currentText():
                                for column, value in row.items():
                                    site_csv_dict.setdefault(column, []).append(value)
                    self.buildSite(site_csv_dict)

######################### Delete Site #################################

        def deleteSite(self):        
                self.text_output.append("Deleting site: " + self.site.currentText())
                self.text_status.setText("In process of deleting")
                self.text_status.setStyleSheet("background-color: rgb(251, 18, 0);")
                text, ok = QInputDialog.getText(self, 'Delete Confirmation', 'Please type confirm if you want to delete site: ' + self.site.currentText())
                if text == "confirm":
                      self.text_output.append("Making a backup copy of : " + self.site.currentText())
                      name = self.site.currentText() 
                      destroy_site = "destroy"
                      filename_temp = os.path.join("./Backup/", self.site.currentText())
                      filename = str(filename_temp)
                      filename += ".yaml"
                      workerdelete = WorkerPull(name, destroy_site, filename)
                      workerdelete.signals.result.connect(self.print_output)
                      workerdelete.signals.finished.connect(self.thread_complete)
                      self.threadpool.start(workerdelete)
                else:
                    self.text_output.append("Cancelled")
                    self.thread_complete()

######################### Verify Site #################################
        
        def verify(self):
                if self.site_push_check == True:
                    self.text_status.setText("In process of verifying site")
                    self.text_status.setStyleSheet("background-color: rgb(251, 18, 0);")
                    name = self.site_main_verify                
                    print(name)
                    workerverify = WorkerVerify(name)
                    workerverify.signals.result.connect(self.print_output)
                    workerverify.signals.finished.connect(self.thread_complete)
                    self.threadpool.start(workerverify)
                else:
                    self.text_output.append("Please deploy this site first")

######################### Clear Log #################################
                              
        def clearLog(self):              
                self.text_output.setText("")
                self.thread_complete()                 

######################### Push Site #################################
        
        def pushSite(self):
                if self.sitefile.currentText() == "":
                    self.text_output.append("Please first build the site")
                else:
                    self.text_output.append("Pushing out site: " + self.sitefile.currentText())
                    
                    self.text_status.setText("In process of pushing site")
                    self.text_status.setStyleSheet("background-color: rgb(251, 18, 0);")
                    msg = QMessageBox()
                    msg.setWindowTitle("Deploy Site")
                    msg.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
                    msg.setText("Confirm you want to push site: " + self.sitefile.currentText())
                    returnValue = msg.exec_()
                    if returnValue == QMessageBox.Yes:
                        self.site_main_verify, ext = self.sitefile.currentText().split(".")
                        destroy_site = None
                        filename_temp = os.path.join("./Configs/", self.sitefile.currentText())
                        filename = str(filename_temp)                    
                        workerdo = WorkerDo(filename, destroy_site)
                        workerdo.signals.result.connect(self.print_output)
                        workerdo.signals.finished.connect(self.thread_complete)
                        self.threadpool.start(workerdo)
                        self.site_push_check = True
                    else:
                        self.text_output.append("Cancelled")
                        self.thread_complete()

######################### Find LAT/LONG #################################
                            
        def getLATLONG(self, address_concat):              
                self.text_output.append("Getting site coordiantes")
                map_url = f"https://www.mapquestapi.com/geocoding/v1/address?key=ejebwfz7Ewm4eAkR9sxGMiCUccasfE6W&location={address_concat}"
                location = requests.get(url=map_url, verify=False).json()
                latLng = location['results'][0]['locations'][0]['latLng']
                latitude = latLng['lat']
                longitude = latLng['lng']
                return (latitude, longitude)

######################### Create Site #################################
        
        def createSITE(self, parameter_dict):              
                self.text_output.append("Create Jinja2 environment...")
                env = jinja2.Environment(loader=jinja2.FileSystemLoader(searchpath=self.jinja_path))
                template = env.get_template(self.jinja_file)
                result = template.render(parameter_dict)
                f = open(os.path.join(output_directory, parameter_dict['site_name'] + ".yaml"), "w")
                f.write(result)
                f.close()
                self.text_output.append("Configuration created..." + (parameter_dict['site_name'] + ".yaml"))
                self.thread_complete() 
                
        def progress_fn(self, n):
            print("%d%% done" % n)

        def execute_this_fn(self, progress_callback):
            print("")

        def print_output(self, s):
            self.text_output.append(s)

        def thread_complete(self):
            self.text_status.setStyleSheet("background-color: rgb(94, 255, 0);")
            self.text_status.setText("Currently idle")
            self.sitefile.clear()
            mac = "DS_Store"
            for dirname, dirnames, filenames in os.walk('./Configs'):
                for filename in filenames:
                    if mac not in filename:
                        self.sitefile.addItem(filename)
            name = self.site_db.currentText() + ".yaml"
            select_site_id = self.sitefile.findText(name)
            self.sitefile.setCurrentIndex(select_site_id)
            
            sites = get()
            self.site.clear()
            if sites == None:
                print("Get list of sites failed. Check authentication\n")
            else:
                for site_name in sites:
                    self.site.addItem(site_name)
            name = self.site_main_verify
            select_site_id = self.site.findText(name)
            self.site.setCurrentIndex(select_site_id)
                        

if __name__ == "__main__":
        app = QApplication(sys.argv)
        win = lineEditDemo()
        win.show()
        sys.exit(app.exec_())