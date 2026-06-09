import matplotlib.pyplot as plt

# =======================
# 简单的 PID 控制器类
# =======================
class PID:
    def __init__(self, Kp, Ki, Kd, dt=1.0):
        self.Kp = Kp
        self.Ki = Ki
        self.Kd = Kd
        self.dt = dt
        self.integral = 0
        self.prev_error = 0

    def update(self, setpoint, measurement):
        error = setpoint - measurement
        self.integral += error * self.dt
        derivative = (error - self.prev_error) / self.dt

        output = self.Kp * error + self.Ki * self.integral + self.Kd * derivative
        self.prev_error = error
        return output


# =======================
# 系统仿真（热水壶）
# =======================
# 初始条件
T_env = 25   # 环境温度
T = 20       # 初始水温
setpoint = 80  # 目标温度
dt = 1
time = []
temperature = []

# PID 控制器
pid = PID(Kp=2.0, Ki=0.1, Kd=5.0, dt=dt)

# 仿真 100 秒
for t in range(100):
    # PID 计算加热功率 (0~100)
    u = pid.update(setpoint, T)
    u = max(0, min(100, u))  # 限制功率范围

    # 系统模型：水温变化（简单线性近似）
    # dT/dt = (加热功率/100)*5 - (T - T_env)*0.05
    dT = (u/100)*5 - (T - T_env)*0.05
    T += dT

    time.append(t)
    temperature.append(T)

# =======================
# 绘图
# =======================
plt.plot(time, temperature, label="Water Temperature")
plt.axhline(setpoint, color="r", linestyle="--", label="Setpoint (80℃)")
plt.xlabel("Time (s)")
plt.ylabel("Temperature (℃)")
plt.legend()
plt.title("PID Control Example - Water Heating")
plt.show()
