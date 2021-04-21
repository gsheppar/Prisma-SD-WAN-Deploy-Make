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
from cloudgenix_config.GetSite import get
import time
import subprocess
import logging
import ipcalc
from csv import DictReader

######################### Thread Commands ###################################

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
    def __init__(self, name):
        super(WorkerPull, self).__init__()
        
        self.name = name
        self.signals = WorkerSignals()
    
    @pyqtSlot()
    def run(self):
        '''
        Your code goes in this function
        '''
        result = "Starting pull please wait....\n"
        self.signals.result.emit(result)
        pull(self.name)
        self.signals.finished.emit()

######################### Main PyQt Window ###################################

class lineEditDemo(QWidget):
        def __init__(self,parent=None):
                super().__init__(parent)    
                self.pull_site_name = ""
                self.csv = {}
                self.jinja_file = ""
                
                sites = get()
                self.site = QComboBox()
                
                btn1 = QPushButton("Make Variable")
                btn1.clicked.connect(self.select_text)
                btn2 = QPushButton("Undo Variable")
                btn2.clicked.connect(self.deselect_text)
                btn3 = QPushButton("Select File")
                btn3.clicked.connect(self.getYML)
                btn4 = QPushButton("Pull")
                btn4.clicked.connect(self.pull)
                btn5 = QPushButton("Save Jinja and CSV")
                btn5.clicked.connect(self.save_text)
                
                layout_console = QFormLayout()
                labelname = QLabel('or select local yaml base:')
                yaml_qhbox = QHBoxLayout()
                yaml_qhbox.addWidget(labelname)
                yaml_qhbox.addWidget(btn3)
                pull_qhbox = QHBoxLayout()
                labelname = QLabel('Select site to pull yaml base:')
                pull_qhbox.addWidget(labelname)
                pull_qhbox.addWidget(self.site)
                pull_qhbox.addWidget(btn4)
                layout_console = QFormLayout()
                layout_console.addRow(pull_qhbox)
                layout_console.addRow(yaml_qhbox)
                self.text_console = QTextEdit() 
                self.text_console.setReadOnly(True)
                self.text_console.setMinimumHeight(500)
                self.text_console.setMinimumWidth(400)
                labelname = QLabel('Message Output')
                layout_console.addRow(labelname)
                layout_console.addRow(self.text_console)
                
                
                layout_display = QFormLayout()
                self.text_output = QPlainTextEdit()
                self.text_output.setMinimumHeight(600)
                self.text_output.setMinimumWidth(450)
                select_qhbox = QHBoxLayout()
                select_qhbox.addWidget(btn1)
                select_qhbox.addWidget(btn2)
                layout_display.addRow(self.text_output)
                layout_display.addRow(select_qhbox)
                layout_display.addRow(btn5)
                
                self.input_left = QGroupBox("Base Selection")
                self.input_left.setLayout(layout_console)
                self.input_left.setStyleSheet('QGroupBox:title {'
                                 'subcontrol-origin: margin;'
                                 'padding-left: 10px;'
                                 'font: bold;'
                                 'padding-right: 10px; }')
                
                self.input_right = QGroupBox("Jinja Base Build")
                self.input_right.setLayout(layout_display)
                self.input_right.setStyleSheet('QGroupBox:title {'
                                 'subcontrol-origin: margin;'
                                 'padding-left: 10px;'
                                 'font: bold;'
                                 'padding-right: 10px; }')
                                 
                self.threadpool = QThreadPool()
                mainLayout = QGridLayout()
                mainLayout.addWidget(self.input_left, 0, 0)
                mainLayout.addWidget(self.input_right, 0, 1)
                self.setLayout(mainLayout)
                self.setWindowTitle("Prisma SD-WAN Site Build")
                
                fmt = QTextCharFormat()
                fmt.setFontWeight(QFont.Bold)
                self.text_console.setCurrentCharFormat(fmt)
                
                
                self.text_console.append("The purpose of this program is to help you build your Master Jinja file. This file can be used with the Prisma SD-WAN DevOps model to fully automate provisioning and deployment.\n\nFirst either pull your base file from a site you want to use or pick a local file. I will automaticaly create variables for your site name and address but for any other options just highlight the text with your mouse, click create variable and name it. When complete hit save and then you can add site details to the CSV file and then use it with the Jinja as part of the site deployment tool. \n")
                
                fmt = QTextCharFormat()
                self.text_console.setCurrentCharFormat(fmt)
                
                if not os.path.exists('Backup'):
                    os.makedirs('Backup')
                
                if sites == None:
                    self.text_console.append("Pull from sites failed but you can choose a local yaml base file \n")
                else:
                    for site_name in sites:
                        self.site.addItem(site_name)

######################### Open Base Yaml ###################################
      
        def getYML(self):
            filename = QFileDialog.getOpenFileName(self, 'Single File', os.getcwd() , '*.yml *.yaml')            
            head_tail = os.path.split(filename[0])
            jinja_file = head_tail[1]
            self.jinja_file = filename[0]
            if jinja_file == "":
                self.text_console.append("Cancelled file selection")
            else:
                self.text_console.append("YAML base selected: " + filename[0] + "\n")
                file_temp = open(filename[0], "r")
                text = file_temp.read()
                self.text_output.insertPlainText(text)
                self.text_output.setReadOnly(True)
                self.text_output.moveCursor(QTextCursor.Start)
                self.find_replace()

######################### Pull Base Yaml ###################################
                
        def pull(self):           
            self.pull_site_name = self.site.currentText()
            workerdo = WorkerPull(self.pull_site_name)
            workerdo.signals.result.connect(self.print_output)
            workerdo.signals.finished.connect(self.thread_complete)
            self.threadpool.start(workerdo)
                
######################### Make Jinja Variable ##############################
        
        def select_text(self):
            cursor = self.text_output.textCursor()
            if cursor.hasSelection():
                select = cursor.selectedText()
                variable, ok = QInputDialog.getText(self, 'Variable Name', 'Please provide variable name (no spaces)')
                variable.replace(" ", "")
                if variable in self.csv.keys(): 
                    msg = QMessageBox()
                    msg.setWindowTitle("Site Variable")
                    msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                    msg.setText("This variable already exsists. Do you want to reference it again?")
                    returnValue = msg.exec_()
                    if returnValue == QMessageBox.Yes:
                        self.text_console.append("Added variable {{ " + variable + " }} for " + select + "\n")
                        cursor.removeSelectedText()
                        variable = "{{ " + variable + " }}"
                        fmt = QTextCharFormat()
                        fmt.setBackground(Qt.green)
                        cursor.setCharFormat(fmt)
                        cursor.insertText(variable)
                    else:
                        fmt = QTextCharFormat()
                        fmt.setForeground(Qt.red)
                        self.text_console.setCurrentCharFormat(fmt)
                        self.text_console.append("Sorry that variable already exsists\n")
                        fmt = QTextCharFormat()
                        self.text_console.setCurrentCharFormat(fmt)
                elif "-" in variable:
                    fmt = QTextCharFormat()
                    fmt.setForeground(Qt.red)
                    self.text_console.setCurrentCharFormat(fmt)
                    self.text_console.append("Sorry please don't use a dash - in your variables. Another option is underscores _\n")
                    fmt = QTextCharFormat()
                    self.text_console.setCurrentCharFormat(fmt)
                elif not variable:
                    print(variable)
                    fmt = QTextCharFormat()
                    fmt.setForeground(Qt.red)
                    self.text_console.setCurrentCharFormat(fmt)
                    self.text_console.append("Sorry please enter some text for the variable\n")
                    fmt = QTextCharFormat()
                    self.text_console.setCurrentCharFormat(fmt)
                else:
                    self.csv.setdefault(variable, []).append(select)
                    self.text_console.append("Added variable {{ " + variable + " }} for " + select + " and put it in CSV\n")
                    cursor.removeSelectedText()
                    variable = "{{ " + variable + " }}"
                    fmt = QTextCharFormat()
                    fmt.setBackground(Qt.green)
                    cursor.setCharFormat(fmt)
                    cursor.insertText(variable)
                    
                    msg = QMessageBox()
                    msg.setWindowTitle("Site Variable")
                    msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                    msg.setText("Do you want to find all instance of the text you selected and insert the variable?")
                    returnValue = msg.exec_()
                    if returnValue == QMessageBox.Yes:
                        self.text_output.moveCursor(QTextCursor.Start)
                        self.text_output.verticalScrollBar().setValue(0)      
                        find_text = select
                        check = self.text_output.find(find_text)
                        while check == True:
                            section = self.text_output.textCursor()
                            text = section.selectedText()
                            fmt.setBackground(Qt.green)
                            section.setCharFormat(fmt)
                            section.insertText(variable)
                            check = self.text_output.find(find_text)
                            section = self.text_output.textCursor()
                            fmt.setBackground(Qt.white)
                            section.setCharFormat(fmt)
                        self.text_output.moveCursor(QTextCursor.Start)
                        self.text_output.verticalScrollBar().setValue(0)

######################### Undo Jinja Variable ##############################
        
        def deselect_text(self):
            cursor = self.text_output.textCursor()
            if cursor.hasSelection():
                select = cursor.selectedText()
                text = select.split()
                if len(text) == 3:
                    if text[0] == "{{":
                        if text[2] == "}}":
                            if text[1] in self.csv:
                                orginal = str(self.csv[text[1]])
                                del self.csv[text[1]]
                            self.text_console.append("Removed variable {{ " + text[1] + " }}\n")
                            cursor.removeSelectedText()
                            orginal = orginal.replace("['", "")
                            orginal = orginal.replace("']", "")
                            cursor.insertText(orginal)

######################### Save Jinja and CSV ##############################
        
        def save_text(self):
            filename = QFileDialog.getSaveFileName(self, 'CSV File', os.getcwd() + "/MasterDatabase.csv")   
            csv_name = filename[0]
            if csv_name != '':
                csv_name = filename[0]
                csv_columns = []
                csv_value = []
                for key, value in self.csv.items() :
                    csv_columns.append(key)
                    csv_value.append(value[0])
                with open(csv_name,'w') as f:
                   writer = csv.writer(f, delimiter=',')
                   writer.writerow(csv_columns)
                   writer.writerow(csv_value)
                   self.text_console.append("CSV saved as: " + csv_name + " \n")
                   
            jinja_string = self.text_output.toPlainText()
            filename = QFileDialog.getSaveFileName(self, 'Jinja File', os.getcwd() + "/MasterBuild.jinja")
            jinja_name = filename[0]
            if jinja_name != '':
                with open(jinja_name,'w') as f:
                    f.write(jinja_string)
                    self.text_console.append("Jinja saved as: " + jinja_name + " \n")
                    fmt = QTextCharFormat()
                    fmt.setFontWeight(QFont.Bold)
                    self.text_console.setCurrentCharFormat(fmt)
                    self.text_console.append("You are all done. Now go add additional sites to your MasterDatabase and then use these two files with our deployment tool to push sites in seconds. Quick reminder make sure to add any auth strings such as SNMP to your MasterJinja file since they are not pulled by default. \n")
                    fmt = QTextCharFormat()
                    self.text_console.setCurrentCharFormat(fmt)
                    
#################### Base Changes for Address and Site Name ########################
        
        def find_replace(self):
            
            description = ""
            site_name = ""
            city = ""
            street = ""
            country = ""
            state = ""
            post_code = ""
            line_start = 0
            line_org = 0
            serial_number_1 = ""
            serial_number_2 = ""
            
            temp_file = open(self.jinja_file, "r")
            intial_file = temp_file .readlines()
            line_num = 0
            for line in intial_file:
                line_num += 1
                if "sites v4.5:" in line:
                    line_start = line_num
                    line_org = line_num
                            
            get = intial_file[line_start]
            head_tail = get.split(": ")
            name = head_tail[0].strip()
            site_name = name.replace(":","")
            self.csv.setdefault("site_name", []).append(site_name)        
            
            section=self.text_output.textCursor()
            section.movePosition(QTextCursor.Down, QTextCursor.MoveAnchor, line_org)
            section.movePosition(QTextCursor.StartOfBlock)
            section.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
            text = section.selectedText()
            section.insertText("  ")
            fmt = QTextCharFormat()
            fmt.setBackground(Qt.green)
            section.setCharFormat(fmt)
            section.insertText("{{" + " site_name }}")
            fmt.setBackground(Qt.white)
            section.setCharFormat(fmt)
            section.insertText(":")
            section.movePosition(QTextCursor.Start)
            self.text_output.verticalScrollBar().setValue(0)            
            
            self.text_output.find("latitude:")
            section=self.text_output.textCursor()
            section.movePosition(QTextCursor.StartOfBlock)
            section.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
            text = section.selectedText()
            section.insertText("      latitude: ")
            fmt.setBackground(Qt.green)
            section.setCharFormat(fmt)
            section.insertText("{{" + " site_lat }}")
            fmt.setBackground(Qt.white)
            section.setCharFormat(fmt)
            section.movePosition(QTextCursor.Start)
            self.text_output.verticalScrollBar().setValue(0)
            
            self.text_output.find("longitude:")
            section=self.text_output.textCursor()
            section.movePosition(QTextCursor.StartOfBlock)
            section.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
            text = section.selectedText()
            section.insertText("      longitude: ")
            fmt.setBackground(Qt.green)
            section.setCharFormat(fmt)
            section.insertText("{{" + " site_long }}")
            fmt.setBackground(Qt.white)
            section.setCharFormat(fmt)
            self.text_output.moveCursor(QTextCursor.Start)
            self.text_output.verticalScrollBar().setValue(0)
            
            self.text_output.find("serial_number:")
            section=self.text_output.textCursor()
            section.movePosition(QTextCursor.StartOfBlock)
            section.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
            text = section.selectedText()
            head_tail = text.split(": ")
            serial_number_1 = head_tail[1].strip()
            section.insertText("        serial_number: ")
            fmt.setBackground(Qt.green)
            section.setCharFormat(fmt)
            section.insertText("{{" + " ion_serial_number_1 }}")
            fmt.setBackground(Qt.white)
            section.setCharFormat(fmt)
            check = self.text_output.find("serial_number:")
            if check == True:
                section=self.text_output.textCursor()
                section.movePosition(QTextCursor.StartOfBlock)
                section.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
                text = section.selectedText()
                head_tail = text.split(": ")
                serial_number_2 = head_tail[1].strip()
                section.insertText("        serial_number: ")
                fmt.setBackground(Qt.green)
                section.setCharFormat(fmt)
                section.insertText("{{" + " ion_serial_number_2 }}")
                fmt.setBackground(Qt.white)
                section.setCharFormat(fmt)
            self.text_output.moveCursor(QTextCursor.Start)
            self.text_output.verticalScrollBar().setValue(0)
            
            self.text_output.find("city:")
            section=self.text_output.textCursor()
            section.movePosition(QTextCursor.StartOfBlock)
            section.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
            text = section.selectedText()
            head_tail = text.split(": ")
            check = len(head_tail)
            if check == 2:
                city = head_tail[1].strip()
                section.insertText("      city: ")
                fmt.setBackground(Qt.green)
                section.setCharFormat(fmt)
                section.insertText("{{" + " city }}")
                fmt.setBackground(Qt.white)
                section.setCharFormat(fmt)
            self.text_output.moveCursor(QTextCursor.Start)
            self.text_output.verticalScrollBar().setValue(0)
            
            self.text_output.find("country:")
            section=self.text_output.textCursor()
            section.movePosition(QTextCursor.StartOfBlock)
            section.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
            text = section.selectedText()
            head_tail = text.split(": ")
            check = len(head_tail)
            if check == 2:
                country = head_tail[1].strip()
                section.insertText("      country: ")
                fmt.setBackground(Qt.green)
                section.setCharFormat(fmt)
                section.insertText("{{" + " country }}")
                fmt.setBackground(Qt.white)
                section.setCharFormat(fmt)
            self.text_output.moveCursor(QTextCursor.Start)
            self.text_output.verticalScrollBar().setValue(0)
            
            self.text_output.find("post_code:")
            section=self.text_output.textCursor()
            section.movePosition(QTextCursor.StartOfBlock)
            section.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
            text = section.selectedText()
            head_tail = text.split(": ")
            check = len(head_tail)
            if check == 2:
                post_code = head_tail[1].strip()
                section.insertText("      post_code: ")
                fmt.setBackground(Qt.green)
                section.setCharFormat(fmt)
                section.insertText("{{" + " post_code }}")
                fmt.setBackground(Qt.white)
                section.setCharFormat(fmt)
            self.text_output.moveCursor(QTextCursor.Start)
            self.text_output.verticalScrollBar().setValue(0)
            
            self.text_output.find("state:")
            section=self.text_output.textCursor()
            section.movePosition(QTextCursor.StartOfBlock)
            section.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
            text = section.selectedText()
            head_tail = text.split(": ")
            check = len(head_tail)
            if check == 2:
                street = head_tail[1].strip()
                section.insertText("      state: ")
                fmt.setBackground(Qt.green)
                section.setCharFormat(fmt)
                section.insertText("{{" + " state }}")
                fmt.setBackground(Qt.white)
                section.setCharFormat(fmt)
            self.text_output.moveCursor(QTextCursor.Start)
            self.text_output.verticalScrollBar().setValue(0)
            
            self.text_output.find("street:")
            section=self.text_output.textCursor()
            section.movePosition(QTextCursor.StartOfBlock)
            section.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
            text = section.selectedText()
            head_tail = text.split(": ")
            check = len(head_tail)
            if check == 2:
                street = head_tail[1].strip()
                section.insertText("      street: ")
                fmt.setBackground(Qt.green)
                section.setCharFormat(fmt)
                section.insertText("{{" + " street }}")
                fmt.setBackground(Qt.white)
                section.setCharFormat(fmt)
            self.text_output.moveCursor(QTextCursor.Start)
            self.text_output.verticalScrollBar().setValue(0)
            
            self.text_output.find("description:")
            section=self.text_output.textCursor()
            section.movePosition(QTextCursor.StartOfBlock)
            section.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
            text = section.selectedText()
            head_tail = text.split(": ")
            check = len(head_tail)
            if check == 2:
                description = head_tail[1].strip()
                section.insertText("      description: ")
                fmt.setBackground(Qt.green)
                section.setCharFormat(fmt)
                section.insertText("{{" + " description }}")
                fmt.setBackground(Qt.white)
                section.setCharFormat(fmt)
            self.text_output.moveCursor(QTextCursor.Start)
            self.text_output.verticalScrollBar().setValue(0)
            
            
            self.csv.setdefault("ion_serial_number_1", []).append(serial_number_1)
            if serial_number_2 != "":
                self.csv.setdefault("ion_serial_number_2", []).append(serial_number_2)
            if description != "":
                self.csv.setdefault("description", []).append(description)
            if street != "":
                self.csv.setdefault("street", []).append(street)
            if city != "":
                self.csv.setdefault("city", []).append(city)
            if post_code != "":
                self.csv.setdefault("post_code", []).append(post_code)
            if state != "":
                self.csv.setdefault("state", []).append(state)
            if country != "":
                self.csv.setdefault("country", []).append(country)
            
            self.text_output.moveCursor(QTextCursor.Start)
            self.text_output.verticalScrollBar().setValue(0)      
            find_text = site_name
            check = self.text_output.find(find_text)
            while check == True:
                section = self.text_output.textCursor()
                text = section.selectedText()
                text = "{{ " + "site_name }}"
                fmt.setBackground(Qt.green)
                section.setCharFormat(fmt)
                section.insertText(text)
                check = self.text_output.find(find_text)
                section = self.text_output.textCursor()
            fmt.setBackground(Qt.white)
            section.setCharFormat(fmt)
            section.movePosition(QTextCursor.Start)
            self.text_output.verticalScrollBar().setValue(0)

        
######################### Undo Jinja Variable ##############################

        
        def progress_fn(self, n):
            print("%d%% done" % n)

        def execute_this_fn(self, progress_callback):
            print("")

        def print_output(self, s):
            self.text_console.append(s)

        def thread_complete(self):
            filename = os.getcwd() + "/Backup/" + self.pull_site_name + ".yaml"
            self.jinja_file = filename
            self.text_console.append("YAML base pulled from " + self.pull_site_name + "\n")
            file_temp = open(filename, "r")
            text = file_temp.read()
            self.text_output.insertPlainText(text)
            self.text_output.setReadOnly(True)
            self.text_output.moveCursor(QTextCursor.Start)
            self.find_replace()

if __name__ == "__main__":
        app = QApplication(sys.argv)
        win = lineEditDemo()
        win.show()
        sys.exit(app.exec_())