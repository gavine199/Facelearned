import dlib  # 人脸识别的库dlib
import numpy  # 数据处理的库numpy
import cv2  # 图像处理的库OpenCv
from PyQt5.QtCore import QThread,QMutex,QMutexLocker,pyqtSignal
from PyQt5.QtGui import QImage
from skimage import io as iio
import os
from time import localtime,strftime
from LearnDatabase import LearnDatabase # 数据库类 存储访问日志、录入人脸数据等
import random  # 陌生人随机ID
from traceback import print_exc # 异常处理打印错误信息，仅调试用

# 人脸识别处理类
class FaceLearning(QThread):
    ID_WORKER_UNAVIABLE = -2
    FACE_EXISTS = -1
    # 载入数据模式
    WORKER_INFO = 1
    LOGCAT_INFO = 2
    OTHERS_INFO = 3
    ACCOUNT_INFO = 4
    # 信号处理模式
    AUTO_CHECK_SINGAL = 12
    INSPECT_FACE_SINGAL = 5
    EXIT_SINGAL = 6
    REGISTER_SINGAL = 7
    Register_FINISHSINGAL = 8
    Register_FAILED = 13
    # 线程事件处理
    IS_EXIT = False
    CHECKFACE_SINGAL = False
    AUTO_CHECKFACE_SINGAL = True
    UPDATE_LOGIC = 11
    update_LoadSignal = pyqtSignal(int) # 重载日志信号
    Register_FinishSignal = pyqtSignal(int) # 注册完成信号
    Label_Sender = pyqtSignal(QImage)
    def __init__(self,file):
        super(FaceLearning,self).__init__()
        self._mutex = QMutex()
        self.PATH_FACE = "data/face_img_database/"
        # face recognition model, the object maps human faces into 128D vectors
        self.facerec = dlib.face_recognition_model_v1("model/dlib_face_recognition_resnet_model_v1.dat")
        # Dlib 预测器
        self.detector = dlib.get_frontal_face_detector()
        self.predictor = dlib.shape_predictor('model/shape_predictor_68_face_landmarks.dat')
        # 数据库
        self.file = file
        self.database = LearnDatabase(self.file)
        # 摄像头
        self.cap = cv2.VideoCapture(0)
        self.initData()

    # 静态方法
    @staticmethod
    def return_euclidean_distance(feature_1, feature_2):
        feature_1 = numpy.array(feature_1)
        feature_2 = numpy.array(feature_2)
        dist = numpy.sqrt(numpy.sum(numpy.square(feature_1 - feature_2)))
        print("欧式距离: ", dist)

        if dist > 0.4:
            return "diff"
        else:
            return "same"

    def initData(self):
        self.name = ""
        self.id = self.ID_WORKER_UNAVIABLE
        self.face_feature = ""
        self.image = None
        self.flag = 0
        self.pic_num = 0
        self.flag_registed = False
        self.puncard_time = "09:00:00"
        with QMutexLocker(self._mutex):
            self.database.loadDataBase(self.WORKER_INFO)
            self.database.loadDataBase(self.LOGCAT_INFO)
            self.database.loadDataBase(self.OTHERS_INFO)
            self.database.loadDataBase(self.ACCOUNT_INFO)
        pass

    def getDateAndTime(self):
        dateandtime = strftime("%Y-%m-%d %H:%M:%S",localtime())
        return "["+dateandtime+"]"
        pass

    # 开启摄像头注册
    def registerCap(self):
        with QMutexLocker(self._mutex):
            # 加载录入用户数据库
            self.database.loadDataBase(self.WORKER_INFO)
        while self.cap.isOpened():
                # cap.read()
                # 返回两个值：
                #    一个布尔值true/false，用来判断读取视频是否成功/是否到视频末尾
                #    图像对象，图像的三维矩阵
                flag, im_rd = self.cap.read()
                cv2.waitKey(1)
                # 人脸数 dets
                dets = self.detector(im_rd, 1)

                # 检测到人脸
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
                                  (255, 0, 0), 2)
                    # 获取图片的长和宽
                    img_height, img_width = im_rd.shape[:2]
                    image = cv2.resize(im_rd, (int(img_height * 0.8), int(img_width * 0.8)))
                    image1 = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
                    imgx = QImage(image1.data, image1.shape[1], image1.shape[0], QImage.Format_RGB888)
                    # TODO:SEND SIGNAL TO MAINWINDOW TO DIS(Get)
                    # 获取当前捕获到的图像的所有人脸的特征，存储到 features_cap_arr
                    shape = self.predictor(im_rd, biggest_face)
                    features_cap = self.facerec.compute_face_descriptor(im_rd, shape)

                    # 对于某张人脸，遍历所有存储的人脸特征
                    for i, knew_face_feature in enumerate(self.database.knew_face_feature):
                        # 将某张人脸与存储的所有人脸数据进行比对
                        compare = self.return_euclidean_distance(features_cap, knew_face_feature)
                        if compare == "same":  # 找到了相似脸
                            print("此人已经存在了呀")
                            # TODO:SEND SIGNAL TO MAINWINDOW TO REMAIN THE PASSAGE
                            self.flag_registed = True
                            try:
                                self.onFinishRegister()
                            except:
                                print('traceback.print_exc():', print_exc())
                            return self.FACE_EXISTS  # 人员存在

                            # print(features_known_arr[i][-1])
                    face_height = biggest_face.bottom() - biggest_face.top()
                    face_width = biggest_face.right() - biggest_face.left()
                    im_blank = numpy.zeros((face_height, face_width, 3), numpy.uint8)
                    try:
                        for ii in range(face_height):
                            for jj in range(face_width):
                                im_blank[ii][jj] = im_rd[biggest_face.top() + ii][biggest_face.left() + jj]
                        self.pic_num += 1
                        # 解决python3下使用cv2.imwrite存储带有中文路径图片
                        if len(self.name) > 0:
                            print("开启写入数据")
                            cv2.imencode('.jpg', im_blank)[1].tofile(
                                self.PATH_FACE + self.name + "/img_face_" + str(self.pic_num) + ".jpg")  # 正确方法
                            print("写入本地：", str(self.PATH_FACE + self.name) + "/img_face_" + str(self.pic_num) + ".jpg")
                    except:
                        print('traceback.print_exc():',print_exc())
                        print("保存照片异常,请对准摄像头")
                        return False

                    if self.pic_num == 10:
                        try:
                            self.onFinishRegister()
                        except:
                            print('traceback.print_exc():', print_exc())
                        return True

    # 是否写入数据库
    def onFinishRegister(self):
        if self.flag_registed == True:
            dir = self.PATH_FACE + self.name
            for file in os.listdir(dir):
                os.remove(dir + "/" + file)
                print("已删除已录入人脸的图片", dir + "/" + file)
            os.rmdir(self.PATH_FACE + self.name)
            print("已删除已录入人脸的姓名文件夹", dir)
            self.initData()
            return
        if self.pic_num > 0:
            pics = os.listdir(self.PATH_FACE + self.name)
            feature_list = []
            feature_average = []
            for i in range(len(pics)):
                pic_path = self.PATH_FACE + self.name + "/" + pics[i]
                print("正在读的人脸图像：", pic_path)
                img = iio.imread(pic_path)
                img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                dets = self.detector(img_gray, 1)
                if len(dets) != 0:
                    shape = self.predictor(img_gray, dets[0])
                    face_descriptor = self.facerec.compute_face_descriptor(img_gray, shape)
                    feature_list.append(face_descriptor)
                else:
                    face_dssaescriptor = 0
                    print("未在照片中识别到人脸")
            if len(feature_list) > 0:
                for j in range(128):
                    # 防止越界
                    feature_average.append(0)
                    for i in range(len(feature_list)):
                        feature_average[j] += feature_list[i][j]
                    feature_average[j] = (feature_average[j]) / len(feature_list)
                # 数据库写入
                with QMutexLocker(self._mutex):
                    self.database.insertRow([self.id, self.name, feature_average], self.WORKER_INFO)
                    print("写入数据库成功")
                # 删除处理图片的缓存
                if True :
                    dir = self.PATH_FACE + self.name
                    for file in os.listdir(dir):
                        os.remove(dir + "/" + file)
                        print("已删除已录入人脸的图片", dir + "/" + file)
                    os.rmdir(self.PATH_FACE + self.name)
                    print("已删除已录入人脸的姓名文件夹", dir)
                    self.initData()
                    return
            pass
        else:
            os.rmdir(self.PATH_FACE + self.name)
            print("已删除空文件夹", self.PATH_FACE + self.name)
        self.initData()

    # 陌生人入库
    def othersRegister(self):
        if self.flag_registed == True:
            dir = self.PATH_FACE + self.id
            for file in os.listdir(dir):
                os.remove(dir + "/" + file)
                print("已删除已录入人脸的图片", dir + "/" + file)
            os.rmdir(self.PATH_FACE + self.id)
            print("已删除已录入人脸的姓名文件夹", dir)
            self.initData()
            return
        if self.pic_num > 0:
            pics = os.listdir(self.PATH_FACE + self.id)
            feature_list = []
            feature_average = []
            for i in range(len(pics)):
                pic_path = self.PATH_FACE + self.id + "/" + pics[i]
                print("正在读的人脸图像：", pic_path)
                img = iio.imread(pic_path)
                img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                dets = self.detector(img_gray, 1)
                if len(dets) != 0:
                    shape = self.predictor(img_gray, dets[0])
                    face_descriptor = self.facerec.compute_face_descriptor(img_gray, shape)
                    feature_list.append(face_descriptor)
                else:
                    face_dssaescriptor = 0
                    print("未在照片中识别到人脸")
            if len(feature_list) > 0:
                for j in range(128):
                    # 防止越界
                    feature_average.append(0)
                    for i in range(len(feature_list)):
                        feature_average[j] += feature_list[i][j]
                    feature_average[j] = (feature_average[j]) / len(feature_list)
                # 数据库写入
                with QMutexLocker(self._mutex):
                    datetime1 = self.getDateAndTime()
                    self.database.insertRow([self.id,datetime1,feature_average], self.OTHERS_INFO)
                    print("写入数据库成功")
                # self.infoText.AppendText(self.getDateAndTime() + "工号:" + str(self.id)
                #                         + " 姓名:" + self.name + " 的人脸数据已成功存入\r\n")
            pass
        else:
            os.rmdir(self.PATH_FACE + self.id)
            print("已删除空文件夹", self.PATH_FACE + self.id)
        self.initData()

    # 核验人脸
    def punchCardCap(self,Unlock):
        with QMutexLocker(self._mutex):
            # 加载录入用户数据库
            self.database.loadDataBase(self.WORKER_INFO)
            # 加载陌生人用户数据库
            # self.database.loadDataBase(self.OTHERS_INFO)
            # 加载访问日志用户数据库
            # self.database.loadDataBase(self.LOGCAT_INFO)
        # cap是否初始化成功
        if self.cap.isOpened():
            # cap.read()
            # 返回两个值：
            #    一个布尔值true/false，用来判断读取视频是否成功/是否到视频末尾
            #    图像对象，图像的三维矩阵
            flag, im_rd = self.cap.read()
            cv2.waitKey(1)
            # 人脸数 dets
            dets = self.detector(im_rd, 1)
            # 检测到人脸
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
                image = cv2.resize(im_rd, (int(img_height*0.8), int(img_width*0.8)))
                image1 = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
                # 获取当前捕获到的图像的所有人脸的特征，存储到 features_cap_arr
                shape = self.predictor(im_rd, biggest_face)
                features_cap = self.facerec.compute_face_descriptor(im_rd, shape)

                # 对于某张人脸，遍历所有存储的注册用户人脸特征
                for i, knew_face_feature in enumerate(self.database.knew_face_feature):
                    # 将某张人脸与存储的所有人脸数据进行比对
                    compare = self.return_euclidean_distance(features_cap, knew_face_feature)
                    if compare == "same":  # 找到了相似脸
                        if Unlock == True:
                            return True
                        self.randomid = str(self.database.knew_id[i]) + "--" +str(random.randint(1000,65535))
                        print("已注册数据库人员")
                        flag = 0
                        nowdt = self.getDateAndTime()
                        try:
                            for j, logcat_name in enumerate(self.database.logcat_name):
                                # 如果存在同时同人就退出写入
                                if logcat_name == self.database.knew_name[i] and nowdt[0:nowdt.index(" ")] == \
                                        self.database.logcat_datetime[j]\
                                        and nowdt[nowdt.index(" "):] == self.database.logcat_late[j]:
                                    flag = 1
                                    break
                        except:
                            print('traceback.print_exc():', print_exc())
                        if flag == 1:
                            break
                        logicdata = [self.randomid,self.database.knew_name[i],nowdt[0:nowdt.index(" ")],nowdt[nowdt.index(" ")+1:]]
                        self.database.insertRow(logicdata,self.LOGCAT_INFO)
                        self.update_LoadSignal.emit(self.UPDATE_LOGIC)
                if Unlock == True:
                    return False
                '''
                # 对于某张人脸，遍历所有存储的陌生人脸特征
                for i, others_face_feature in enumerate(self.database.others_face_feature):
                    # 将某张人脸与存储的所有人脸数据进行比对
                    compare = self.return_euclidean_distance(features_cap, others_face_feature)
                    if compare == "same":  # 找到了相似脸
                        print("已录入陌生人数据库人员")
                        flag = 0
                        nowdt = self.getDateAndTime()
                        try:
                            for j, others_id in enumerate(self.database.others_id):
                                # 如果存在同时同人就退出写入
                                if others_id == self.database.others_id[i] and nowdt[0:nowdt.index(" ")] == \
                                        self.database.logcat_datetime[j] \
                                        and nowdt[nowdt.index(" "):] == self.database.logcat_late[j]:
                                    flag = 1
                                    break
                        except:
                            print('traceback.print_exc():', traceback.print_exc())
                        if flag == 1:
                            break
                        logicdata = [self.database.others_id[i], "陌生人",
                                     nowdt[0:nowdt.index(" ")], nowdt[nowdt.index(" ") + 1:]]
                        self.database.insertRow(logicdata, self.LOGCAT_INFO)
                        self.update_LoadSignal.emit(self.UPDATE_LOGIC)
                        return
                    elif compare == "diff":
                        print("未录入陌生人数据库人员")
                        self.id = str(random.randint(10000,99999))
                        face_height = biggest_face.bottom() - biggest_face.top()
                        face_width = biggest_face.right() - biggest_face.left()
                        im_blank = numpy.zeros((face_height, face_width, 3), numpy.uint8)
                        try:
                            for ii in range(face_height):
                                for jj in range(face_width):
                                    im_blank[ii][jj] = im_rd[biggest_face.top() + ii][biggest_face.left() + jj]
                            self.pic_num += 1
                            # 解决python3下使用cv2.imwrite存储带有中文路径图片
                            if len(self.id) > 0:
                                if self.id not in (os.listdir(self.PATH_FACE)):
                                    os.makedirs(self.PATH_FACE + self.id)
                                    print("开启写入数据")
                                    cv2.imencode('.jpg', im_blank)[1].tofile(
                                        self.PATH_FACE + self.id + "/img_face_" + str(self.pic_num) + ".jpg")  # 正确方法
                                    print("写入本地：",
                                          str(self.PATH_FACE + self.id) + "/img_face_" + str(self.pic_num) + ".jpg")
                                else:
                                    self.flag_registed = True
                                    print("此人已经存在")
                        except:
                            print('traceback.print_exc():', traceback.print_exc())
                            print("保存照片异常,请对准摄像头")
                            return False

                        if self.pic_num == 10:
                            self.othersRegister()
                            self.update_LoadSignal.emit(self.UPDATE_LOGIC)
                            return True
                        pass
                '''

    # 信号槽处理
    def signalHandle(self, event):
        if event == self.REGISTER_SINGAL:
            self.start() # 开启线程，处理自动核验人脸时线程挂起无法运行的情况
            self.AUTO_CHECKFACE_SINGAL = False
            self.CHECKFACE_SINGAL = False
        elif event == self.INSPECT_FACE_SINGAL:
            self.start()  # 开启线程，处理自动核验人脸时线程挂起无法运行的情况
            self.AUTO_CHECKFACE_SINGAL = False
            self.CHECKFACE_SINGAL = True
        elif event == self.AUTO_CHECK_SINGAL:
            self.start() # 开启线程，处理自动核验人脸时线程挂起无法运行的情况
            self.AUTO_CHECKFACE_SINGAL = True
            self.CHECKFACE_SINGAL = False
        elif event == self.EXIT_SINGAL:
            self.IS_EXIT == True

    # 获取注册用户名称id
    def setName(self,name,id):
        self.name = name
        self.id = id

    # 获取图片
    def setImage(self,img):
        self.image = img

    # 解锁处理TODO
    def unlockHandle(self):
        print("UNLOCK")
        pass

    # 线程执行
    def run(self):
        while True:
            if self.EXIT_SINGAL == True:
                break                # 退出程序处理
            if self.AUTO_CHECKFACE_SINGAL == True:
                self.punchCardCap(False)
                self.sleep(3)        # 自动扫描处理
                print("自动扫描处理")
            elif self.CHECKFACE_SINGAL == True:
                temp = self.punchCardCap(True)
                if temp == True:
                    self.unlockHandle()  # 人脸解锁处理
                else:
                    print("未识别的人脸")
                print("人脸解锁处理")
            else:
                try:
                    temp = self.registerCap()  # 用户注册处理
                except:
                    print('traceback.print_exc():', print_exc())
                # temp = True
                print("用户注册处理")
                if temp == True:
                    try:
                        self.Register_FinishSignal.emit(self.Register_FINISHSINGAL)
                        self.AUTO_CHECKFACE_SINGAL = True
                        self.CHECKFACE_SINGAL = False
                        print("注册成功")
                    except:
                        print('traceback.print_exc():', print_exc())
                    # QMessageBox.critical(self, '识别提示', '没有检查到人脸，请靠近一点')
                elif temp == self.FACE_EXISTS:
                    self.Register_FinishSignal.emit(self.Register_FAILED)
                    self.AUTO_CHECKFACE_SINGAL = True
                    self.CHECKFACE_SINGAL = False
                    print("此人已经存在")
        pass





if __name__ == "__main__":
    x = "test.db"
    a = FaceLearning(x)
    a.registerCap()
    print("ok")
    pass


