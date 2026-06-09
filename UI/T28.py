import sys
import time
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget, QPushButton, QInputDialog, QMessageBox, QHeaderView,QComboBox,QHBoxLayout,QAbstractItemView
)

import yaml
from .conf import config
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("表格修改和提交示例")
        self.setGeometry(100, 100, 1200, 600)

        # 创建中央小部件和布局
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()
        central_widget.setLayout(layout)






        # 创建 QTableWidget
        self.table_widget = QTableWidget()
        layout.addWidget(self.table_widget)

        # 初始化表格，设置行数和列数（5 行，100 列）
        self.table_widget.setRowCount(48)
        self.table_widget.setColumnCount(48)

        # 生成列标题，例如 "列1", "列2", ..., "列100"
        self.headers = ["告警名称", "一级告警", "二级告警", "三级告警", "四级告警", "五级告警", "一级回差值",
                   "二级回差值", "三级回差值", "四级回差值", "五级回差值", "一级产生延时", "二级产生延时",
                   "三级产生延时",
                   "四级产生延时", "五级产生延时", "一级消除延时", "二级消除延时", "三级消除延时", "四级消除延时",
                   "五级消除延时",
                   "放电一级Relay", "脱扣一级Relay", "充电一级Relay", "放电二级Relay", "脱扣二级Relay", "充电二级Relay",
                   "放电三级Relay",
                   "脱扣三级Relay", "充电三级Relay", "一级继电器延时", "二级继电器延时", "三级继电器延时",
                   "一级充电输出额", "二级充电输出额", "三级充电输出额",
                   "四级充电输出额", "五级充电输出额",
                   "一级放电输出额", "二级放电输出额", "三级放电输出额", "四级放电输出额", "五级放电输出额",
                   "一级告警使能", "二级告警使能", "三级告警使能", "四级告警使能", "五级告警使能"
                   ]
        self.table_widget.setHorizontalHeaderLabels(self.headers)

        self.table_widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        # #填充数据
        # data = [[f"数据{row+1}-{col+1}" for col in range(100)] for row in range(5)]
        # for row, row_data in enumerate(data):
        #     for col, item in enumerate(row_data):
        #         self.table_widget.setItem(row, col, QTableWidgetItem(item))

        # 自动调整列宽
        # header = self.table_widget.horizontalHeader()
        # header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)  # 根据内容调整列宽
        #self.table_widget.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)  # 禁止编辑

        # 创建水平布局用于放置按钮，并添加到垂直布局的下方
        button_layout = QHBoxLayout()
        layout.addLayout(button_layout)

        # 创建下拉框选择电池包
        self.comboBox = QComboBox(self)
        button_layout.addWidget(self.comboBox)
        self.comboBox.addItems([str(i) for i in range(0,16)])

        # 添加“修改”按钮
        self.button = QPushButton("刷新数据")
        button_layout.addWidget( self.button)
        #self.button.clicked.connect(self.modify_cell_value)

        # 添加“修改”按钮
        self.modify_button = QPushButton("修改选中的单元格")
        button_layout.addWidget(self.modify_button)
        self.modify_button.clicked.connect(self.modify_cell_value)

        # 添加“提交”按钮
        self.submit_button = QPushButton("提交修改内容")
        button_layout.addWidget(self.submit_button)
        self.submit_button.clicked.connect(self.submit_data)

        #self.setItem(1,1,"1")
        # for i in range(0,44):
        #     self.change_row_color(i,QColor("green"))

    def modify_cell_value(self):
        # 获取当前选中的单元格
        selected_items = self.table_widget.selectedItems()

        if selected_items:
            selected_item = selected_items[0]  # 假设用户只选择了一个单元格
            row = selected_item.row()
            col = selected_item.column()

            # 弹出输入框让用户输入新的值
            # new_value, ok = QInputDialog.getText(self, "修改单元格", f"请输入新的值 (行 {row+1}, 列 {col+1}):")
            #
            # if ok and new_value:  # 如果用户点击了OK并输入了新值
            #     self.table_widget.setItem(row, col, QTableWidgetItem(new_value))
        else:
            # 如果没有选中任何单元格，显示警告框
            QMessageBox.warning(self, "警告", "请先选择一个单元格！")

    def submit_data(self):
        # 获取表格中的所有数据
        row_count = self.table_widget.rowCount()
        column_count = self.table_widget.columnCount()

        # 用于存储表格数据的列表
        table_data = []

        for row in range(row_count):
            row_data = []
            for col in range(column_count):
                # 获取每个单元格的内容
                item = self.table_widget.item(row, col)
                if item is not None:
                    row_data.append(item.text())
                else:
                    row_data.append('')  # 如果单元格为空，添加空字符串
            table_data.append(row_data)

        # 此处可以将 table_data 处理：比如打印、保存到文件或提交到服务器
        print("提交的数据：")
        for row in table_data:
            print(row)

        # 弹出提示框，提示用户提交成功
        QMessageBox.information(self, "提交成功", "表格数据已成功提交！")
    def setItem(self,row,col,con):
        item = QTableWidgetItem(con)
        self.table_widget.setItem(row, col, item)

        if (config["Alarm_name_key"][list(config["Alarm_name_key"].keys())[row]]==0):
            item.setBackground(QColor(200, 200, 200))
        else:
            item.setBackground(QColor("green"))

    def change_row_color(self, row_index, color):
        # 改变某一行的背景颜色
        for col in range(len(self.headers)):
            item = self.table_widget.item(row_index, col)
            if item is None:
                # item.setBackground(color)
                item = QTableWidgetItem()
                self.table_widget.setItem(row_index, col, item)  # 设置默认的 QTableWidgetItem
            item.setBackground(color)  # 改变背景颜色




if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.change_row_color(1,QColor("red"))


    window.show()

    sys.exit(app.exec())
