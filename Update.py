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


######################### Main PyQt Window ###################################

class lineEditDemo(QWidget):
        def __init__(self,parent=None):
                super().__init__(parent)    
                self.description = ""
                self.name = ""
                self.city = ""
                self.street = ""
                self.country = ""
                self.state = ""
                self.post_code = ""
                self.line_start = 0
                self.line_org = 0
                self.pull_site_name = ""
                self.csv = {}
                self.csv_file = ""
                self.jinja_file = ""
                
                btn1 = QPushButton("Make Variable")
                btn1.clicked.connect(self.select_text)
                btn2 = QPushButton("Undo Variable")
                btn2.clicked.connect(self.deselect_text)
                btn3 = QPushButton("Select File")
                btn3.clicked.connect(self.getJINJA)
                btn4 = QPushButton("Select FIle")
                btn4.clicked.connect(self.getCSV)
                btn5 = QPushButton("Save Jinja and CSV")
                btn5.clicked.connect(self.save_text)
                
                layout_console = QFormLayout()
                labelname = QLabel('Select CSV file:')
                pull_qhbox = QHBoxLayout()
                pull_qhbox.addWidget(labelname)
                pull_qhbox.addWidget(btn4)
                
                labelname = QLabel('Select Jinja file:')
                yaml_qhbox = QHBoxLayout()
                yaml_qhbox.addWidget(labelname)
                yaml_qhbox.addWidget(btn3)
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
                self.setWindowTitle("Prisma SD-WAN Site Build Update")
                
                fmt = QTextCharFormat()
                fmt.setFontWeight(QFont.Bold)
                self.text_console.setCurrentCharFormat(fmt)
                
                
                self.text_console.append("The purpose of this program is to help update your Master Jinja file. This file can be used with the Prisma SD-WAN DevOps model to fully automate provisioning and deployment.\n\nFirst select your CSV file and then your Master Jinja file. Then you can add or remove any variables. When complete hit save and then you can add site details to the CSV file and use it with the Jinja as part of the site deployment tool. \n")
                
                fmt = QTextCharFormat()
                self.text_console.setCurrentCharFormat(fmt)
                
                if not os.path.exists('Backup'):
                    os.makedirs('Backup')

######################### Open Base Yaml ###################################
      
        def getJINJA(self):
            filename = QFileDialog.getOpenFileName(self, 'Single File', os.getcwd() , '*.jinja')            
            head_tail = os.path.split(filename[0])
            jinja_file = head_tail[1]
            self.jinja_file = filename[0]
            if jinja_file == "":
                self.text_console.append("Cancelled file selection")
            else:
                self.text_console.append("Jinja base selected: " + filename[0] + "\n")
                file_temp = open(filename[0], "r")
                text = file_temp.read()
                self.text_output.insertPlainText(text)
                self.text_output.setReadOnly(True)
                self.text_output.moveCursor(QTextCursor.Start)
                self.find_replace()

######################### Open Base Yaml ###################################
      
        def getCSV(self):
            filename = QFileDialog.getOpenFileName(self, 'Single File', os.getcwd() , '*.csv')            
            head_tail = os.path.split(filename[0])
            jinja_file = head_tail[1]
            self.csv_file = filename[0]
            if jinja_file == "":
                self.text_console.append("Cancelled file selection")
            else:
                self.text_console.append("CSV selected: " + filename[0] + "\n")
                csv_temp_file = open(self.csv_file, "r")
                dict_reader = csv.DictReader(csv_temp_file)
                ordered_dict_from_csv = list(dict_reader)[0]
                self.csv = dict(ordered_dict_from_csv)                
                
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
                            
                            self.text_output.moveCursor(QTextCursor.Start)
                            self.text_output.verticalScrollBar().setValue(0)      
                            check = self.text_output.find(select)
                            fmt = QTextCharFormat()      
                            while check == True:
                                section = self.text_output.textCursor()
                                text = section.selectedText()
                                fmt.setBackground(Qt.white)
                                section.setCharFormat(fmt)
                                section.insertText(orginal)
                                check = self.text_output.find(select)
                                section = self.text_output.textCursor()
                            section.movePosition(QTextCursor.Start)
                            self.text_output.verticalScrollBar().setValue(0)

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
                    csv_value.append(value)
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
                        
            fmt = QTextCharFormat()      
            for key in self.csv:
                self.text_output.moveCursor(QTextCursor.Start)
                self.text_output.verticalScrollBar().setValue(0)      
                find_text = "{{ " + key + " }}"
                check = self.text_output.find(find_text)
                while check == True:
                    section = self.text_output.textCursor()
                    text = section.selectedText()
                    fmt.setBackground(Qt.green)
                    section.setCharFormat(fmt)
                    section.insertText(text)
                    check = self.text_output.find(find_text)
                    section = self.text_output.textCursor()
                fmt.setBackground(Qt.white)
                section.setCharFormat(fmt)
                section.movePosition(QTextCursor.Start)
                self.text_output.verticalScrollBar().setValue(0)      
            
        
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