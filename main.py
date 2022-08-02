from ast import Lambda
import sys 
from PyQt5.QtWidgets import QMainWindow,QApplication
from PyQt5.QtGui import QColor
from PyQt5.QtSerialPort import QSerialPort, QSerialPortInfo
from OUTPUTS_VIEWER import Ui_MainWindow
import PyQt5.QtCore as QtCore
import pyqtgraph as pg
import numpy as np
import math
import frames
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QMessageBox

import resources_rc

class MiApp(QMainWindow):
	def __init__(self):
		super().__init__()
		self.ui = Ui_MainWindow()
		self.ui.setupUi(self)

		#Frames
		self.F = frames.Frame()

		#Timer
		self.timer=QTimer()

		#Serial
		self.port = QSerialPort() 
		self.baudratesDIC = {
		'1200':1200,
		'2400':2400,
		'4800':4800,
		'9600':9600,
		'19200':19200,
		'38400':38400,
		'57600':57600,
		'115200':115200
		}

		self.ui.comboBox_baudrate.addItems(self.baudratesDIC.keys())
		self.ui.comboBox_baudrate.setCurrentText('9600')
		
		self.ui.pushButton_disconnect.setEnabled(False)
		self.ui.pushButton_connect.setEnabled(True)
		self.controlsEnabled(False)

		self.update_ports()

		self.ui.label_PWM1_value.setText("Value: 000%")
		self.ui.label_PWM2_value.setText("Value: 000%")
		self.ui.label_status.setText("Disconnected")

		self.graphConfig()
		self.defaultPlot()

		self.x = list()
		self.AccX = list()
		self.AccY = list()
		self.AccZ = list()
		self.n = 0.0
		self.colorLineAccX = '#232c3c'
		self.colorLineAccY = '#232c3c'
		self.colorLineAccZ = '#232c3c'

		#Events
		self.ui.horizontalSlider_PWM1.valueChanged.connect(self.PWM1_valueChanged)
		self.ui.horizontalSlider_PWM2.valueChanged.connect(self.PWM2_valueChanged)
		self.ui.pushButton_connect.clicked.connect(self.connect_serial)
		self.ui.pushButton_disconnect.clicked.connect(self.disconnect_serial)
		self.ui.pushButton_refresh.clicked.connect(self.update_ports)
		self.ui.pushButton_clean.clicked.connect(self.graphClear)
		self.ui.pushButton_start.clicked.connect(self.start)
		self.ui.pushButton_stop.clicked.connect(self.stop)
		self.ui.radioButton_ON1.toggled.connect(self.controlOutput_1)
		self.ui.radioButton_ON2.toggled.connect(self.controlOutput_2)

		self.ui.checkBox_AccX.toggled.connect(self.checkBoxAccX_event)
		self.ui.checkBox_AccY.toggled.connect(self.checkBoxAccY_event)
		self.ui.checkBox_AccZ.toggled.connect(self.checkBoxAccZ_event)

		self.port.readyRead.connect(self.data_arrive)
		self.timer.timeout.connect(self.timeOut)
	
	def checkBoxAccX_event(self):
		if self.ui.checkBox_AccX.isChecked():
			self.colorLineAccX = '#169ECE'
		else:
			self.colorLineAccX = '#232c3c'

	def checkBoxAccY_event(self):
		if self.ui.checkBox_AccY.isChecked():
			self.colorLineAccY = '#1a7dbe'
		else:
			self.colorLineAccY = '#232c3c'

	def checkBoxAccZ_event(self):
		if self.ui.checkBox_AccZ.isChecked():
			self.colorLineAccZ = '#396a71'
		else:
			self.colorLineAccZ = '#232c3c'
			
	def defaultPlot(self):
		x = np.linspace(0, 3 * np.pi, 100)
		y1 = np.sin(x + np.pi)
		y2 = np.sin(x + np.pi/2)
		y3 = np.sin(x)
		self.plt.addLegend()

		self.lineAccX = self.plt.plot(x, y1, pen = pg.mkPen('#169ECE', width=2), name= "Data Axis X")
		self.lineAccY = self.plt.plot(x, y2, pen = pg.mkPen('#1a7dbe', width=2), name= "Data Axis Y")
		self.lineAccZ = self.plt.plot(x, y3, pen = pg.mkPen('#396a71', width=2), name= "Data Axis Z")

	def graphConfig(self):
		styles = {'color':'#169ECE', 'font-size':'20px', 'font-family':'Nirmala UI'}

		pg.setConfigOption('background', '#171717')
		pg.setConfigOption('foreground', '#169ECE')
		self.plt = pg.PlotWidget(title='')
		self.ui.graph_Layout.addWidget(self.plt)
		self.plt.showGrid(x=True,y=True)
		self.plt.setLabel('left', 'Acc Value [dec. G]', **styles)
		self.plt.setLabel('bottom', 'Sample', **styles)

	def start(self):
		if self.port.isOpen():
				self.timer.start(int(self.ui.spinBox_period.value()))
				self.lineAccX.clear()
				self.lineAccY.clear()
				self.lineAccZ.clear()
		else:
			print('>> ' + 'DEVICE NOT OPEN' + ' <<')
		
	def stop(self):
		self.timer.stop()
		#reply = QMessageBox.warning(self, "Mensaje", "Seguro quiere salir", QMessageBox.Ok)	

	def timeOut(self):
		self.send_data(str(self.F.FRAME_ACC_ALL_AXES))

	def graphClear(self):
		self.x.clear()
		self.AccX.clear()
		self.AccY.clear()
		self.AccZ.clear()
		self.n = 0
		self.lineAccX.clear()
		self.lineAccY.clear()
		self.lineAccZ.clear()

	def controlsEnabled(self, value):
		self.ui.radioButton_ON1.setEnabled(value)
		self.ui.radioButton_ON2.setEnabled(value)
		self.ui.radioButton_OFF1.setEnabled(value)
		self.ui.radioButton_OFF2.setEnabled(value)
		self.ui.horizontalSlider_PWM1.setEnabled(value)
		self.ui.horizontalSlider_PWM2.setEnabled(value)
		self.ui.pushButton_start.setEnabled(value)

	def controlsRestart(self):
		self.ui.radioButton_OFF1.setChecked(True)
		self.ui.radioButton_OFF2.setChecked(True)
		self.ui.horizontalSlider_PWM1.setValue(0)
		self.ui.horizontalSlider_PWM2.setValue(0)

	def data_arrive(self):
		if not self.port.canReadLine(): return
		rx = self.port.readLine()
		data = str(rx, 'utf-8').strip()
		self.excecuteFrame(data)
	
	def excecuteFrame(self, frame):
		data = frame.split(":")
		
		#if (":"+data[1]) == str(self.F.FRAME_ACC_AXIS_X):
			#self.graphAddNewValue(float(data[3])) if data[2] == 'P' else self.graphAddNewValue((-1)*float(data[3]))
		
		AccX = float(data[2]) if data[1] == 'P' else (-1)*float(data[2])
		AccY = float(data[4]) if data[3] == 'P' else (-1)*float(data[4])
		AccZ = float(data[6]) if data[5] == 'P' else (-1)*float(data[6])
		self.graphAddNewData(tuple([AccX, AccY, AccZ]))

	def graphAddNewData(self, Acc_values:tuple):
			self.AccX.append(Acc_values[0])
			self.AccY.append(Acc_values[1])
			self.AccZ.append(Acc_values[2])
			self.x.append(self.n)
			self.n += 1 

			self.lineAccX = self.plt.plot(self.x, self.AccX, pen = pg.mkPen(self.colorLineAccX, width=2))
			self.lineAccY = self.plt.plot(self.x, self.AccY, pen = pg.mkPen(self.colorLineAccY, width=2))
			self.lineAccZ = self.plt.plot(self.x, self.AccZ, pen = pg.mkPen(self.colorLineAccZ, width=2))


	def graphAddNewValue(self, value):
		self.y.append(value)
		self.x.append(self.n)
		self.n += 1 

		self.lineAccX.clear()
		self.lineAccX = self.plt.plot(self.x, self.y, pen = pg.mkPen(self.colorLineAccX, width=2))

	def controlOutput_1(self):
		self.send_data(str(self.F.FRAME_LED_GREEN_ON)) if self.ui.radioButton_ON1.isChecked() else self.send_data(str(self.F.FRAME_LED_GREEN_OFF))

	def controlOutput_2(self):
		self.send_data(str(self.F.FRAME_LED_RED_ON)) if self.ui.radioButton_ON2.isChecked() else self.send_data(str(self.F.FRAME_LED_RED_OFF))

	def PWM1_valueChanged(self):
		value = str(self.ui.horizontalSlider_PWM1.value()).rjust(3, '0')
		self.ui.label_PWM1_value.setText("Value: " + value +"%")
		self.send_data("Value PWM1: " + value +"%")

	def PWM2_valueChanged(self):
		value = str(self.ui.horizontalSlider_PWM2.value()).rjust(3, '0')
		self.ui.label_PWM2_value.setText("Value: " + value +"%")
		self.send_data("Value PWM2: " + value +"%")

	def connect_serial(self):		
		try:
			port = self.ui.comboBox_port_list.currentText()
			baud = self.ui.comboBox_baudrate.currentText()
			self.port.setBaudRate(int(baud))
			self.port.setPortName(port)
			if self.port.open(QtCore.QIODevice.ReadWrite):
				self.ui.pushButton_disconnect.setEnabled(True)
				self.ui.pushButton_connect.setEnabled(False)
				self.controlsEnabled(True)
				self.ui.label_status.setText("Connected to " + port)
		except:
			print('>> ' + 'ERROR OCURRED!' + ' <<')
		finally:
			pass
	
	def disconnect_serial(self):
		if self.port.isOpen():
			self.port.close()
			self.timer.stop()
			self.ui.label_status.setText("Disconnected")
			self.ui.pushButton_disconnect.setEnabled(False)
			self.ui.pushButton_connect.setEnabled(True)
			self.controlsEnabled(False)
			self.controlsRestart()

	def send_data(self, data):
		try:
			if self.port.isOpen():
				data += '\n'
				self.port.write(data.encode())
			else:
				print('>> ' + 'DEVICE NOT OPEN' + ' <<')
		except:
			print('>> ' + 'ERROR OCURRED!' + ' <<')
		finally:
			pass

	def update_ports(self):
		self.ui.comboBox_port_list.clear()
		self.ui.comboBox_port_list.addItems([ port.portName() for port in QSerialPortInfo().availablePorts() ])

	def closeEvent(self,e):
		if self.port.isOpen():
			self.port.close()
			self.timer.stop()

if __name__ == '__main__':
	app = QApplication(sys.argv)
	w = MiApp()
	w.show()
	sys.exit(app.exec_())