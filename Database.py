import zlib
import sqlite3
import io
import numpy as np


class LearnDatabase():
    # 数据库部分
    # 初始化数据库
    MAXSIZE = 100
    def __init__(self,file):
        self.filename = file
        self.initDatabase()

    def initDatabase(self):
        conn = sqlite3.connect(self.filename)  #建立数据库连接
        cur = conn.cursor()             #得到游标对象
        # 创建 worker_info库
        cur.execute('''create table if not exists worker_info
        (name text not null,
        id int not null primary key,
        face_feature array not null)''')
        # 创建 logcat库
        cur.execute('''create table if not exists logcat
         (datetime text not null,
         id text not null primary key,
         name text not null,
         late text not null)''')
        # 创建 others库
        cur.execute('''create table if not exists others
        (datetime text not null,
        id int not null primary key,
        face_feature array not null)''')
        # 创建 account库
        cur.execute('''create table if not exists account
        (account_num text not null primary key,
        password text not null,
        keyid int not null )''')
        cur.close()
        conn.commit()
        conn.close()

    def adapt_array(self,arr):
        out = io.BytesIO()
        np.save(out, arr)
        out.seek(0)

        dataa = out.read()
        # 压缩数据流
        return sqlite3.Binary(zlib.compress(dataa, zlib.Z_BEST_COMPRESSION))

    def convert_array(self,text):
        out = io.BytesIO(text)
        out.seek(0)

        dataa = out.read()
        # 解压缩数据流
        out = io.BytesIO(zlib.decompress(dataa))
        return np.load(out)

    def insertRow(self,Row,type):
        conn = sqlite3.connect(self.filename)  # 建立数据库连接
        cur = conn.cursor()  # 得到游标对象
        try:
            if type == 1:
                cur.execute("insert into worker_info (id,name,face_feature) values(?,?,?)",
                        (Row[0],Row[1],self.adapt_array(Row[2])))
                print("写人脸数据成功")
            if type == 2:
                cur.execute("insert into logcat (id,name,datetime,late) values(?,?,?,?)",
                            (Row[0],Row[1],Row[2],Row[3]))
                print("写日志成功")
            if type == 3:
                cur.execute("insert into others (id,datetime,face_feature) values(?,?,?)",
                        (Row[0],Row[1],self.adapt_array(Row[2])))
                print("写陌生人数据成功")
            if type == 4:
                cur.execute("insert into account (account_num,password,keyid) values(?,?,?)",
                            (Row[0], Row[1],Row[2]))
                print("写管理员数据成功")
                pass
        except Exception as e:
            print(e)
            conn.rollback()
            pass
        cur.close()
        conn.commit()
        conn.close()
        pass

    def deleteRow(self,order,type):
        conn = sqlite3.connect(self.filename)  # 建立数据库连接
        cur = conn.cursor()  # 得到游标对象
        try:
            if type == 1:
                sql_delete = "delete from worker_info where id =" + str(order)
                cur.execute(sql_delete)
                print("删除人脸数据成功" + "id=" + str(order))
            if type == 2:
                sql_delete = "delete from logcat where id =" + str(order)
                cur.execute(sql_delete)
                print("删除日志成功" + "id=" + str(order))
            if type == 3:
                sql_delete = "delete from others where id =" + str(order)
                cur.execute(sql_delete)
                print("删除陌生人脸数据成功" + "id=" + str(order))
            if type == 4:
                sql_delete = "delete from account where account_num =" + str(order)
                cur.execute(sql_delete)
                print("删除管理员账户成功" + "account_num=" + str(order))
                pass
        except Exception as e:
            print(e)
            conn.rollback()
            pass
        cur.close()
        conn.commit()
        conn.close()
        pass

    def loadDataBase(self,type):
        conn = sqlite3.connect(self.filename)  # 建立数据库连接
        cur = conn.cursor()  # 得到游标对象

        # 人脸识别设置记录库
        if type == 1:
            self.knew_id = []
            self.knew_name = []
            self.knew_face_feature = []
            cur.execute('select id,name,face_feature from worker_info')
            origin = cur.fetchall()
            for row in origin:
                # print(row[0])
                self.knew_id.append(row[0])
                # print(row[1])
                self.knew_name.append(row[1])
                # print(self.convert_array(row[2]))
                self.knew_face_feature.append(self.convert_array(row[2]))

        # 所识别访客记录数据库
        if type == 2:
            self.logcat_id = []
            self.logcat_name = []
            self.logcat_datetime = []
            self.logcat_late = []
            cur.execute('select id,name,datetime,late from logcat')
            origin = cur.fetchall()
            for row in origin:
                # print(row[0])
                self.logcat_id.append(row[0])
                # print(row[1])
                self.logcat_name.append(row[1])
                # print(row[2])
                self.logcat_datetime.append(row[2])
                # print(row[3])
                self.logcat_late.append(row[3])

        # 陌生人来访记录库
        if type == 3:
            self.others_id = []
            self.others_datetime = []
            self.others_face_feature = []
            cur.execute('select id,datetime,face_feature from others')
            origin = cur.fetchall()
            for row in origin:
                # print(row[0])
                self.others_id.append(row[0])
                # print(row[1])
                self.others_datetime.append(row[1])
                # print(self.convert_array(row[2]))
                self.others_face_feature.append(self.convert_array(row[2]))

        # 管理员账户
        if type == 4:
            self.account_num = []
            self.password = []
            self.keyid = []
            cur.execute('select account_num,password,keyid from account')
            origin = cur.fetchall()
            for row in origin:
                # print(row[0])
                self.account_num.append(row[0])
                # print(row[1])
                self.password.append(row[1])
                # print(row[2])
                self.keyid.append(row[2])
        pass

    def test(self,row,type):
        # self.insertRow(row,type)
        print("插入数据成功")
        self.loadDataBase(type)
        print("加载数据成功")
        if type == 1:
            print(self.knew_id,
            self.knew_name,
            self.knew_face_feature)
        if type == 2:
            print(self.logcat_id,
            self.logcat_name,
            self.logcat_datetime,
            self.logcat_late)
        if type == 3:
            print(self.others_id,
            self.others_datetime,
            self.others_face_feature)
        if type == 4:
            print(self.account_num,
                  self.password)
            pass
        # self.deleteRow(row[0],type)
        print("删除数据成功")
        self.loadDataBase(1)
        self.loadDataBase(2)
        self.loadDataBase(3)
        self.loadDataBase(4)
        print("重新加载所有数据成功")
        print(self.knew_id,
              self.knew_name,
              self.knew_face_feature)

        print(self.logcat_id,
              self.logcat_name,
              self.logcat_datetime,
              self.logcat_late)

        print(self.others_id,
              self.others_datetime,
              self.others_face_feature)
        print(self.account_num,
              self.password,
              self.keyid)
        pass



if __name__ == "__main__":
    file = "test.db"
    row1 = [584,"荷里活",np.arange(0,128,1)]
    row2 = [27,"荷里活","2019-5-2","23:44"]
    row3 = [2567,"2019-5-6-19:30",np.arange(0,128,1)]
    row4 = ["1507965","1234",'0']
    type = 4
    a = LearnDatabase(file)
    # a.loadDataBase(type)
    # print(a.account_num,isinstance(a.account_num[0],str))
    a.test(row4,type)
    # print(len(a.logcat_id))
    pass
