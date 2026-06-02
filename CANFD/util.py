
from PyQt6.QtWidgets import QWidget, QApplication,QTableWidgetItem,QInputDialog,QMessageBox

def CanDiag_Seed_2_Key(in_seed):
    calData = [0] * 4
    returnKey = [0] * 4
    u8xorArray = [0x66, 0x77, 0x83, 0xE9]

    # 处理 calData 数组
    for i in range(4):
        calData[i] = ((in_seed >> (24 - i * 8)) & 0xFF) ^ u8xorArray[i]

    # 计算 returnKey 数组
    returnKey[0] = ((calData[2] & 0x03) << 6) | ((calData[3] & 0xFC) >> 2)
    returnKey[1] = ((calData[3] & 0x03) << 6) | (calData[0] & 0x3F)
    returnKey[2] = (calData[0] & 0xFC) | ((calData[1] & 0xC0) >> 6)
    returnKey[3] = (calData[1] & 0xFC) | (calData[2] & 0x03)

    # 组合 returnKey 数组生成 u32Key
    u32Key = (returnKey[0] << 24) | (returnKey[1] << 16) | (returnKey[2] << 8) | returnKey[3]

    return u32Key

def Unsignal_Change(unsigned_value):
    return unsigned_value if unsigned_value < 0x8000 else unsigned_value - 0x10000
def to_unsigned_16bit(n):
    # 若n为负数，则加上0x10000
    return n if n >= 0 else n + 0x10000
def STI(tw,col,signal,value,unit):
    tw.setItem(col,0,QTableWidgetItem(signal))
    tw.setItem(col, 1, QTableWidgetItem(value))
    tw.setItem(col, 2, QTableWidgetItem(unit))

def STIID(Canid,ID,tw,col,signal,value,unit,dictRec,up_down):

    """
        "时间":-1,
    "霍尔电流":-1,
    "B端电压上半簇":-1,
    "P端电压上半簇":-1,
    "运行状态上半簇":-1,
    "SOC上半簇":-1,
    "最大单体电压上半簇":-1,
    "最小单体电压上半簇":-1,
    "充电继电器上半簇":-1,
    "放电继电器上半簇":-1,
    "最严重告警等级上半簇":-1,
    "OCV更新次数上半簇":-1,
    "最高温度上半簇":-1,
    "最低温度上半簇":-1,
    "分流器电流": -1,
    "B端电压下半簇": -1,
    "P端电压下半簇": -1,
    "运行状态下半簇": -1,
    "SOC下半簇": -1,
    "最大单体电压下半簇": -1,
    "最小单体电压下半簇": -1,
    "充电继电器下半簇": -1,
    "放电继电器下半簇":-1,
    "最严重告警等级下半簇":-1,
    "OCV更新次数下半簇": -1,
    "最高温度下半簇": -1,
    "最低温度下半簇": -1,
    "B端电压整簇":-1,
    "P端电压整簇":-1,
    "SOH":-1,
    """
    if up_down==0:
        if(Canid.casefold()==ID.casefold()):
            tw.setItem(col,0,QTableWidgetItem(signal))
            tw.setItem(col, 1, QTableWidgetItem(value))
            tw.setItem(col, 2, QTableWidgetItem(unit))

            if signal=="霍尔电流":
                dictRec["霍尔电流"] = value
            if signal=="B端电压":
                dictRec["B端电压上半簇"] = value
            if signal=="P端电压":
                dictRec["P端电压上半簇"] = value
            if signal=="运行状态":
                dictRec["运行状态上半簇"] = value
            if signal=="SOC":
                dictRec["SOC上半簇"] = value
            if signal=="最大单体电压":
                dictRec["最大单体电压上半簇"] = value
            if signal=="最小单体电压":
                dictRec["最小单体电压上半簇"] = value
            if signal=="充电继电器":
                dictRec["充电继电器上半簇"] = value
            if signal=="放电继电器":
                dictRec["放电继电器上半簇"] = value
            if signal=="最严重告警等级":
                dictRec["最严重告警等级上半簇"] = value
            if signal=="OCV_UPDT_COUNT_UP":
                dictRec["OCV更新次数上半簇"] = value


    if up_down==1:
        if (Canid.casefold() == ID.casefold()):
            tw.setItem(col, 0, QTableWidgetItem(signal))
            tw.setItem(col, 1, QTableWidgetItem(value))
            tw.setItem(col, 2, QTableWidgetItem(unit))

            if signal == "分流器电流":
                dictRec["分流器电流"] = value
            if signal == "B端电压":
                dictRec["B端电压下半簇"] = value
            if signal == "P端电压":
                dictRec["P端电压下半簇"] = value
            if signal == "运行状态":
                dictRec["运行状态下半簇"] = value
            if signal == "SOC":
                dictRec["SOC下半簇"] = value
            if signal == "最大单体电压":
                dictRec["最大单体电压下半簇"] = value
            if signal == "最小单体电压":
                dictRec["最小单体电压下半簇"] = value
            if signal == "充电继电器":
                dictRec["充电继电器下半簇"] = value
            if signal == "放电继电器":
                dictRec["放电继电器下半簇"] = value
            if signal == "最严重告警等级":
                dictRec["最严重告警等级下半簇"] = value
            if signal == "OCV_UPDT_COUNT_DOWN":
                dictRec["OCV更新次数下半簇"] = value

    if up_down == 2:
        if (Canid.casefold() == ID.casefold()):
            tw.setItem(col, 0, QTableWidgetItem(signal))
            tw.setItem(col, 1, QTableWidgetItem(value))
            tw.setItem(col, 2, QTableWidgetItem(unit))

            if signal == "B总压":
                dictRec["B端电压整簇"] = value
            if signal == "P总压":
                dictRec["P端电压整簇"] = value
            if signal == "SOH":
                dictRec["SOH"] = value
