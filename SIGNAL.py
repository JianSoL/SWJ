BCUSignalQ = [
    0x1D2,
    0x1D3,
    0x1D4,
    0x1D5,
    0x9084A,
    0x9084B,
    0x90878,
    0x90879,
    0x326,
    0x327,
    0x32A,
    0x32B,
    0x31C,
    0x31D,
    0xE,#系统电流
    0x5B,#B端电压
    0x5C,#P端电压
    0xC,#系统运行状态
    0x10,#系统SOC
    0x148,#系统最大单体电压
    0x14B,#系统最小单体电压
    0x00,#充电继电器状态（暂无）
    0x00,#放电继电器状态（暂无）
    0x114,#系统最严重告警级别
    0x1AF,#最大允许充电电流
    0x1AD,#最大允许放电电流
    0x1C0,#MAX_SOC
    0x1C1,#MIN_SOC
    0x1C2,#PURE_SOC
    0x1C3,#REVISE_SOC
    0x1C4,#REVISESOC_TEMP
    0x1C5,#CELL_MIN_SOC_TEMP
    0x1C6,#CELL_MAX_SOC_TEMP
    0x1C7,#PACK_FUZZY_SOC
    0x1BE,#OCVMAXSOC
    0x1BF,#OCVMINSOC
    0x1CA,#OCV_UPDT_COUNT
    0x1CB,#OCV_FAIL_CODE
    0x1C9,#VAR_SYS_FULL_CHRG_DCHG
    0x90801,#TOTAL_CHRG_AH
    0x90802,#TOTAL_CHRG_AH
    0x90803,#CHRG_TIMES
    0x90804,#DSCH_TIMES
    0x1C8,#VAR_SYS_FULL_CHRG_FLG
    0x90401,#模组数
    0x90402,#每个模组AFE数量
    0x9045F,#电池箱电芯数
    0x90460,#电池箱温度数
    0x90461,#极柱温度数
    0x9040D,#中线标志位
    # 0x354,#MAX_SOC_UP
    # 0x356,#MIN_SOC_UP
    # 0x358,#PURE_SOC_UP
    # 0x346,#REVISE_SOC_UP
    # 0x348,#REVISESOC_TEMP_UP
    # 0x34A,#MIN_SOC_TEMP_UP
    # 0x34C,#MAX_SOC_TEMP_UP
    # 0x34E,#FUZZY_SOC_UP
    # 0x33C,#OCVMAXSOC_UP
    # 0x33A,#OCVMINSOC_UP
    # 0x33E,#OCV_UPDT_COUNT_UP
    # 0x340,#OCV_FAIL_CODE_UP
    # 0x334,#FULL_CHRG_FLG_UP
    0x1D, # VAR_SYS_SOE_UP
    0x1E, # VAR_SYS_SOE_DOWN
    0x20, #VAR_SYS_SOE_DISP_UP
    0x21, #VAR_SYS_SOE_DISP_DOWN
    0x254,#VAR_SYS_SOE_RADE_UP
    0x255,#VAR_SYS_SOE_ACE_UP
    0x256,  # VAR_SYS_SOE_RADE_DOWN
    0x257,  # VAR_SYS_SOE_ACE_DOWN
    0x1CD, #VAR_SYS_SINGLE_CHRG_KWH_UP
    0x1CE, #VAR_SYS_SINGLE_DISCHRG_KWH_UP
    0x1CF, #VAR_SYS_SINGLE_CHRG_KWH_DOWN
    0x1D0, #VAR_SYS_SINGLE_DISCHRG_KWH_DOWN
    0x352,#VAR_SYS_OCV_RESULT_UP
    0x353,#VAR_SYS_OCV_RESULT_DOWN
    0x5B,#VAR_SYS_ANALOG_BAT_VOLT
    0x5C,#VAR_SYS_ANALOG_PACK_VOLT
    0x342,#VAR_SYS_FULL_CHRG_DCHG_UP
    0x343,#VAR_SYS_FULL_CHRG_DCHG_DOWN
    0x334,#VAR_SYS_FULL_CHRG_FLG_UP
    0x335,#VAR_SYS_FULL_CHRG_FLG_DOWN
    0x90446,#PAR_SYS_BAL_START_DIV_VOLT 均衡启动压差
    0x90447, #PAR_SYS_BAL_STOP_DIV_VOLT 均衡停止压差
    0x9044A ,#PAR_SYS_BAL_START_VOLT_PASSIVE 均衡启动电压
    0x9044B,#PAR_SYS_BAL_VOLT_UP   均衡保护电压上限
    0x9044C,#PAR_SYS_BAL_VOLT_DN 均衡保护电压下限
    0x9044D,#PAR_SYS_CALI_BAL_TEMP_UP 均衡开启温度上限
    0x9044E,#PAR_SYS_CALI_BAL_TEMP_DN 均衡开启温度下限
    0x9045D,#PAR_SYS_BAT_RATED_CAPA   电池额定容量[ 0.1AH ]
    0x90479,#PAR_SYS_PRECHARGE_MODE
    0x9047A,#PAR_SYS_PRECHARGE_VOLT_RATE
    0x9047C,#PAR_SYS_PRECHARGE_MIN_TIME最小预充时间
    0x9049C,#PAR_SYS_SOXC_CHRG_REV_TIME
    0x9049D,#PAR_SYS_SOXC_CHRG_REV_TIME_MIN
    0x9047D,#预充电流
    0x346,#Reveise_SOC_UP
    0x347,#Reveise_SOC_DOWN
    0x348,#Reveise_SOC_Temp_UP
    0x349,#Reveise_SOC_Temp_DOWN
    0x34A,#MIN_SOC_Temp_UP
    0x34B,#MIN_SOC_Temp_DOWN
    0x34C,#MAX_SOC_Temp_UP
    0x34D,#MAX_SOC_Temp_DOWN
    0x34E,#Fuzzy_SOC_UP
    0x34F,#Fuzzy_SOC_DOWN
    0x354,#MAX_SOC_UP
    0x355,#MAX_SOC_DOWN
    0x356,#MIN_SOC_UP
    0x357,#MIN_SOC_DOWN
    0x358,#PURE_SOC_UP
    0x359,#PURE_SOC_DOWN
    0x33A,#OCVMIN_SOCUP
    0x33B,#OCVMIN_SOCDOWN
    0x33C,#OCVMAX_SOCUP
    0x33D,#OCVMAX_SOCDOWN
    0x33E,#OCVUP_DATA_COUNT_UP
    0x33F,#OCVUP_DATA_COUNT_DOWN
    0x340,#OCV_FAIL_CODE_UP
    0x341,#OCV_FAIL_CODE_DOWN


    0x1FF,#剩余充电时间
    0x200,#剩余放电时间
    0x14E,#单体最高温度
    0x151,#单体最低温度
    0x144,#平均温度
    0x15,#SOE
    0x1F,#SOE_DISP
    0x252,#剩余可放电[0.01KWH]
    0x253,#剩余可充电[0.01KWH]
    0x1FD,#单次充电KWH[0.01KWH]
    0x1FE,#单次放电KWH[0.01KWH]
    0x1D7,#OCV置位结果
    0x1C8,#满充满放状态
    0x1C9,#满充状态

    0x9040D,#N线标志位
    0x9049E,#SOC定期下降时间
    0x9049F,#SOC定期下降额







]

BAUSignalQ = [
    90,#请求温度1
    91,#请求温度2
    0x30C1,#PAR_SYS_BCU_NUM
    0x30D0,#PAR_SYS_BRANCH_NUM
    0x30D6,#PAR_SYS_MIN_RUNNING_BCU_NUM
    0x3016,#VAR_VMS_CTRL_CIRCUIT_BREAKER
    0x0185,#VAR_SYS_MANUAL_CONNECT_GRID
    0x3029,#VAR_VMS_CTRL_FORCE_CHG_CMD,
    0x00DC,#VAR_SYS_ALLOW_DSCH_CURR
    0x00DE,#VAR_SYS_ALLOW_CHRG_CURR
    0x00ED,#VAR_SYS_ALLOW_DHRG_CURR_UP
    0x00EF,#VAR_SYS_ALLOW_DHRG_CURR_DOWN
    0x00D2,#VAR_SYS_ALLOW_CHRG_CURR_UP
    0x00D4,#VAR_SYS_ALLOW_CHRG_CURR_down
    0x3105,#PAR_SYS_RUN_PRE_VOLT_RATE
    0x3104,#PAR_SYS_BCU_WITH_VOLT_DV
    0x3106,#PAR_SYS_BCU_WITH_VOLT_DV
    0x00BE,#VAR_SYS_MOST_SEVERE_LEVEL
    0x30D5,#PAR_SYS_BAT_HAS_N
    0xF,#VAR_SYS_RUN_STATUS [0、初始 1、自测 2、准备 4、高压待机  10、切断 ]
    0x3101,#预充时间
]

ResData = {
    "时间":[],
    "霍尔电流":[],
    "B端电压上半簇":[],
    "P端电压上半簇":[],
    "运行状态上半簇":[],
    "SOC上半簇":[],
    "最大单体电压上半簇":[],
    "最小单体电压上半簇":[],
    "充电继电器上半簇":[],
    "放电继电器上半簇":[],
    "最严重告警等级上半簇":[],
    "OCV更新次数上半簇":[],
    "最高温度上半簇":[],
    "最低温度上半簇":[],
    "分流器电流": [],
    "B端电压下半簇": [],
    "P端电压下半簇": [],
    "运行状态下半簇": [],
    "SOC下半簇": [],
    "最大单体电压下半簇": [],
    "最小单体电压下半簇": [],
    "充电继电器下半簇": [],
    "放电继电器下半簇":[],
    "最严重告警等级下半簇":[],
    "OCV更新次数下半簇": [],
    "最高温度下半簇": [],
    "最低温度下半簇": [],
    "B端电压整簇":[],
    "P端电压整簇":[],
    "SOH":[],
}


ResDataRec = {
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
}