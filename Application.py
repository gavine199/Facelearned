import serial
import re
import serial.tools.list_ports
import cv2  # 图像处理的库OpenCv
import os
import PyQt5
# 添加PyQt5环境变量(解决运行平台问题)
dirname = os.path.dirname(PyQt5.__file__)
plugin_path = os.path.join(dirname,'Qt', 'plugins', 'platforms')
os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = plugin_path
from PyQt5.QtCore import QTimer,QThread,QMutex,QMutexLocker,pyqtSignal
from PyQt5 import QtCore,QtWidgets
from PyQt5.QtGui import QIcon, QPixmap,QImage,QPalette,QColor
from PyQt5.QtGui import QStandardItem, QStandardItemModel
from PyQt5.QtWidgets import QMessageBox,QFileDialog
from PyQt5.QtWidgets import QApplication,QAbstractItemView, QLabel,QLCDNumber,QInputDialog
from serial.threaded import ReaderThread,FramedPacket
from faceLearning import FaceLearning
from queue import Queue
from mainwindow import Ui_MainWindow
import dlib
from traceback import print_exc
import sys

##############################################################
#************************************************************
##############################################################
# $信号槽类$
class MySingnal(QThread):

    Data_Signal = QtCore.pyqtSignal(list)
    Tip_Singal = QtCore.pyqtSignal(str,str)
    Paint_Singal = QtCore.pyqtSignal(int)

    def __init__(self):
        super(MySingnal,self).__init__()

    def Data_Sender(self,Data):
        self.Data_Signal.emit(Data)

    def Tip_Sender(self,title,message):
        self.Tip_Singal.emit(title,message)

    def Paint_Sender(self,int_data):
        self.Paint_Singal.emit(int_data)
###############################################################
#************************************************************
##############################################################
# $串口通信协议$
class PrintLines(FramedPacket):


    def __init__(self):
        super(FramedPacket, self).__init__()
        self.packet = bytearray()

    def connection_lost(self, exc):
        """Forget transport"""
        self.transport = None
        self.in_packet = False
        del self.packet[:]
        super(PrintLines, self).connection_lost(exc)
        sys.stdout.write('port closed')

    def data_received(self, data):
        """Find data enclosed in START/STOP, call handle_packet"""
        handel_Data = []
        for byte in serial.iterbytes(data):
            if byte == self.START:
                self.in_packet = True
            elif byte == self.STOP:
                self.in_packet = False
                handel_Data.append(self.handle_packet(bytes(self.packet))) # make read-only copy
                del self.packet[:]
            elif self.in_packet:
                self.packet.extend(byte)
            else:
                self.handle_out_of_packet_data(byte)
        return handel_Data

    def handle_packet(self,packet):
        Buffer_type = ''
        translated_packet = packet.decode()
        for index in translated_packet:
            if index == 'C':
                Buffer_type = 'CMD'
            elif index == 'D':
                Buffer_type = 'DATA'

        if Buffer_type == 'CMD':
            # 预留命令行接口
            return translated_packet.split('a')[1].split('b')[0]
        elif Buffer_type == 'DATA':
            #print(float(translated_packet.split('a')[1].split('b')[0]))
            return float(translated_packet.split('a')[1].split('b')[0])
        else:
            return 'error'
        raise NotImplementedError('please implement functionality in handle_packet')
##############################################################
#************************************************************
##############################################################
# $读写线程$
class ReadThread(ReaderThread):

    def __init__(self,serial_instance,protocol_factory,Myqueue):
        super(ReadThread,self).__init__(serial_instance = serial_instance,protocol_factory = protocol_factory)
        self.temp = None
        self.queue = Myqueue
        self.flag = None
        self.readerStateSingal = MySingnal()


    def data_handler(self,handledata):
        # 传输状况标志
        cmdsign = None
        for data0 in handledata:
            if data0 == 'error':
                self.flag = 'False'
            elif isinstance(data0,float):
               try:
                    self.queue.put(data0,block=False)
                    self.flag = 'True'
               except:
                    self.flag = 'Lost_packet'
            elif isinstance(data0,str):
                self.flag = 'CMD'
                cmdsign = data0
            self.readerStateSingal.Tip_Sender(cmdsign, self.flag)


    def run(self):
        """Reader loop"""
        if not hasattr(self.serial, 'cancel_read'):
            self.serial.timeout = 1
        self.protocol = self.protocol_factory()
        try:
            self.protocol.connection_made(self)
        except Exception as e:
            self.alive = False
            self.protocol.connection_lost(e)
            self._connection_made.set()
            return
        error = None
        self._connection_made.set()
        while self.alive and self.serial.is_open:
            try:
                # read all that is there or wait for one byte (blocking)
                data = self.serial.read(self.serial.in_waiting or 1)
            except serial.SerialException as e:
                # probably some I/O problem such as disconnected USB serial
                # adapters -> exit
                error = e
                break
            else:
                if data:
                    # make a separated try-except for called used code
                    try:
                        self.temp = self.protocol.data_received(data)
                        self.data_handler(self.temp)
                    except Exception as e:
                        error = e
                        break
        self.alive = False
        self.protocol.connection_lost(error)
        self.protocol = None
##############################################################
# ************************************************************
##############################################################
# $日志表格显示线程$
class LogicalTable(QThread):
    MAXROWSIZE = 32
    MAXCLOSIZE = 4
    signal_OpenEvent = 9
    signal_CloseEvent = 10
    UPDATE_LOGIC = 11
    logic_OpenState = False
    def __init__(self,widget,label,database):
        super(LogicalTable,self).__init__()
        self._lock = QMutex()  # 线程数据库访问锁
        self.displaywidget = widget
        self.displaydatabase = database
        self.updateflag = True
        self.label = label
        self.model = QStandardItemModel(self)
        self.logicInit()  # 加载初始化
        self.displaywidget.setModel(self.model)

    # 日志数据更新
    # 获取访问日志数据长x宽
    # 且插入数据
    def logicDisplay(self):
        self.label.close()
        self.displaywidget.show()
        self.model.clear()
        self.row = None
        self.cloumn = None
        mylist = ["ID","访问名称","访问日期","访问时间"]
        with QMutexLocker(self._lock):
            self.displaydatabase.loadDataBase(2)
            self.textitemlist = [self.displaydatabase.logcat_id,
                                 self.displaydatabase.logcat_name,
                                 self.displaydatabase.logcat_datetime,
                                 self.displaydatabase.logcat_late
                                 ]
            self.row = len(self.displaydatabase.logcat_id)
            self.cloumn = self.MAXCLOSIZE
            self.model.setRowCount(self.MAXROWSIZE)
            self.model.setColumnCount(self.cloumn)
            # 显示标题
            self.item_list = [QStandardItem('{}'.format(datatext)) for datatext in
                              mylist]  # 往每个项目插入对应数据
            for clo in range(self.MAXCLOSIZE):
                self.model.setItem(0, clo, self.item_list[clo])

            if self.row <= self.MAXROWSIZE:
                y = list(range(self.row))
                y.reverse()
                rowx = 0
                for row in y:
                    self.item_list = [QStandardItem('{}'.format(datatext[row])) for datatext in
                                      self.textitemlist]  # 往每个项目插入对应数据
                    for clo in range(self.MAXCLOSIZE):
                        self.model.setItem(rowx+1,clo,self.item_list[clo])
                    rowx += 1
            else:
                y = list(range((self.row - self.MAXROWSIZE),self.row))
                y.reverse()
                rowx = 0
                for row in y:
                    self.item_list = [QStandardItem('{}'.format(datatext[row])) for datatext in
                                      self.textitemlist]  # 往每个项目插入对应数据
                    for clo in range(self.MAXCLOSIZE):
                        self.model.setItem(rowx+1,clo,self.item_list[clo])
                    rowx += 1
                pass
        self.displaywidget.setEditTriggers(QAbstractItemView.NoEditTriggers)  # 无法编辑
        self.displaywidget.horizontalHeader().setStretchLastSection(True)  # 自动调整补充窗口
        pass

    # 信号处理
    def signalLogicHandle(self,event):
        self.start()
        if event == self.signal_OpenEvent:
            self.logic_OpenState = True
        elif event == self.signal_CloseEvent:
            self.logic_OpenState = False
        elif event == self.UPDATE_LOGIC:
            self.updateflag = True
        pass

    # 关闭和初始化处理
    def logicInit(self):
        self.displaywidget.close()
        self.label.show()

    def run(self):
        while True:
            if self.logic_OpenState == True :
                if self.updateflag == True:
                    self.logicDisplay() # 加载数据库访问
                    self.updateflag = False
                    self.sleep(1)
            elif self.logic_OpenState == False:
                self.logicInit() # 显示初始化图形
                self.updateflag = True
                self.sleep(1)
##############################################################
#************************************************************
##############################################################
# $摄像头显示线程$
class LabelThread(QThread):
    ISCAPDISPLAY = False
    videoSignal = pyqtSignal(QImage)
    def __init__(self, video):
        super(LabelThread,self).__init__()
        self.video = video  # 摄像头视频图像
        self.detector = dlib.get_frontal_face_detector()

    # 信号事件处理
    def signalHandle(self, event):
        self.ISCAPDISPLAY = event
        pass

    def run(self):
        while True:
                try:
                    if self.video.isOpened():
                        # cap.read()
                        # 返回两个值：
                        #    一个布尔值true/false，用来判断读取视频是否成功/是否到视频末尾
                        #    图像对象，图像的三维矩阵
                        flag, im_rd = self.video.read()
                        # 每帧数据延时1ms，延时为0读取的是静态帧
                        kk = cv2.waitKey(1)
                        # 检测到人脸
                        dets = self.detector(im_rd, 1)
                        if len(dets) != 0:
                            biggest_face = dets[0]
                            # 取占比最大的脸
                            maxArea = 0
                            for det in dets:
                                w = det.right() - det.left()
                                h = det.top() - det.bottom()
                                if w * h > maxArea:
                                    biggest_face = det
                                    maxArea = w * h
                                    # 绘制矩形框

                            cv2.rectangle(im_rd, tuple([biggest_face.left(), biggest_face.top()]),
                                          tuple([biggest_face.right(), biggest_face.bottom()]),
                                          (255, 0, 255), 2)
                            img_height, img_width = im_rd.shape[:2]
                            image = cv2.resize(im_rd, (int(img_height * 0.8), int(img_width * 0.8)))
                            image1 = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
                            imgx = QImage(image1.data, image1.shape[1], image1.shape[0], QImage.Format_RGB888)
                        else:
                            img_height, img_width = im_rd.shape[:2]
                            image = cv2.resize(im_rd, (int(img_height * 0.8), int(img_width * 0.8)))
                            image1 = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
                            imgx = QImage(image1.data, image1.shape[1], image1.shape[0], QImage.Format_RGB888)
                        if  self.ISCAPDISPLAY:
                            self.videoSignal.emit(imgx)  # 更新图片
                except:
                    print('traceback.print_exc():', print_exc())
        pass
##############################################################
# ************************************************************
##############################################################
_translate = QtCore.QCoreApplication.translate
# $应用进程$
class Application(Ui_MainWindow,QtWidgets.QMainWindow):
    ID_WORKER_UNAVIABLE = -1
    # 载入数据模式
    WORKER_INFO = 1
    LOGCAT_INFO = 2
    OTHERS_INFO = 3
    ACCOUNT_INFO = 4
    # 信号传输模式选择
    INSPECT_FACE_SINGAL = 5
    EXIT_SINGAL = 6
    REGISTER_SINGAL = 7
    Register_FINISHSINGAL = 8
    signal_OpenEvent = 9
    signal_CloseEvent = 10
    UPDATE_LOGIC = 11
    AUTO_CHECK_SINGAL = 12
    Register_FAILED = 13

    # 人脸识别信号
    faceRegisterSignal = QtCore.pyqtSignal(int)
    faceCheckSignal = QtCore.pyqtSignal(int)
    faceSetNameSignal = QtCore.pyqtSignal(str,str)
    faceCapSignal = QtCore.pyqtSignal(bool)
    # 日志显示信号
    logicalDisplaySignal = QtCore.pyqtSignal(int)
    def __init__(self,
                myqueue = None,
                protocol_factory = None,
                file = None,
                parent = None):
        super(Application, self).__init__(parent = parent)
        # 界面初始化
        self.setupUi(self)
        self.file = file
        # 界面显示的好看图片
        self.videoPicture = QImage("data/2/Beatiful/2-2.png")
        self.loadingPicture = QImage("data/2/Loading/loading_2.png")
        # 加载数据锁
        self._Mlock = QMutex()
        # 人脸识别线程
        self.face_thread = FaceLearning(self.file)
        # 管理员数据字典
        with QMutexLocker(self._Mlock):
            self.accoutDatabase = {self.face_thread.database.account_num[i]: self.face_thread.database.password[i] for i in
                                   range(len(self.face_thread.database.account_num))}
        # 日志显示线程
        self.logic = LogicalTable(self.tableView,self.logicShow,self.face_thread.database)
        self.logicalTableInit()
        # 摄像头显示线程
        self.capLabel = LabelThread(self.face_thread.cap)
        # 用户删除槽连接
        self.accountBoxInit()
        self.ser = None
        self.myqueue = myqueue
        self.protocol_factory = protocol_factory
        # 串口接收线程
        self.read_threads = None
        # 串口接收数
        self.receive_Num = 0
        # 串口丢包数
        self.receive_Lost = 0
        # 实例化一个定时器
        self.timer = QTimer(self)
        self.lcdDisplay(10.10,10.10)
        self.serialinit()
        # 人脸识别线程开启
        self.signalFaceConnect()
        try:
            # 摄像头显示线程开启
            self.capLabel.start()
        except:
            print(print_exc())
        self.face_thread.start()
        # 日志显示线程开启
        self.logic.start()
        # 加载好看的图片
        self.videoLabel.setPixmap(QPixmap.fromImage(self.videoPicture))
        self.logicShow.setPixmap(QPixmap.fromImage(self.loadingPicture))

    # 处理窗口关闭事件
    def closeEvent(self,e):
        self.timer.stop()
        if self.ser != None:
            self.comClose()
        self.face_thread.exit(0)
        self.logic.exit(1)
        self.capLabel.exit(2)

    # 串口初始化
    def serialinit(self):
        # 串口失效
        self.ser = None
        # 显示接收的字符数量
        dis = '接收：' + '{:d}'.format(self.receive_Num) + '  丢包数：' + '{:d}'.format(self.receive_Lost)
        self.statusbar.showMessage(dis)

        # 刷新一下串口的列表
        self.refresh()

        # 波特率
        self.Com_Baud.addItem('115200')
        self.Com_Baud.addItem('57600')
        self.Com_Baud.addItem('56000')
        self.Com_Baud.addItem('38400')
        self.Com_Baud.addItem('19200')
        self.Com_Baud.addItem('14400')
        self.Com_Baud.addItem('9600')
        self.Com_Baud.addItem('4800')
        self.Com_Baud.addItem('2400')
        self.Com_Baud.addItem('1200')

        # 数据位
        self.Com_Bytes.addItem('8')
        self.Com_Bytes.addItem('7')
        self.Com_Bytes.addItem('6')
        self.Com_Bytes.addItem('5')

        # 停止位
        self.Com_StopBytes.addItem('1')
        self.Com_StopBytes.addItem('1.5')
        self.Com_StopBytes.addItem('2')

        # 校验位
        self.Com_CheckByte.addItem('NONE')
        self.Com_CheckByte.addItem('ODD')
        self.Com_CheckByte.addItem('EVEN')

        # 刷新串口外设按钮
        self.Com_Refrsh.clicked.connect(self.refresh)
        # 打开关闭串口按钮
        self.Com_Open.clicked.connect(self.comOpen)
        # 关闭串口按钮
        self.Com_Close.clicked.connect(self.comClose)
        # 波特率修改
        self.Com_Baud.activated.connect(self.baudModify)
        # 串口号修改
        self.Com_List.activated.connect(self.comModify)
        # 执行一下打开串口
        self.comOpen()
        self.Com_Open.setChecked(True)

    # 刷新一下串口
    def refresh(self):
        # 查询可用的串口
        plist = list(serial.tools.list_ports.comports())

        if len(plist) <= 0:
            print("No used com!");
            self.statusbar.showMessage('没有可用的串口')
        else:
            # 把所有的可用的串口输出到comboBox中去
            self.Com_List.clear()

            for i in range(0, len(plist)):
                plist_0 = list(plist[i])
                self.Com_List.addItem(str(plist_0[0]))
            print("刷新成功！！！")

    # 波特率修改
    def baudModify(self):
        try:
            if self.ser != None and self.ser.is_open == False:
                self.ser.baudrate = int(self.Com_Baud.currentText())
        except:
            QMessageBox.critical(self, '参数修改提示', '该串口正在运行不允许修改参数')

    # 串口号修改
    def comModify(self):
        try:
            if self.ser != None and self.ser.is_open == False:
                self.ser.port = self.Com_List.currentText()
        except:
            QMessageBox.critical(self, '参数修改提示', '该串口正在运行不允许修改参数')

    # 打开串口
    def comOpen(self):
        try:
            # 输入参数'COM13',115200
            self.ser = serial.Serial(self.Com_List.currentText(), int(self.Com_Baud.currentText()), timeout=0.5)
            self.read_threads = ReadThread(serial_instance=self.ser,
                                           protocol_factory=self.protocol_factory,
                                           Myqueue=self.myqueue)
            self.read_threads.readerStateSingal.Tip_Singal.connect(self.Datastate_handle)
            self.read_threads.start()
            print('串口调用成功')
        except:
            QMessageBox.critical(self, '串口提示', '没有可用的串口或当前串口被占用')
            print('串口调用失败')
            return None
        # 字符间隔超时时间设置
        # self.ser.interCharTimeout = 1
        # 1ms的测试周期
        self.timer.start(2)
        self.comstate_tip.setText('串口已开启')
        self.Com_Open.setEnabled(False)
        self.Com_Close.setEnabled(True)
        print('open')

    # 关闭串口
    def comClose(self):
        # 关闭定时器，停止读取接收数据
        self.timer.stop()
        try:
            # 关闭串口
            self.read_threads.close()
            self.read_threads.join(2)
            self.clearDataVolume()
        except:
            QMessageBox.critical(self, '串口提示', '关闭串口失败')
            return None

        self.ser = None
        self.ser_threads = None
        self.comstate_tip.setText('串口已关闭')
        self.Com_Close.setEnabled(False)
        self.Com_Open.setEnabled(True)
        print('close!')
        return True
        pass

    # 监控串口数据接收是否正常
    def Datastate_handle(self,CMD, state):

        if state is not 'error' and state is not 'Lost_packet':
            self.receive_Num += 1
            if self.myqueue.empty() is not True:
                temp = self.myqueue.get()
                self.lcdDisplay(temp,temp)
        else:
            self.receive_Lost += 1

        if CMD is not None:
            pass  # 预留命令信号处理
        # 统计接收字符的数量
        dis = '接收：' + '{:d}'.format(self.receive_Num) + '    丢包数：' + '{:d}'.format(self.receive_Lost)
        self.statusbar.showMessage(dis)
        pass

    # 清除数据量计数
    def clearDataVolume(self):
        self.receive_Num = 0
        self.receive_Lost = 0
        pass

    # 液晶显示屏
    def lcdDisplay(self,number1,number2):

        self.lcdNumber.setSegmentStyle(QLCDNumber.Outline)
        self.lcdNumber.setDigitCount(5)
        self.lcdNumber.display(number1)

        self.lcdNumber_2.setSegmentStyle(QLCDNumber.Outline)
        self.lcdNumber_2.setDigitCount(5)
        self.lcdNumber_2.display(number2)
        pass

    # 日志显示初始化信号<-->槽连接
    def logicalTableInit(self):
        self.pushButton.clicked.connect(self.logicalTableDisplay)
        self.logicalDisplaySignal.connect(self.logic.signalLogicHandle)
        self.pushButton_2.clicked.connect(self.logicalTableSave)
        pass

    # 输入密码获取管理员权限
    def getView(self,dis):
        # 管理员数据字典
        with QMutexLocker(self._Mlock):
            self.accoutDatabase = {self.face_thread.database.account_num[i]: self.face_thread.database.password[i] for i in
                                   range(len(self.face_thread.database.account_num))}
        account,ok= QInputDialog.getText(self, 'Account Input', 'Please enter the account number:')
        secret,bingo = QInputDialog.getText(self, 'secret Input', 'Please enter the secret number:')
        if ok and bingo:
            if account in self.accoutDatabase.keys():
                if secret == self.accoutDatabase.get(account):
                    if dis:
                        if self.pushButton_2.isEnabled() and self.Register_Button.isEnabled():
                            self.logicalDisplaySignal.emit(self.signal_OpenEvent)
                    else:
                        pass
                    return True
                else:
                    return "账号或者密码不正确"
            else:
                return "账号或者密码不正确"
            pass
        else:
            return False

    # 日志显示
    def logicalTableDisplay(self):
        if self.pushButton.text() == "查看访问日志":
            tips = self.getView(True)
            if tips == True:
                self.pushButton.setText(_translate("MainWindow", "关闭访问日志"))
            elif tips == False:
                pass            # 未输入时不给用提示，提高用户体验
            else:
                try:
                    QMessageBox.critical(self, '登陆提示', tips)
                except:
                    print("出错了")
                    pass
        else:
            self.pushButton.setText(_translate("MainWindow", "查看访问日志"))
            self.logicalDisplaySignal.emit(self.signal_CloseEvent)
        pass

    # 日志保存
    def logicalTableSave(self):
        self.pushButton_2.setEnabled(False)
        if self.pushButton.text() == "关闭访问日志":
            try:
                fileName2, ok2 = QFileDialog.getSaveFileName(self,
                                                             "文件保存",
                                                             "C:/",
                                                             "All Files (*);;Text Files (*.txt)")
                QMessageBox.critical(self, '保存日志提示', "保存日志成功")
            except:
                QMessageBox.critical(self, '保存日志提示', "保存日志失败")
                pass
        else:
            try:
                QMessageBox.critical(self, '保存日志提示', "请先登陆账号")
            except Exception:
                QMessageBox.critical(self, '错误提示', Exception)
                pass
            tips = self.getView(True)
            if tips == True:
                QMessageBox.critical(self, '保存日志提示', "保存日志成功")
            else:
                try:
                    QMessageBox.critical(self, '登陆提示', tips)
                except:
                    print("出错了")
                    pass
        self.pushButton_2.setEnabled(True)
        pass

    # 清除非法字符
    def clearValidate(self,title):
        # 文件保存非法字符
        rstr = r"[\/\\\:\*\?\"\<\>\|]"  # '/ \ : * ? " < > |'
        new_title = re.sub(rstr, "_", title)  # 替换为下划线
        return new_title
        pass

    # 注册人脸点击信号槽
    def registerSignalSend(self):
        self.Register_Button.setEnabled(False)
        self.faceCapSignal.emit(True)
        self.registerlist = []
        with QMutexLocker(self._Mlock):
            self.face_thread.database.loadDataBase(self.ACCOUNT_INFO)
        tips = self.getView(True) # 获取管理员权限
        if tips == True:
            name, ok = QInputDialog.getText(self, 'Name Input', 'Please enter the name:')
            idle, bingo = QInputDialog.getText(self, 'Id Input', 'Please enter the id(0~65535):')
            if ok and bingo:
                with QMutexLocker(self._Mlock):
                    self.face_thread.database.loadDataBase(self.WORKER_INFO)
                while True:
                    try:
                        isinstance(int(idle),int)
                        if (int(idle) not in self.face_thread.database.knew_id):
                            break
                    except:
                        QMessageBox.critical(self, '注册提示', "ID请输入数字")
                    QMessageBox.critical(self, '注册提示', "该ID已经存在")
                    name, ok = QInputDialog.getText(self, 'Name Input', 'Please enter the name:')
                    idle, bingo = QInputDialog.getText(self, 'Id Input', 'Please enter the id(0~65535):')
                    if ok == False or bingo == False:
                        self.faceCapSignal.emit(False)
                        self.Register_Button.setEnabled(True)
                        self.videoLabel.setPixmap(QPixmap.fromImage(self.videoPicture))
                        return
                jurisdiction,yeah = QInputDialog.getText(self, 'Jurisdiction Request', 'Please enter guest or admin')
                if yeah:
                    if jurisdiction == "guest":
                        self.registerlist = []
                        self.faceSetNameSignal.emit(self.clearValidate(name),idle)
                        os.makedirs(self.face_thread.PATH_FACE + self.face_thread.name)
                        self.faceRegisterSignal.emit(self.REGISTER_SINGAL)
                    elif jurisdiction == "admin":
                        while True:
                            acconut, enheng = QInputDialog.getText(self, 'New Acconut Input',
                                                                   'Please enter the New Acconut:')
                            password, a = QInputDialog.getText(self, 'New password Input',
                                                               'Please enter the New password:')
                            if enheng and a:
                                with QMutexLocker(self._Mlock):
                                    self.face_thread.database.loadDataBase(self.ACCOUNT_INFO)
                                if acconut not in self.face_thread.database.account_num:
                                    self.registerlist = [acconut, password,idle]  # 暂存管理员人员账户
                                    self.faceSetNameSignal.emit(self.clearValidate(name), idle)
                                    os.makedirs(self.face_thread.PATH_FACE + self.face_thread.name)
                                    self.faceRegisterSignal.emit(self.REGISTER_SINGAL)
                                    break
                                else:
                                    QMessageBox.critical(self, '注册提示', "已经存在该管理员账户")
                            else:
                                self.faceCapSignal.emit(False)
                                self.Register_Button.setEnabled(True)
                                self.videoLabel.setPixmap(QPixmap.fromImage(self.videoPicture))
                                break
                    else:
                        while True:
                            QMessageBox.critical(self, '注册提示', "请输入正确的格式")
                            jurisdiction, yeah = QInputDialog.getText(self, 'Jurisdiction Request',
                                                                      'Please enter guest or admin')
                            if yeah:
                                if jurisdiction == "guest":
                                    self.registerlist = []
                                    self.faceSetNameSignal.emit(self.clearValidate(name), idle)
                                    os.makedirs(self.face_thread.PATH_FACE + self.face_thread.name)
                                    self.faceRegisterSignal.emit(self.REGISTER_SINGAL)
                                    break
                                elif jurisdiction == "admin":
                                    while True:
                                        acconut, enheng = QInputDialog.getText(self, 'New Acconut Input',
                                                                               'Please enter the New Acconut:')
                                        password, a = QInputDialog.getText(self, 'New password Input',
                                                                           'Please enter the New password:')
                                        if enheng and a:
                                            with QMutexLocker(self._Mlock):
                                                self.face_thread.database.loadDataBase(self.ACCOUNT_INFO)
                                            if acconut not in self.face_thread.database.account_num:
                                                self.registerlist = [acconut, password,idle]  # 暂存管理员人员账户
                                                self.faceSetNameSignal.emit(self.clearValidate(name), idle)
                                                os.makedirs(self.face_thread.PATH_FACE + self.face_thread.name)
                                                self.faceRegisterSignal.emit(self.REGISTER_SINGAL)
                                                break
                                            else:
                                                QMessageBox.critical(self, '注册提示', "已经存在该管理员账户")
                                        else:
                                            self.faceCapSignal.emit(False)
                                            self.Register_Button.setEnabled(True)
                                            self.videoLabel.setPixmap(QPixmap.fromImage(self.videoPicture))
                                            break
                                    break
                                else:
                                    pass
                            else:
                                self.faceCapSignal.emit(False)
                                self.Register_Button.setEnabled(True)
                                self.videoLabel.setPixmap(QPixmap.fromImage(self.videoPicture))
                                pass

                        pass
                else:
                    self.faceCapSignal.emit(False)
                    self.Register_Button.setEnabled(True)
                    self.videoLabel.setPixmap(QPixmap.fromImage(self.videoPicture))
                    pass
            else:
                self.faceCapSignal.emit(False)
                self.Register_Button.setEnabled(True)
                self.videoLabel.setPixmap(QPixmap.fromImage(self.videoPicture))
                pass
        elif tips == False:
            self.faceCapSignal.emit(False)
            self.Register_Button.setEnabled(True)
            self.videoLabel.setPixmap(QPixmap.fromImage(self.videoPicture))
            pass  # 未输入时不给用提示，提高用户体验
        else:
            try:
                self.faceCapSignal.emit(False)
                self.Register_Button.setEnabled(True)
                self.videoLabel.setPixmap(QPixmap.fromImage(self.videoPicture))
                QMessageBox.critical(self, '登陆提示', tips)
            except Exception:
                QMessageBox.critical(self, '错误提示', Exception)
                pass
        pass

    # 接收信号处理
    def receiveSignalHandle(self, state):
        if state == self.Register_FINISHSINGAL:
            if len(self.registerlist) > 0:
                with QMutexLocker(self._Mlock):
                    self.face_thread.database.insertRow(self.registerlist,self.ACCOUNT_INFO)
                    # 删除默认密码
                    self.face_thread.database.loadDataBase(self.ACCOUNT_INFO)
                    if len(self.face_thread.database.keyid) == 0:
                        self.face_thread.database.insertRow(['123', '1234', '-1'], self.ACCOUNT_INFO)
                    elif (len(self.face_thread.database.keyid) > 1 and '123' in self.face_thread.database.account_num):
                        self.face_thread.database.deleteRow('123', self.ACCOUNT_INFO)
                    self.face_thread.database.loadDataBase(self.ACCOUNT_INFO)

            self.faceCapSignal.emit(False)
            self.Register_Button.setEnabled(True)
            self.videoLabel.setPixmap(QPixmap.fromImage(self.videoPicture))
        if state == self.Register_FAILED:
            QMessageBox.critical(self, '注册失败', '人脸已经存在或没有识别到人脸，请靠近摄像头')
            self.faceCapSignal.emit(False)
            self.Register_Button.setEnabled(True)
            self.videoLabel.setPixmap(QPixmap.fromImage(self.videoPicture))
        pass

    # 核验人脸点击信号槽
    def checkSignalSend(self):
        if self.pushButton_3.text() == "识别解锁":
            self.Register_Button.setEnabled(False)
            self.faceCheckSignal.emit(self.INSPECT_FACE_SINGAL)
            self.faceCapSignal.emit(True)
            self.pushButton_3.setText(_translate("MainWindow", "解锁结束"))
            self.videoLabel.setPixmap(QPixmap.fromImage(self.videoPicture))
        elif self.pushButton_3.text() == "解锁结束":
            self.Register_Button.setEnabled(True)
            self.faceCapSignal.emit(False)
            self.faceCheckSignal.emit(self.AUTO_CHECK_SINGAL)
            self.pushButton_3.setText(_translate("MainWindow", "识别解锁"))
            self.videoLabel.setPixmap(QPixmap.fromImage(self.videoPicture))
        pass

    # 脸部图片显示
    def faceDisplay(self,img):
        self.videoLabel.setPixmap(QPixmap.fromImage(img))

    # 面部识别信号<-->槽连接
    def signalFaceConnect(self):
        self.face_thread.Register_FinishSignal.connect(self.receiveSignalHandle)
        self.face_thread.update_LoadSignal.connect(self.logic.signalLogicHandle)
        self.Register_Button.clicked.connect(self.registerSignalSend)
        self.pushButton_3.clicked.connect(self.checkSignalSend)
        self.faceRegisterSignal.connect(self.face_thread.signalHandle)
        self.faceSetNameSignal.connect(self.face_thread.setName)
        self.faceCheckSignal.connect(self.face_thread.signalHandle)
        self.faceCapSignal.connect(self.capLabel.signalHandle)
        self.capLabel.videoSignal.connect(self.faceDisplay)
        pass

    # 用户BOX初始化
    def accountBoxInit(self):
        self.DeleteButton.setEnabled(False)
        self.selectButton.clicked.connect(self.displayAccount)
        self.DeleteButton.clicked.connect(self.deleteAccount)

    # 显示账户
    def displayAccount(self):
        if self.selectButton.text() == "查询用户":
            tips = self.getView(False)
            if tips == True:
                self.DeleteButton.setEnabled(True)
                try:
                 self.face_thread.database.loadDataBase(self.WORKER_INFO)
                 temp = self.face_thread.database.knew_id
                 for text in temp:
                    self.RegisterBox.addItem(str(text))
                 self.selectButton.setText(_translate("MainWindow", "关闭查询"))
                except Exception:
                    QMessageBox.critical(self, '错误提示', Exception)
            elif tips == False:
                pass  # 未输入时不给用提示，提高用户体验
            else:
                try:
                    QMessageBox.critical(self, '登陆提示', tips)
                except Exception:
                    QMessageBox.critical(self, '错误提示', Exception)
                    pass
        elif self.selectButton.text() == "关闭查询":
            self.DeleteButton.setEnabled(False)
            self.RegisterBox.clear()
            self.selectButton.setText(_translate("MainWindow", "查询用户"))
        pass

    # 删除账户
    def deleteAccount(self):
        count = 0
        deleteitem = self.RegisterBox.currentText()
        choice = QMessageBox.question(self, 'Title', '确定删除账户'+deleteitem + '?',
                                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
        if choice == QMessageBox.Yes:
            self.face_thread.database.loadDataBase(self.ACCOUNT_INFO)
            self.face_thread.database.loadDataBase(self.WORKER_INFO)
            try:
                for idrow in self.face_thread.database.keyid:
                    if idrow in self.face_thread.database.knew_id:
                        self.face_thread.database.deleteRow(self.face_thread.database.account_num[count],self.ACCOUNT_INFO)
                        break
                    count += 1
                # 初始化密码
                self.face_thread.database.loadDataBase(self.ACCOUNT_INFO)
                if len(self.face_thread.database.keyid) == 0:
                    self.face_thread.database.insertRow(['123', '1234', '-1'], self.ACCOUNT_INFO)
                elif (len(self.face_thread.database.keyid) > 1 and '123' in self.face_thread.database.account_num):
                    self.face_thread.database.deleteRow('123', self.ACCOUNT_INFO)
                self.face_thread.database.deleteRow(deleteitem,self.WORKER_INFO)
            except Exception:
                QMessageBox.critical(self, '错误提示', Exception)
            try:
                self.face_thread.database.loadDataBase(self.WORKER_INFO)
                temp = self.face_thread.database.knew_id
                for text in temp:
                    self.RegisterBox.addItem(str(text))
            except Exception:
                QMessageBox.critical(self, '错误提示', Exception)
        else:
            pass
        pass
##############################################################
# ************************************************************
##############################################################

# $QT应用进程$

app = QApplication(sys.argv)
file = "test.db"
myQueue = Queue()
b = Application(myqueue=myQueue,
                protocol_factory=PrintLines,
                file = file
                )
b.show()
sys.exit(app.exec_())
pass
